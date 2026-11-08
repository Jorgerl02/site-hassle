"""``bakeoff refine``: diagnose and fix candidates (scale, geometry, material)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.markup import escape

from harness.cli import (
    PREFLIGHT_EXIT_CODE,
    ScaleToleranceOption,
    _resolve_tolerance,
    _usd,
    app,
    console,
    missing_keys,
    variant_keys,
)
from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.config import Settings
from harness.core.models import DEFAULT_SAMPLE_CSV
from harness.core.registry import available_variants
from harness.eval.report import format_tolerance
from harness.post.blender_post import BlenderPostError
from harness.post.bpy_post import DEFAULT_FIT_GUARD
from harness.refine.rules import NO_POST_DETAIL

# Failures of one candidate's refinement that are reported without a traceback.
REFINE_ERRORS = (
    FileNotFoundError,
    KeyError,
    BlenderNotAvailable,
    BlenderPostError,
    subprocess.TimeoutExpired,
    httpx.HTTPError,
    ValueError,
)


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


# Issue kinds stay in English in code and refine.json; the user reads them in Spanish.
ISSUE_LABELS = {"scale": "escala", "geometry": "geometría", "material": "material"}
REPOST_LABEL = "re-postprocesado (gratis)"


def _action_label(kind: str, reason: str | None = None) -> str:
    if kind == "fit_box" and reason == NO_POST_DETAIL:
        return REPOST_LABEL  # the free re-post for a candidate without post-processing
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
    from harness.refine.actions import not_regenerable_reason, regenerations_in_workdir
    from harness.refine.rules import MAX_EXTRA_CANDIDATES, diagnose, plan

    if scale_tolerance is not None:
        scale_tolerance = _resolve_tolerance(scale_tolerance)
    run_root = storage.run_dir(run_id, runs_root)
    if not run_root.is_dir():
        console.print(f"[red]No existe la ejecución {run_root}[/red]")
        raise typer.Exit(1)
    if variant is not None:
        variant = variant.strip().upper()  # same convention as `run`
    piece_ids = None if piece.strip().lower() == "all" else [p.strip() for p in piece.split(",")]
    targets = _refine_targets(run_root, piece_ids, variant, candidate)
    if not targets:
        console.print("[red]Ningún candidato coincide con --piece/--variant/--candidate.[/red]")
        raise typer.Exit(1)

    settings = Settings.load()
    registered = set(available_variants())
    problems: list[str] = []
    tolerances: dict[tuple[str, str, int], float] = {}
    for piece_id, var, idx in targets:
        workdir = storage.variant_dir(run_id, piece_id, var, runs_root)
        cand_dir = storage.candidate_dir(workdir, idx)
        try:
            meta = storage.read_meta(cand_dir)
            if not isinstance(meta, dict):
                raise ValueError("no es un objeto JSON")
            row = load_scores_row(run_id, piece_id, var, idx, root=runs_root)
        except (OSError, ValueError) as exc:
            console.print(
                f"[red]{piece_id}/{var}/cand_{idx}: no se puede leer meta.json o "
                f"scores.jsonl ({escape(str(exc))}).[/red] Corrige o elimina el archivo y "
                "vuelve a intentarlo."
            )
            raise typer.Exit(1) from None
        tolerance, source = _candidate_tolerance(scale_tolerance, row)
        tolerances[(piece_id, var, idx)] = tolerance
        issues = diagnose(meta, row, tolerance=tolerance, guard=fit_guard)
        common = {
            "regenerations_done": regenerations_in_workdir(workdir),
            "max_regenerations": MAX_EXTRA_CANDIDATES,
            "can_retexture": retexture,
        }
        allowed = plan(issues, paid_budget=max_rounds, **common)
        needed = plan(issues, paid_budget=None, **common)
        console.print(f"[bold]{piece_id}[/bold] · {var}/cand_{idx}")
        console.print(f"  tolerancia de escala: {format_tolerance(tolerance)} ({source})")
        blocked_regen = not_regenerable_reason(var, meta)
        if not issues:
            console.print("  sin problemas detectados")
        for issue in issues:
            label = ISSUE_LABELS.get(issue.kind, issue.kind)
            console.print(f"  problema ({label}): {issue.detail}", markup=False)
        allowed_kinds = [a.kind for a in allowed]
        for action in needed:
            note = ""
            if action.kind not in allowed_kinds:
                note = " — fuera de --max-rounds"
            elif action.kind == "regenerate" and blocked_regen:
                note = f" — no regenerable: {blocked_regen} (se omitirá, sin coste)"
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
            label = _action_label(action.kind, action.reason)
            console.print(f"  plan: {label}{note}", markup=False)

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
                tolerance=tolerances[(piece_id, var, idx)],
                fit_guard=fit_guard,
            )
        except REFINE_ERRORS as exc:
            console.print(f"  error: {_refine_error_message(exc)}", markup=False)
            failed += 1
            continue
        for step in rep.steps:
            extra = f" → cand_{step['new_candidate']}" if step.get("new_candidate") else ""
            cost = f" · {_usd(float(step['cost_usd']))}" if step.get("cost_usd") else ""
            detail = f": {step['detail']}" if step.get("detail") else ""
            label = _action_label(step["action"], step.get("reason"))
            console.print(
                f"  {label} en cand_{step['candidate']}: "
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
        if rep.cost_usd:  # per candidate: a later failure never loses earlier spend
            _add_refine_cost(run_root, rep.cost_usd)
    console.print(
        f"Refinado: {len(targets)} candidato(s), {total_paid} acción(es) de pago, "
        f"coste {_usd(total_cost)}"
    )
    if failed:
        raise typer.Exit(1)


def _candidate_tolerance(explicit: float | None, row: dict[str, Any] | None) -> tuple[float, str]:
    """``(tolerance, Spanish source)``: --scale-tolerance if given, else the one recorded in
    the candidate's ``scores.jsonl`` row (the one its evaluation used), else ``.env``."""
    if explicit is not None:
        return explicit, "--scale-tolerance"
    recorded = (row or {}).get("scale_tolerance")
    if recorded is not None:
        try:
            value = float(recorded)
        except (TypeError, ValueError):
            value = None
        if value is not None and 0 < value < 1:
            return value, "registrada en scores.jsonl por bakeoff eval"
    return _resolve_tolerance(None), "SCALE_TOLERANCE de .env o 3 % por defecto"


def _refine_error_message(exc: BaseException) -> str:
    """Spanish one-liner for a refinement failure (no traceback)."""
    if isinstance(exc, BlenderNotAvailable):
        return f"sin Blender (BLENDER_BIN): {exc}"
    if isinstance(exc, BlenderPostError):
        return f"falló el postprocesado en Blender: {str(exc).splitlines()[0]}"
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"timeout de Blender ({exc.timeout} s)"
    if isinstance(exc, httpx.HTTPError):
        return f"error de red con el proveedor: {exc}"
    if isinstance(exc, KeyError):
        return str(exc.args[0]) if exc.args else repr(exc)
    return str(exc)


def _add_refine_cost(run_root: Path, cost: float) -> None:
    """Refinement spend goes into the run's ``total_cost_usd`` (and ``refine_cost_usd``)."""
    data = storage.read_meta(run_root)
    if not data:
        return
    data["refine_cost_usd"] = float(data.get("refine_cost_usd") or 0.0) + cost
    data["total_cost_usd"] = float(data.get("total_cost_usd") or 0.0) + cost
    data["updated_at"] = datetime.now(UTC).isoformat()
    storage.write_meta(run_root, data)
