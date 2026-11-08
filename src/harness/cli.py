"""``bakeoff`` command line: run variants, evaluate, report, refine and deliver."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.config import Settings, resolve_scale_tolerance
from harness.core.errors import error_kind
from harness.core.models import DEFAULT_SAMPLE_CSV, Piece, VariantResult, load_pieces
from harness.core.registry import available_variants, get_variant
from harness.core.variant import is_not_applicable
from harness.post.blender_post import BlenderPostError, postprocess
from harness.post.bpy_post import DEFAULT_FIT_GUARD
from harness.prep.requirements import PHOTO_REQUIREMENTS

ROUTER_CLASSIFIERS = ("auto", "vlm", "rules")  # mirrors harness.variants.f_router.CLASSIFIERS

POST_REASON_NO_BLENDER = "sin Blender"
POST_LOG_TAIL_CHARS = 2000
PREFLIGHT_EXIT_CODE = 2

# Keys each variant needs before its first paid call (Settings attribute → env var name).
KEY_ENV = {
    "tripo_api_key": "TRIPO_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
    "meshy_api_key": "MESHY_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
}
VARIANT_KEYS: dict[str, tuple[str, ...]] = {
    "A": ("tripo_api_key",),
    "B": ("tripo_api_key",),
    "C": ("tripo_api_key", "gemini_api_key"),
    "D": ("meshy_api_key",),
    # F: its organic routes (B: Tripo; C: Tripo + Gemini). The VLM key only with
    # --router-classifier vlm (see router_keys): "auto" falls back to rules without it.
    "F": ("tripo_api_key", "gemini_api_key"),
}
VARIANTS_NEEDING_BLENDER = frozenset({"E"})
# F routes rectilinear pieces to E but falls back to the organic route without Blender.
VARIANTS_PREFERRING_BLENDER = frozenset({"F"})

app = typer.Typer(help="Bake-off de pipelines foto→3D.", no_args_is_help=True)
console = Console(soft_wrap=True)  # long paths stay copyable (no hard wraps)


class _PostStep:
    """Identical headless-Blender post-processing for every candidate of every variant.

    After the first ``BlenderNotAvailable`` Blender is not launched again in this run.
    """

    def __init__(
        self,
        enabled: bool,
        fit_box: bool = False,
        fit_guard: float = DEFAULT_FIT_GUARD,
        tolerance: float | None = None,
    ) -> None:
        self.enabled = enabled
        self.fit_box = fit_box
        self.fit_guard = fit_guard
        self.tolerance = tolerance
        self.blender_missing = False

    def __call__(self, cand_dir: Path, piece: Piece) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        # A stale model_post.glb from an earlier run would be picked up by the evaluation.
        storage.model_post_path(cand_dir).unlink(missing_ok=True)
        if self.blender_missing:
            return {"ok": False, "reason": POST_REASON_NO_BLENDER}
        glb = storage.model_path(cand_dir)
        if not glb.is_file():
            return {"ok": False, "reason": f"no existe {glb.name}"}
        try:
            result = postprocess(
                glb,
                storage.model_post_path(cand_dir),
                piece,
                fit_box=self.fit_box,
                fit_guard=self.fit_guard,
                tolerance=self.tolerance,
            )
        except BlenderNotAvailable:
            self.blender_missing = True
            console.print("  [yellow]postprocesado omitido: sin Blender (BLENDER_BIN)[/yellow]")
            return {"ok": False, "reason": POST_REASON_NO_BLENDER}
        except BlenderPostError as exc:
            return {"ok": False, "reason": (exc.log or str(exc))[-POST_LOG_TAIL_CHARS:]}
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "reason": f"timeout de Blender ({exc.timeout} s)"}
        except OSError as exc:
            return {"ok": False, "reason": f"no se pudo lanzar Blender: {exc}"}
        raw = result.raw or {}
        return {
            "ok": True,
            "glb_path": str(result.glb_path),
            "seconds": result.seconds,
            "errors": result.errors,
            "errors_axis": result.errors_axis,
            "scale_factor": result.scale_factor,
            "draco": result.draco,
            # Guard outcome from post_meta.json: lets `refine` tell a rejected fit apart.
            "fit_box_requested": bool(raw.get("fit_box_requested", self.fit_box)),
            "fit_box_applied": result.fit_box_applied,
            "fit_factors": result.fit_factors,
            "fit_skip_reason": raw.get("fit_skip_reason"),
            "errors_before_fit": result.errors_before_fit,
            "triangles_before": result.tris_before,
            "triangles_after": result.tris_after,
            "scale_tolerance": self.tolerance,
        }


def _blender_ok(settings: Settings) -> bool:
    return settings.blender_bin is not None and Path(settings.blender_bin).is_file()


def router_keys(classifier: str = "auto", organic_variant: str | None = None) -> tuple[str, ...]:
    """Keys F needs: the VLM key only with ``classifier="vlm"``, plus its organic route(s)."""
    keys = ["anthropic_api_key"] if classifier == "vlm" else []
    for route in [organic_variant] if organic_variant else ["C", "B"]:
        keys += VARIANT_KEYS.get(route.upper(), ())
    return tuple(dict.fromkeys(keys))


def variant_keys(
    name: str, *, router_classifier: str = "auto", organic_variant: str | None = None
) -> tuple[str, ...]:
    if name == "F":
        return router_keys(router_classifier, organic_variant)
    return VARIANT_KEYS.get(name, ())


def missing_keys(keys: tuple[str, ...], settings: Settings) -> list[str]:
    return [KEY_ENV[k] for k in keys if not getattr(settings, k)]


def preflight(
    variant_names: list[str],
    post: bool,
    settings: Settings,
    *,
    router_classifier: str = "auto",
    organic_variant: str | None = None,
) -> tuple[list[str], list[str]]:
    """Return ``(problems, warnings)`` (Spanish) for the requested variants and options."""
    problems: list[str] = []
    warnings: list[str] = []
    for name in variant_names:
        keys = variant_keys(
            name, router_classifier=router_classifier, organic_variant=organic_variant
        )
        missing = missing_keys(keys, settings)
        if missing:
            problems.append(f"Variante {name}: falta {', '.join(missing)}")
    blender = _blender_ok(settings)
    if not blender:
        where = (
            f"BLENDER_BIN no existe: {settings.blender_bin}"
            if settings.blender_bin
            else "BLENDER_BIN no definido"
        )
        for name in variant_names:
            if name in VARIANTS_NEEDING_BLENDER:
                problems.append(f"Variante {name}: necesita Blender ({where})")
            elif name in VARIANTS_PREFERRING_BLENDER:
                warnings.append(
                    f"Variante {name}: sin Blender las piezas rectilíneas irán a la ruta "
                    f"orgánica ({where})"
                )
        if post:
            problems.append(f"--post: el postprocesado necesita Blender ({where}); usa --no-post")
    return problems, warnings


def _usd(amount: float) -> str:
    """Spanish money format: 1.5 → "1,50 USD"."""
    return f"{amount:.2f} USD".replace(".", ",")


def _key(entry: dict[str, Any]) -> tuple[str, str]:
    return str(entry.get("piece_id")), str(entry.get("variant"))


class RunMeta:
    """Run-level ``meta.json`` written after EVERY (piece, variant) step and merged with the
    existing file, so an interrupted run keeps its bookkeeping and a reused ``--run-id``
    adds to it instead of overwriting it.

    ``results``/``skipped`` hold the latest outcome per (piece, variant) (they mirror what
    is on disk). ``errors`` are never dropped: when a step is attempted again, its earlier
    errors are kept with ``superseded: true``. ``total_cost_usd`` adds up every executed step.
    """

    def __init__(self, run_root: Path, run_id: str, candidates: int) -> None:
        self.run_root = run_root
        self.data = storage.read_meta(run_root)
        now = datetime.now(UTC).isoformat()
        self.data.setdefault("run_id", run_id)
        self.data.setdefault("created_at", now)
        self.data.setdefault("variants", [])
        self.data.setdefault("pieces", [])
        self.data.setdefault("total_cost_usd", 0.0)
        for list_key in ("results", "errors", "skipped"):
            self.data.setdefault(list_key, [])
        self.data["candidates"] = candidates

    def declare(self, variants: list[str], pieces: list[str]) -> None:
        for field, values in (("variants", variants), ("pieces", pieces)):
            for value in values:
                if value not in self.data[field]:
                    self.data[field].append(value)
        self.save()

    def result_for(self, key: tuple[str, str]) -> dict[str, Any] | None:
        return next((r for r in self.data["results"] if _key(r) == key), None)

    def has_active_error(self, key: tuple[str, str]) -> bool:
        return any(_key(e) == key and not e.get("superseded") for e in self.data["errors"])

    def _supersede(self, key: tuple[str, str]) -> None:
        for err in self.data["errors"]:
            if _key(err) == key:
                err["superseded"] = True

    def _replace(self, list_key: str, entry: dict[str, Any] | None, key: tuple[str, str]) -> None:
        kept = [e for e in self.data[list_key] if _key(e) != key]
        self.data[list_key] = [*kept, entry] if entry is not None else kept

    def record_result(self, result: VariantResult, cost: float) -> None:
        key = (result.piece_id, result.variant)
        self._supersede(key)
        self._replace("results", result.model_dump(mode="json"), key)
        skipped = None
        if is_not_applicable(result):
            skipped = {
                "piece_id": result.piece_id,
                "variant": result.variant,
                "kind": "not_applicable",
                "reason": result.notes,
            }
        self._replace("skipped", skipped, key)
        self.data["total_cost_usd"] = float(self.data["total_cost_usd"]) + cost
        self.save()

    def record_error(self, piece_id: str, variant: str, exc: BaseException) -> None:
        key = (piece_id, variant)
        self._supersede(key)
        self._replace("results", None, key)
        self._replace("skipped", None, key)
        self.data["errors"].append(
            {
                "piece_id": piece_id,
                "variant": variant,
                "kind": error_kind(exc),
                "error": repr(exc),
                "at": datetime.now(UTC).isoformat(),
            }
        )
        self.save()

    def save(self) -> None:
        self.data["updated_at"] = datetime.now(UTC).isoformat()
        storage.write_meta(self.run_root, self.data)


def _has_infra_candidate_error(workdir: Path) -> bool:
    """Whether a candidate of this step failed for an infrastructure reason (network...)."""
    for meta_file in sorted(workdir.glob("cand_*/meta.json")):
        cand_meta = storage.read_meta(meta_file.parent)
        if cand_meta.get("error") and cand_meta.get("error_kind") == "infra":
            return True
    return False


def _reusable(meta: RunMeta, key: tuple[str, str], workdir: Path) -> bool:
    """A finished step: recorded result, no active error, every candidate's GLB on disk and
    no candidate that failed for an infrastructure reason (those are retried on resume;
    candidates that failed on the provider's side are not)."""
    previous = meta.result_for(key)
    if previous is None or meta.has_active_error(key):
        return False
    if not all(Path(c["glb_path"]).is_file() for c in previous.get("candidates", [])):
        return False
    return not _has_infra_candidate_error(workdir)


ScaleToleranceOption = Annotated[
    float | None,
    typer.Option(
        help="Tolerancia de escala (error relativo por eje para «escala» 5 y apto), p. ej. "
        "0.05; por defecto SCALE_TOLERANCE de .env o 0.03",
    ),
]


def _resolve_tolerance(value: float | None) -> float:
    """``--scale-tolerance`` (or ``SCALE_TOLERANCE`` from ``.env``) validated, as a float."""
    try:
        return resolve_scale_tolerance(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--scale-tolerance") from exc


def _select_pieces(pieces: list[Piece], spec: str) -> list[Piece]:
    if spec.strip().lower() == "all":
        return pieces
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    by_id = {p.id: p for p in pieces}
    unknown = [w for w in wanted if w not in by_id]
    if unknown:
        raise typer.BadParameter(f"Piezas desconocidas: {', '.join(unknown)}")
    return [by_id[w] for w in wanted]


@app.command()
def run(
    variants: Annotated[str, typer.Option(help="Variantes separadas por comas, p. ej. A,B")],
    pieces: Annotated[str, typer.Option(help="'all' o ids separados por comas")] = "all",
    candidates: Annotated[int, typer.Option(min=1, help="Candidatos por pieza y variante")] = 2,
    run_id: Annotated[str | None, typer.Option(help="Id de la ejecución")] = None,
    sample: Annotated[Path, typer.Option(help="CSV de la muestra")] = DEFAULT_SAMPLE_CSV,
    runs_root: Annotated[Path, typer.Option(help="Carpeta raíz de salidas")] = storage.RUNS_ROOT,
    post: Annotated[
        bool,
        typer.Option(
            "--post/--no-post",
            help="Postprocesado Blender idéntico para todos los candidatos (model_post.glb)",
        ),
    ] = True,
    fit_box: Annotated[
        bool,
        typer.Option(
            "--fit-box/--no-fit-box",
            help="En el postprocesado, ajusta la caja a las medidas exactas si el error de la "
            "escala uniforme cabe en --fit-guard en los tres ejes (el error previo se conserva)",
        ),
    ] = False,
    fit_guard: Annotated[
        float,
        typer.Option(min=0.0, help="Error relativo máximo por eje para --fit-box"),
    ] = DEFAULT_FIT_GUARD,
    resume: Annotated[
        bool,
        typer.Option(
            "--resume/--no-resume",
            help="Con un --run-id existente, reutiliza los pasos (pieza, variante) terminados",
        ),
    ] = True,
    skip_preflight: Annotated[
        bool,
        typer.Option(
            "--skip-preflight",
            help="No abortar si faltan claves o Blender (los pasos afectados fallarán como "
            "infraestructura)",
        ),
    ] = False,
    scale_tolerance: ScaleToleranceOption = None,
    router_classifier: Annotated[
        str,
        typer.Option(
            help="Variante F: cómo decide la ruta. auto = VLM si hay ANTHROPIC_API_KEY, si no "
            "reglas; vlm = siempre el VLM (exige la clave); rules = solo la etiqueta "
            "rectilinear del CSV (sin coste)",
        ),
    ] = "auto",
    organic_variant: Annotated[
        str | None,
        typer.Option(
            help="Variante F: variante registrada para las piezas orgánicas en lugar de C/B "
            "(p. ej. D)",
        ),
    ] = None,
) -> None:
    """Ejecuta las variantes sobre las piezas y escribe meta.json por candidato y por run."""
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    tolerance = _resolve_tolerance(scale_tolerance)
    if router_classifier not in ROUTER_CLASSIFIERS:
        raise typer.BadParameter(
            f"{router_classifier!r}; válidos: {', '.join(ROUTER_CLASSIFIERS)}",
            param_hint="--router-classifier",
        )
    if organic_variant is not None:
        organic_variant = organic_variant.strip().upper()
    selected = _select_pieces(load_pieces(sample), pieces)
    if not selected:
        console.print(f"[red]No hay piezas en {sample}.[/red]")
        raise typer.Exit(1)
    router_options: dict[str, Any] = {}
    if router_classifier != "auto":
        router_options["classifier"] = router_classifier
    if organic_variant is not None:
        router_options["organic_variant"] = organic_variant
    try:
        resolved = [
            get_variant(name, **(router_options if name.strip().upper() == "F" else {}))
            for name in variants.split(",")
            if name.strip()
        ]
    except KeyError as exc:
        raise typer.BadParameter(str(exc.args[0])) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--organic-variant") from exc

    problems, warnings = preflight(
        [v.name for v in resolved],
        post,
        Settings.load(),
        router_classifier=router_classifier,
        organic_variant=organic_variant,
    )
    for warning in warnings:
        console.print(f"[yellow]Aviso:[/yellow] {warning}")
    if problems:
        console.print("[bold]Comprobación previa (antes de cualquier llamada de pago):[/bold]")
        for problem in problems:
            console.print(f"  [red]✗[/red] {problem}")
        if not skip_preflight:
            console.print(
                "Abortado: corrige la configuración (.env) o usa --skip-preflight para "
                "continuar de todos modos."
            )
            raise typer.Exit(PREFLIGHT_EXIT_CODE)
        console.print("[yellow]--skip-preflight: se continúa pese a los problemas.[/yellow]")

    post_step = _PostStep(post, fit_box=fit_box, fit_guard=fit_guard, tolerance=tolerance)
    run_meta = RunMeta(storage.run_dir(run_id, runs_root), run_id, candidates)
    run_meta.declare([v.name for v in resolved], [p.id for p in selected])
    executed = reused = failed = 0
    for piece in selected:
        for variant in resolved:
            console.print(f"[bold]{piece.id}[/bold] · variante {variant.name}")
            workdir = storage.variant_dir(run_id, piece.id, variant.name, runs_root)
            if resume and _reusable(run_meta, (piece.id, variant.name), workdir):
                console.print("  reutilizado (ya terminado en este run)")
                reused += 1
                continue
            try:
                result = variant.run(piece, workdir, candidates)
            except Exception as exc:  # one failing piece/variant must not stop the run
                kind = error_kind(exc)
                console.print(f"  [red]error ({kind}):[/red] {exc}")
                run_meta.record_error(piece.id, variant.name, exc)
                failed += 1
                continue
            if is_not_applicable(result):
                console.print(f"  {result.notes}")
            for cand in result.candidates:
                cand_dir = storage.candidate_dir(workdir, cand.index)
                meta = storage.read_meta(cand_dir)
                meta.update(
                    piece_id=piece.id, variant=result.variant, **cand.model_dump(mode="json")
                )
                post_info = post_step(cand_dir, piece)
                if post_info is not None:
                    meta["post"] = post_info
                storage.write_meta(cand_dir, meta)
            run_meta.record_result(result, sum(c.cost_usd for c in result.candidates))
            executed += 1

    total = float(run_meta.data["total_cost_usd"])
    console.print(
        f"Run [bold]{run_id}[/bold]: {executed} ejecutados, {reused} reutilizados, "
        f"{failed} errores; coste acumulado {_usd(total)}"
    )


def _eval_module():
    try:
        import harness.eval as eval_module
    except ModuleNotFoundError as exc:
        if exc.name != "harness.eval":
            raise
        console.print(
            "[red]El módulo de evaluación (harness.eval) aún no existe; "
            "se implementa en la Tarea 6.[/red]"
        )
        raise typer.Exit(1) from None
    return eval_module


@app.command("eval")
def eval_(
    run_id: Annotated[str, typer.Option(help="Id de la ejecución")],
    runs_root: Annotated[Path, typer.Option(help="Carpeta raíz de salidas")] = storage.RUNS_ROOT,
    sample: Annotated[Path, typer.Option(help="CSV de la muestra")] = DEFAULT_SAMPLE_CSV,
    render: Annotated[
        bool,
        typer.Option(
            "--render/--no-render",
            help="Renderizar con Blender; --no-render reutiliza los renders ya existentes",
        ),
    ] = True,
    scale_tolerance: ScaleToleranceOption = None,
) -> None:
    """Evalúa una ejecución (geometría, renders, juez VLM, hoja ciega)."""
    tolerance = _resolve_tolerance(scale_tolerance)
    _eval_module().evaluate_run(
        run_id, runs_root=runs_root, sample=sample, render=render, tolerance=tolerance
    )


def _split_paths(values: list[Path] | None) -> list[Path]:
    """``--sheets a.csv --sheets b.csv`` and ``--sheets a.csv,b.csv`` are equivalent."""
    out: list[Path] = []
    for value in values or []:
        out += [Path(part.strip()) for part in str(value).split(",") if part.strip()]
    return out


@app.command()
def report(
    run_id: Annotated[str, typer.Option(help="Id de la ejecución")],
    runs_root: Annotated[Path, typer.Option(help="Carpeta raíz de salidas")] = storage.RUNS_ROOT,
    sheets: Annotated[
        list[Path] | None,
        typer.Option(
            help="Hojas ciegas rellenadas por jueces humanos (CSV; el nombre del archivo es el "
            "del juez). Repetible o separadas por comas: --sheets ana.csv,luis.csv",
        ),
    ] = None,
) -> None:
    """Genera el informe de una ejecución evaluada (y la sección de jueces humanos)."""
    eval_module = _eval_module()
    try:
        eval_module.build_report(run_id, runs_root=runs_root, sheets=_split_paths(sheets) or None)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]No se pudo generar el informe:[/red] {exc}")
        raise typer.Exit(1) from None


# --- photo requirements ----------------------------------------------------------------------

REQUIREMENTS_EPILOG = "Requisitos de la foto: " + " · ".join(PHOTO_REQUIREMENTS)


@app.command(epilog=REQUIREMENTS_EPILOG)
def requisitos() -> None:
    """Muestra los requisitos de la foto de entrada."""
    console.print("[bold]Requisitos de la foto:[/bold]")
    for req in PHOTO_REQUIREMENTS:
        console.print(f"  · {req}")


def _photo_problems(photo: Path) -> list[str]:
    """``validate_input`` issues; an unreadable file becomes a problem, not a traceback."""
    from PIL import Image, UnidentifiedImageError

    from harness.prep.clean import validate_input

    if not photo.is_file():
        return [f"No existe el archivo {photo}"]
    try:
        return validate_input(photo)
    except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
        return [f"La imagen no se puede leer (formato no admitido o archivo dañado): {exc}"]
    except (OSError, ValueError, SyntaxError) as exc:  # truncated/corrupt data inside Pillow
        return [f"La imagen no se puede leer (archivo dañado): {exc}"]


@app.command(epilog=REQUIREMENTS_EPILOG)
def validar(
    fotos: Annotated[
        list[Path] | None, typer.Argument(help="Fotos a comprobar (además de --pieces)")
    ] = None,
    pieces: Annotated[
        str | None, typer.Option(help="'all' o ids: comprueba las fotos de esas piezas")
    ] = None,
    sample: Annotated[Path, typer.Option(help="CSV de la muestra")] = DEFAULT_SAMPLE_CSV,
) -> None:
    """Comprueba que las fotos cumplen los requisitos de entrada (sale con 1 si alguna no)."""
    photos = list(fotos or [])
    if pieces:
        selected = _select_pieces(load_pieces(sample), pieces)
        photos += [Path(img) for p in selected for img in p.images]
    if not photos:
        raise typer.BadParameter("indica fotos o --pieces")
    from harness.prep.requirements import explain

    bad = 0
    for photo in photos:
        problems = _photo_problems(photo)
        if problems:
            bad += 1
            console.print(f"[red]✗[/red] {photo}")
            console.print(explain(problems), markup=False)
        else:
            console.print(f"[green]✓[/green] {photo}")
    console.print(f"{len(photos) - bad}/{len(photos)} fotos cumplen los requisitos")
    if bad:
        raise typer.Exit(1)


# --- deliver ---------------------------------------------------------------------------------


class _UserError(Exception):
    """A problem with the user's arguments or data, printed without a traceback."""


def _candidate_indices(workdir: Path, needs: str | None = None) -> list[int]:
    indices = []
    for cand in workdir.glob("cand_*"):
        suffix = cand.name.removeprefix("cand_")
        if cand.is_dir() and suffix.isdigit() and (needs is None or (cand / needs).is_file()):
            indices.append(int(suffix))
    return sorted(indices)


def _pick_candidate(
    run_root: Path, piece_id: str, variant: str | None, candidate: int | None
) -> tuple[str, int, Path]:
    """``(variant, candidate, cand_dir)`` to deliver; ambiguity is an error, never a guess."""
    needs = storage.model_post_path(Path()).name
    piece_dir = run_root / piece_id
    if not piece_dir.is_dir():
        raise _UserError(f"{piece_id}: no hay resultados en {run_root}")
    if variant is None:
        options = sorted(
            d.name for d in piece_dir.iterdir() if d.is_dir() and _candidate_indices(d, needs)
        )
        if len(options) != 1:
            listed = ", ".join(options) or "ninguna"
            raise _UserError(f"{piece_id}: indica --variant (variantes con {needs}: {listed})")
        variant = options[0]
    workdir = piece_dir / variant
    if candidate is None:
        options_idx = _candidate_indices(workdir, needs)
        if len(options_idx) != 1:
            listed = ", ".join(map(str, options_idx)) or "ninguno"
            raise _UserError(
                f"{piece_id}/{variant}: indica --candidate (candidatos con {needs}: {listed})"
            )
        candidate = options_idx[0]
    cand_dir = storage.candidate_dir(workdir, candidate)
    if not storage.model_post_path(cand_dir).is_file():
        raise _UserError(f"{piece_id}/{variant}: no existe {storage.model_post_path(cand_dir)}")
    return variant, candidate, cand_dir


def _mb(n_bytes: int | None) -> str:
    return "—" if n_bytes is None else f"{n_bytes / 1_000_000:.2f} MB".replace(".", ",")


def _int_es(value: int) -> str:
    return f"{value:,}".replace(",", ".")


@app.command("deliver")
def deliver_cmd(
    run_id: Annotated[str, typer.Option(help="Id de la ejecución")],
    pieces: Annotated[str, typer.Option(help="Ids separados por comas, p. ej. p05,p15")],
    variant: Annotated[
        str | None, typer.Option(help="Variante; obligatoria si la pieza tiene varias")
    ] = None,
    candidate: Annotated[
        int | None, typer.Option(min=1, help="Candidato; obligatorio si hay varios")
    ] = None,
    max_tris: Annotated[int, typer.Option(min=1, help="Triángulos máximos del GLB web")] = 60_000,
    max_tex: Annotated[int, typer.Option(min=1, help="Lado máximo de las texturas (px)")] = 2048,
    size_limit: Annotated[
        int, typer.Option(min=1, help="Tamaño máximo del GLB web en bytes")
    ] = 5_000_000,
    out_dir: Annotated[
        Path | None,
        typer.Option(help="Carpeta de salida (una subcarpeta por pieza); por defecto el candidato"),
    ] = None,
    runs_root: Annotated[Path, typer.Option(help="Carpeta raíz de salidas")] = storage.RUNS_ROOT,
    sample: Annotated[Path, typer.Option(help="CSV de la muestra")] = DEFAULT_SAMPLE_CSV,
) -> None:
    """Entrega web: GLB ligero (Draco), USDZ para RA en iPhone y viewer.html por pieza."""
    from harness.post import deliver as post_deliver

    run_root = storage.run_dir(run_id, runs_root)
    selected = _select_pieces(load_pieces(sample), pieces)
    failures = over = 0
    viewer_dirs: list[Path] = []
    for piece in selected:
        try:
            var, cand, cand_dir = _pick_candidate(run_root, piece.id, variant, candidate)
        except _UserError as exc:
            console.print(f"[red]✗[/red] {exc}")
            failures += 1
            continue
        console.print(f"[bold]{piece.id}[/bold] · {var}/cand_{cand}")
        target = out_dir / piece.id if out_dir is not None else None
        try:
            result = post_deliver.deliver(
                cand_dir,
                piece,
                max_tris=max_tris,
                max_tex=max_tex,
                size_limit_bytes=size_limit,
                out_dir=target,
            )
        except BlenderNotAvailable as exc:
            console.print(f"[red]La entrega necesita Blender:[/red] {exc}")
            raise typer.Exit(PREFLIGHT_EXIT_CODE) from None
        except (post_deliver.BlenderDeliverError, FileNotFoundError, OSError) as exc:
            console.print(f"  [red]error:[/red] {exc}", markup=False)
            failures += 1
            continue
        except subprocess.TimeoutExpired as exc:
            console.print(f"  [red]timeout de Blender ({exc.timeout} s)[/red]")
            failures += 1
            continue
        status = (
            "[green]dentro del límite[/green]"
            if result.within_limit
            else f"[red]SUPERA el límite de {_mb(result.size_limit_bytes)}[/red]"
        )
        retry = " (con reintento)" if result.retried else ""
        console.print(f"  GLB web: {_mb(result.glb_bytes)} · {status}{retry}")
        usdz = _mb(result.usdz_bytes) if result.usdz_path else f"no generado ({result.usdz_error})"
        console.print(f"  USDZ: {usdz}")
        console.print(f"  Triángulos: {_int_es(result.tris_before)} → {_int_es(result.tris_after)}")
        console.print(f"  Visor: {result.viewer_path}")
        viewer_dirs.append(result.out_dir)
        over += not result.within_limit
    if viewer_dirs:
        served = out_dir if out_dir is not None else viewer_dirs[0]
        page = (viewer_dirs[0] / post_deliver.VIEWER_FILENAME).relative_to(served).as_posix()
        console.print(
            f"Para verlo: python -m http.server 8000 --directory {served} y abre "
            f"http://localhost:8000/{page} (la RA en el móvil necesita HTTPS)"
        )
    if failures or over:
        raise typer.Exit(1)


# --- refine ----------------------------------------------------------------------------------


def _refine_targets(
    run_root: Path, piece_ids: list[str] | None, variant: str | None, candidate: int | None
) -> list[tuple[str, str, int]]:
    targets = []
    for meta_file in run_root.glob("*/*/cand_*/meta.json"):
        cand_dir = meta_file.parent
        piece_id, var = cand_dir.parent.parent.name, cand_dir.parent.name
        suffix = cand_dir.name.removeprefix("cand_")
        if piece_id == "eval" or not suffix.isdigit():
            continue
        if piece_ids is not None and piece_id not in piece_ids:
            continue
        if variant is not None and var != variant:
            continue
        if candidate is not None and int(suffix) != candidate:
            continue
        targets.append((piece_id, var, int(suffix)))
    return sorted(targets)


STEP_STATUS = {"ok": "hecho", "failed": "fallido", "skipped": "omitido"}


def _action_label(kind: str) -> str:
    return {
        "fit_box": "ajuste a la caja (gratis)",
        "regenerate": "regenerar (de pago)",
        "retexture": "retexturizar (de pago)",
    }.get(kind, kind)


@app.command()
def refine(
    run_id: Annotated[str, typer.Option(help="Id de la ejecución")],
    piece: Annotated[str, typer.Option(help="Pieza o piezas separadas por comas, o 'all'")],
    variant: Annotated[str | None, typer.Option(help="Solo esta variante")] = None,
    candidate: Annotated[int | None, typer.Option(min=1, help="Solo este candidato")] = None,
    max_rounds: Annotated[
        int,
        typer.Option(
            min=0, help="Acciones de pago como máximo por candidato (0 = solo las gratuitas)"
        ),
    ] = 2,
    retexture: Annotated[
        bool,
        typer.Option("--retexture/--no-retexture", help="Permite retexturizar con Meshy"),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Solo diagnostica y muestra el plan; no aplica nada"),
    ] = False,
    fit_guard: Annotated[
        float, typer.Option(min=0.0, help="Error relativo máximo por eje para el ajuste a la caja")
    ] = DEFAULT_FIT_GUARD,
    scale_tolerance: ScaleToleranceOption = None,
    runs_root: Annotated[Path, typer.Option(help="Carpeta raíz de salidas")] = storage.RUNS_ROOT,
    sample: Annotated[Path, typer.Option(help="CSV de la muestra")] = DEFAULT_SAMPLE_CSV,
) -> None:
    """Diagnostica y corrige candidatos (escala, geometría, material); 2 si falta una clave.

    Escala → ajuste a la caja (gratis); geometría → regenerar (de pago); material →
    retexturizar con Meshy (de pago). Sale con 2, antes de tocar nada, si una acción de pago
    dentro de --max-rounds necesita una clave que no está en .env.
    """
    from harness.refine import RefineProviders, load_scores_row, refine_candidate
    from harness.refine.actions import regenerations_in_workdir
    from harness.refine.rules import MAX_EXTRA_CANDIDATES, diagnose, plan

    tolerance = _resolve_tolerance(scale_tolerance)
    run_root = storage.run_dir(run_id, runs_root)
    if not run_root.is_dir():
        console.print(f"[red]No existe la ejecución {run_root}[/red]")
        raise typer.Exit(1)
    piece_ids = None if piece.strip().lower() == "all" else [p.strip() for p in piece.split(",")]
    targets = _refine_targets(run_root, piece_ids, variant, candidate)
    if not targets:
        console.print("[red]Ningún candidato coincide con --piece/--variant/--candidate.[/red]")
        raise typer.Exit(1)

    settings = Settings.load()
    registered = set(available_variants())
    problems: list[str] = []
    for piece_id, var, idx in targets:
        workdir = storage.variant_dir(run_id, piece_id, var, runs_root)
        meta = storage.read_meta(storage.candidate_dir(workdir, idx))
        row = load_scores_row(run_id, piece_id, var, idx, root=runs_root)
        issues = diagnose(meta, row, tolerance=tolerance, guard=fit_guard)
        common = {
            "regenerations_done": regenerations_in_workdir(workdir),
            "max_regenerations": MAX_EXTRA_CANDIDATES,
            "can_retexture": retexture,
        }
        allowed = plan(issues, paid_budget=max_rounds, **common)
        needed = plan(issues, paid_budget=None, **common)
        console.print(f"[bold]{piece_id}[/bold] · {var}/cand_{idx}")
        if not issues:
            console.print("  sin problemas detectados")
        for issue in issues:
            console.print(f"  problema ({issue.kind}): {issue.detail}", markup=False)
        allowed_kinds = [a.kind for a in allowed]
        for action in needed:
            note = ""
            if action.kind not in allowed_kinds:
                note = " — fuera de --max-rounds"
            elif action.kind == "regenerate" and var.upper() not in registered:
                note = " — no regenerable: variante importada (se omitirá)"
            elif action.kind == "regenerate":
                missing = ", ".join(missing_keys(variant_keys(var.upper()), settings))
                if missing:
                    note = f" — falta {missing}"
                    problems.append(f"{piece_id}/{var}/cand_{idx}: regenerar necesita {missing}")
            elif action.kind == "retexture" and not settings.meshy_api_key:
                note = " — falta MESHY_API_KEY"
                problems.append(f"{piece_id}/{var}/cand_{idx}: retexturizar necesita MESHY_API_KEY")
            console.print(f"  plan: {_action_label(action.kind)}{note}", markup=False)

    if dry_run:
        console.print("--dry-run: no se ha aplicado nada.")
        return
    if problems:
        console.print("[bold]Comprobación previa (antes de cualquier acción de pago):[/bold]")
        for problem in problems:
            console.print(f"  [red]✗[/red] {problem}")
        console.print(
            "Abortado: añade la clave a .env, usa --max-rounds 0 (solo acciones gratuitas) "
            "o --no-retexture."
        )
        raise typer.Exit(PREFLIGHT_EXIT_CODE)

    providers = RefineProviders.from_settings(settings)
    if not retexture:
        providers.retexturer = None
    total_cost = 0.0
    total_paid = failed = 0
    for piece_id, var, idx in targets:
        console.print(f"[bold]{piece_id}[/bold] · {var}/cand_{idx}: refinando")
        try:
            rep = refine_candidate(
                run_id,
                piece_id,
                var,
                idx,
                max_rounds=max_rounds,
                providers=providers,
                pieces_csv=sample,
                root=runs_root,
                tolerance=tolerance,
                fit_guard=fit_guard,
            )
        except (FileNotFoundError, KeyError) as exc:
            console.print(f"  [red]error:[/red] {exc}", markup=False)
            failed += 1
            continue
        for step in rep.steps:
            extra = f" → cand_{step['new_candidate']}" if step.get("new_candidate") else ""
            cost = f" · {_usd(float(step['cost_usd']))}" if step.get("cost_usd") else ""
            detail = f": {step['detail']}" if step.get("detail") else ""
            console.print(
                f"  {_action_label(step['action'])} en cand_{step['candidate']}: "
                f"{STEP_STATUS.get(step['status'], step['status'])}{extra}{cost}{detail}",
                markup=False,
            )
            failed += step["status"] == "failed"
        if not rep.steps:
            console.print("  ninguna acción aplicable")
        after = "; ".join(i.detail for i in rep.issues_after) or "sin problemas"
        console.print(f"  resultado (cand_{rep.final_candidate}): {after}", markup=False)
        for warning in rep.warnings:
            console.print(f"  [yellow]aviso:[/yellow] {warning}", markup=False)
        total_cost += rep.cost_usd
        total_paid += rep.paid_actions
    if total_cost:
        _add_refine_cost(run_root, total_cost)
    console.print(
        f"Refinado: {len(targets)} candidato(s), {total_paid} acción(es) de pago, "
        f"coste {_usd(total_cost)}"
    )
    if failed:
        raise typer.Exit(1)


def _add_refine_cost(run_root: Path, cost: float) -> None:
    """Refinement spend goes into the run's ``total_cost_usd`` (and ``refine_cost_usd``)."""
    data = storage.read_meta(run_root)
    if not data:
        return
    data["refine_cost_usd"] = float(data.get("refine_cost_usd") or 0.0) + cost
    data["total_cost_usd"] = float(data.get("total_cost_usd") or 0.0) + cost
    data["updated_at"] = datetime.now(UTC).isoformat()
    storage.write_meta(run_root, data)


if __name__ == "__main__":
    app()
