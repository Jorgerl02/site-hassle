"""``bakeoff`` command line: run variants, evaluate and report."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.config import Settings
from harness.core.errors import error_kind
from harness.core.models import DEFAULT_SAMPLE_CSV, Piece, VariantResult, load_pieces
from harness.core.registry import get_variant
from harness.core.variant import is_not_applicable
from harness.post.blender_post import BlenderPostError, postprocess

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
    # F: router VLM + its organic routes (B: Tripo; C: Tripo + Gemini).
    "F": ("anthropic_api_key", "tripo_api_key", "gemini_api_key"),
}
VARIANTS_NEEDING_BLENDER = frozenset({"E"})
# F routes rectilinear pieces to E but falls back to the organic route without Blender.
VARIANTS_PREFERRING_BLENDER = frozenset({"F"})

app = typer.Typer(help="Bake-off de pipelines foto→3D.", no_args_is_help=True)
console = Console()


class _PostStep:
    """Identical headless-Blender post-processing for every candidate of every variant.

    After the first ``BlenderNotAvailable`` Blender is not launched again in this run.
    """

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
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
            result = postprocess(glb, storage.model_post_path(cand_dir), piece)
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
        return {
            "ok": True,
            "glb_path": str(result.glb_path),
            "seconds": result.seconds,
            "errors": result.errors,
            "errors_axis": result.errors_axis,
            "scale_factor": result.scale_factor,
            "draco": result.draco,
            "triangles_before": result.tris_before,
            "triangles_after": result.tris_after,
        }


def _blender_ok(settings: Settings) -> bool:
    return settings.blender_bin is not None and Path(settings.blender_bin).is_file()


def preflight(
    variant_names: list[str], post: bool, settings: Settings
) -> tuple[list[str], list[str]]:
    """Return ``(problems, warnings)`` (Spanish) for the requested variants and options."""
    problems: list[str] = []
    warnings: list[str] = []
    for name in variant_names:
        missing = [KEY_ENV[k] for k in VARIANT_KEYS.get(name, ()) if not getattr(settings, k)]
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
) -> None:
    """Ejecuta las variantes sobre las piezas y escribe meta.json por candidato y por run."""
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    selected = _select_pieces(load_pieces(sample), pieces)
    if not selected:
        console.print(f"[red]No hay piezas en {sample}.[/red]")
        raise typer.Exit(1)
    try:
        resolved = [get_variant(name) for name in variants.split(",") if name.strip()]
    except KeyError as exc:
        raise typer.BadParameter(str(exc.args[0])) from exc

    problems, warnings = preflight([v.name for v in resolved], post, Settings.load())
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

    post_step = _PostStep(post)
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
        f"{failed} errores; coste acumulado {total:.2f} USD"
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
) -> None:
    """Evalúa una ejecución (geometría, renders, juez VLM, hoja ciega)."""
    _eval_module().evaluate_run(run_id, runs_root=runs_root, sample=sample, render=render)


@app.command()
def report(
    run_id: Annotated[str, typer.Option(help="Id de la ejecución")],
    runs_root: Annotated[Path, typer.Option(help="Carpeta raíz de salidas")] = storage.RUNS_ROOT,
) -> None:
    """Genera el informe de una ejecución evaluada."""
    _eval_module().build_report(run_id, runs_root=runs_root)


if __name__ == "__main__":
    app()
