"""``bakeoff`` command line: run variants, evaluate, report, refine and deliver."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from typer.core import TyperGroup

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.config import InvalidSettingsError, Settings, resolve_scale_tolerance
from harness.core.errors import error_kind
from harness.core.models import DEFAULT_SAMPLE_CSV, Piece, VariantResult, load_pieces
from harness.core.registry import get_variant
from harness.core.variant import is_not_applicable
from harness.post.blender_post import BlenderPostError, postprocess
from harness.post.bpy_post import DEFAULT_FIT_GUARD

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

SETTINGS_EXIT_CODE = 2

console = Console(soft_wrap=True)  # long paths stay copyable (no hard wraps)
err_console = Console(stderr=True, soft_wrap=True)


class _SettingsAwareGroup(TyperGroup):
    """An invalid ``.env`` value (e.g. ``SCALE_TOLERANCE``) read anywhere under a command
    — CLI code or deep inside the harness — ends with a Spanish message and exit 2, never
    with a traceback."""

    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except InvalidSettingsError as exc:
            err_console.print(f"[red]Configuración inválida (.env):[/red] {exc}", markup=True)
            raise typer.Exit(SETTINGS_EXIT_CODE) from None


app = typer.Typer(
    help="Bake-off de pipelines foto→3D.", no_args_is_help=True, cls=_SettingsAwareGroup
)


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
    except InvalidSettingsError:
        raise  # a bad .env, not a bad flag: handled by the group (exit 2, no traceback)
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
    if router_options and "F" not in {v.name for v in resolved}:
        flags = " y ".join(
            flag
            for flag, key in (
                ("--router-classifier", "classifier"),
                ("--organic-variant", "organic_variant"),
            )
            if key in router_options
        )
        err_console.print(
            f"[yellow]Aviso:[/yellow] {flags} solo afecta a la variante F, que no está en "
            "--variants; se ignora."
        )

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


# --- commands defined in sibling modules ------------------------------------------------------
# Each module registers its commands on ``app`` when imported (order = order in ``--help``).
from harness import cli_deliver, cli_prep, cli_refine  # noqa: E402, F401, I001
from harness.cli_refine import _add_refine_cost  # noqa: E402, F401  (re-exported)


if __name__ == "__main__":
    app()
