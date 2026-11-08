"""Evaluation of a run: geometry, control renders, VLM judge, blind sheet and report.

``evaluate_run(run_id)`` and ``build_report(run_id)`` are what ``harness.cli`` calls.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.config import Settings, resolve_scale_tolerance
from harness.core.models import DEFAULT_SAMPLE_CSV, Piece, load_pieces
from harness.eval.blind_sheet import (
    DEFAULT_SEED,
    CandidateRef,
    assign_blind_ids,
    copy_blind_renders,
    write_blind_sheet,
)
from harness.eval.geometry import fit_info, measure_candidate, model_for_candidate
from harness.eval.judge import JSONAsker, judge_candidate
from harness.eval.render import RenderError, existing_renders, render_views
from harness.eval.report import read_scores, render_markdown, summarize
from harness.eval.sheets import build_human_summary, load_sheets

__all__ = ["evaluate_run", "build_report"]

console = Console()


def _discover_candidates(run_root: Path) -> dict[CandidateRef, tuple[Path, dict[str, Any]]]:
    found: dict[CandidateRef, tuple[Path, dict[str, Any]]] = {}
    for meta_file in sorted(run_root.glob("*/*/cand_*/meta.json")):
        cand_dir = meta_file.parent
        if cand_dir.parent.parent.name == "eval":
            continue
        meta = storage.read_meta(cand_dir)
        ref = CandidateRef(
            piece_id=str(meta.get("piece_id") or cand_dir.parent.parent.name),
            variant=str(meta.get("variant") or cand_dir.parent.name),
            candidate=int(meta.get("index") or cand_dir.name.removeprefix("cand_")),
        )
        found[ref] = (cand_dir, meta)
    return found


def _run_meta_record(
    entry: dict[str, Any], by_id: dict[str, Piece], status: str, kind: str, reason: str
) -> dict[str, Any]:
    """Piece-level record for a (piece, variant) step that produced no candidate."""
    piece = by_id.get(entry.get("piece_id", ""))
    return {
        "blind_id": None,
        "piece_id": entry.get("piece_id"),
        "variant": entry.get("variant"),
        "candidate": None,
        "category": piece.category if piece else None,
        "status": status,
        "error_kind": kind,
        "from_run_meta": True,
        "reasons": [reason],
        "geometry": None,
        "scores": None,
        "cost_usd": 0.0,
        "seconds": 0.0,
        "router_cost_usd": 0.0,
        "judge_cost_usd": 0.0,
        "judge_model": None,
    }


def _failed_candidate_record(
    ref: CandidateRef, meta: dict[str, Any], by_id: dict[str, Piece]
) -> dict[str, Any]:
    """Record for a candidate whose generation failed (its ``meta.json`` carries ``error``).

    No GLB is loaded and it gets no blind id. ``error_kind == "infra"`` (network, missing
    key...) → ``unscored``, outside the denominator; ``"candidate"`` or missing (provider
    task failed) → ``candidate_failed``, counts as not apt.
    """
    piece = by_id.get(ref.piece_id)
    kind = "infra" if meta.get("error_kind") == "infra" else "candidate"
    return {
        "blind_id": None,
        "piece_id": ref.piece_id,
        "variant": ref.variant,
        "candidate": ref.candidate,
        "category": piece.category if piece else None,
        "status": "unscored" if kind == "infra" else "candidate_failed",
        "error_kind": kind,
        "generation_error": True,
        "reasons": [f"generación fallida ({kind}): {meta.get('error')}"],
        "glb_path": None,
        "geometry": None,
        "scores": None,
        "cost_usd": float(meta.get("cost_usd") or 0.0),
        "seconds": float(meta.get("seconds") or 0.0),
        "router_cost_usd": float(meta.get("router_cost_usd_share") or 0.0),
        "judge_cost_usd": 0.0,
        "judge_model": None,
    }


def _default_judge() -> tuple[JSONAsker | None, str | None]:
    key = Settings.load().anthropic_api_key
    if not key:
        return None, "juez VLM omitido: ANTHROPIC_API_KEY no definido"
    from harness.clients.vlm import VLMClient

    # No server-side fallback: every score must come from the requested judge model.
    return VLMClient(api_key=key, allow_fallback=False), None


def evaluate_run(
    run_id: str,
    *,
    runs_root: Path = storage.RUNS_ROOT,
    judge: JSONAsker | None = None,
    render: bool = True,
    pieces: list[Piece] | None = None,
    sample: Path = DEFAULT_SAMPLE_CSV,
    seed: int = DEFAULT_SEED,
    blender_bin: Path | None = None,
    tolerance: float | None = None,
) -> Path:
    """Evaluate every candidate of a run; writes ``scores.jsonl`` and the blind sheet.

    ``tolerance`` is the scale tolerance (None → ``SCALE_TOLERANCE`` from ``.env``, 3 % by
    default); the value in effect is recorded in every ``scores.jsonl`` record.

    ``render=False`` skips Blender and reuses renders already on disk, if complete.
    ``judge=None`` builds a ``VLMClient`` from ``ANTHROPIC_API_KEY`` (judging is skipped,
    with the reason recorded, when there is no key). Returns the ``scores.jsonl`` path.
    """
    run_root = Path(runs_root) / run_id
    if not run_root.is_dir():
        raise FileNotFoundError(f"No existe la ejecución {run_root}")
    by_id = {p.id: p for p in (pieces if pieces is not None else load_pieces(sample))}
    tolerance = resolve_scale_tolerance(tolerance)
    judge_skip: str | None = None
    if judge is None:
        judge, judge_skip = _default_judge()

    eval_dir = storage.eval_dir(run_id, runs_root)
    candidates = _discover_candidates(run_root)
    records: list[dict[str, Any]] = []
    for ref, (_cand_dir, meta) in candidates.items():
        if meta.get("error"):
            records.append(_failed_candidate_record(ref, meta, by_id))
            console.print(f"{ref.piece_id}/{ref.variant}/cand_{ref.candidate}: generación fallida")
    candidates = {ref: v for ref, v in candidates.items() if not v[1].get("error")}
    sheet_entries: list[tuple[str, CandidateRef, list[Path], list[Path]]] = []
    blender_missing: str | None = None

    for blind_id, ref in assign_blind_ids(list(candidates), seed):
        cand_dir, meta = candidates[ref]
        piece = by_id.get(ref.piece_id)
        reasons: list[str] = []
        glb = model_for_candidate(cand_dir)
        record: dict[str, Any] = {
            "blind_id": blind_id,
            "piece_id": ref.piece_id,
            "variant": ref.variant,
            "candidate": ref.candidate,
            "category": piece.category if piece else None,
            "glb_path": str(glb),
            "cost_usd": float(meta.get("cost_usd") or 0.0),
            "seconds": float(meta.get("seconds") or 0.0),
            "router_cost_usd": float(meta.get("router_cost_usd_share") or 0.0),
            "geometry": None,
            "scores": None,
            "judge_cost_usd": 0.0,
            "judge_model": None,
        }

        geometry = None
        candidate_error: str | None = None
        if piece is None:
            reasons.append(f"pieza {ref.piece_id} no está en la muestra")
        else:
            geo = measure_candidate(glb, piece)
            geometry, candidate_error = geo.metrics, geo.error
            if geometry is not None:
                record["geometry"] = {
                    **geometry.model_dump(),
                    "max_error": geometry.max_error,
                    "scale_ok": geometry.is_scale_ok(tolerance),
                    "source": geo.source,
                    "raw_extents_cm": list(geo.raw_extents_cm) if geo.raw_extents_cm else None,
                    "scale_factor": geo.scale_factor,
                }
            else:
                reasons.append(f"sin geometría: {candidate_error}")
        fit = fit_info(glb, meta)
        if fit is not None:  # measured geometry is post-fit; keep the pre-fit error visible
            record["fit_box_applied"] = fit["fit_box_applied"]
            record["errors_before_fit"] = fit["errors_before_fit"]

        renders: list[Path] | None = None
        out_dir = storage.renders_dir(cand_dir)
        if not render:
            renders = existing_renders(out_dir)
            if renders is None:
                reasons.append("render desactivado y sin renders previos")
        elif blender_missing:
            reasons.append(f"render omitido: {blender_missing}")
        elif glb.is_file():
            try:
                renders = render_views(glb, out_dir, blender_bin=blender_bin)
            except BlenderNotAvailable as exc:
                blender_missing = str(exc)
                reasons.append(f"render omitido: {exc}")
            except (RenderError, subprocess.TimeoutExpired) as exc:
                reasons.append(f"render fallido: {exc}")
        else:
            reasons.append(f"render omitido: no existe el modelo {glb.name}")
        blind_renders = copy_blind_renders(renders, eval_dir, blind_id) if renders else []
        photos = [p for p in piece.images if Path(p).is_file()] if piece else []
        sheet_entries.append((blind_id, ref, photos, blind_renders))

        # The judge runs for every candidate with renders, even without geometry.
        if judge is None:
            reasons.append(judge_skip or "juez VLM no disponible")
        elif not blind_renders:
            pass  # nothing to show the judge; the render reason is already recorded
        elif not photos:
            reasons.append("juez VLM omitido: no hay fotos originales")
        else:
            cost_before = float(getattr(judge, "total_cost_usd", 0.0) or 0.0)
            try:
                record["scores"] = judge_candidate(
                    judge,
                    blind_id=blind_id,
                    photos=photos,
                    renders=blind_renders,
                    geometry=geometry,
                    tolerance=tolerance,
                )
                record["judge_model"] = getattr(judge, "last_model", None)
            except Exception as exc:  # one failed judgement must not stop the run
                reasons.append(f"juez VLM: {exc}")
            cost_after = float(getattr(judge, "total_cost_usd", 0.0) or 0.0)
            record["judge_cost_usd"] = cost_after - cost_before

        # scored: judged. candidate_failed: not judged, but the candidate itself is broken
        # (counts as not apt). unscored: infrastructure skip (excluded from the denominator).
        if record["scores"]:
            record["status"] = "scored"
        elif candidate_error:
            record["status"] = "candidate_failed"
        else:
            record["status"] = "unscored"
        record["reasons"] = reasons
        records.append(record)
        console.print(f"{blind_id}: {record['status']}")

    run_meta = storage.read_meta(run_root)
    for error in run_meta.get("errors", []):
        if error.get("superseded"):
            continue  # a later attempt of the same (piece, variant) replaced it
        kind = error.get("kind") or "candidate"
        # infra: missing key, no Blender, network → outside the denominator.
        # candidate: the provider task failed / no GLB → counts as not apt.
        status = "unscored" if kind == "infra" else "generation_failed"
        records.append(_run_meta_record(error, by_id, status, kind, str(error.get("error", ""))))
    for skipped in run_meta.get("skipped", []):
        if skipped.get("kind") == "not_applicable":
            records.append(
                _run_meta_record(
                    skipped, by_id, "not_applicable", "not_applicable", str(skipped.get("reason"))
                )
            )

    for rec in records:
        rec["scale_tolerance"] = tolerance
    scores_file = storage.scores_path(run_id, runs_root)
    scores_file.write_text(
        "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in records),
        encoding="utf-8",
    )
    write_blind_sheet(
        storage.blind_sheet_path(run_id, runs_root),
        storage.blind_key_path(run_id, runs_root),
        sheet_entries,
    )
    scored = sum(r["status"] == "scored" for r in records)
    console.print(f"Evaluados {len(records)} registros ({scored} puntuados) → {scores_file}")
    return scores_file


def build_report(
    run_id: str,
    *,
    runs_root: Path = storage.RUNS_ROOT,
    sheets: list[Path] | None = None,
) -> Path:
    """Write ``report.md`` from ``scores.jsonl``; returns its path.

    ``sheets`` are human judges' copies of ``blind_sheet.csv`` (judge = file name); they are
    joined with ``eval/blind_key.csv`` and added as the «Jueces humanos» section. Raises
    ``ValueError`` (Spanish message) when a sheet cannot be read or does not match the key.
    """
    scores_file = Path(runs_root) / run_id / "eval" / "scores.jsonl"
    if not scores_file.is_file():
        raise FileNotFoundError(f"No existe {scores_file}; ejecuta antes `bakeoff eval`")
    records = read_scores(scores_file)
    human = None
    if sheets:
        key_path = storage.blind_key_path(run_id, runs_root)
        if not key_path.is_file():
            raise FileNotFoundError(f"No existe {key_path}; ejecuta antes `bakeoff eval`")
        missing = [str(p) for p in sheets if not Path(p).is_file()]
        if missing:
            raise FileNotFoundError(f"No existe la hoja: {', '.join(missing)}")
        try:
            judged = load_sheets(key_path, [Path(p) for p in sheets])
        except ValueError as exc:
            if "sin entrada en la clave" not in str(exc):
                raise
            raise ValueError(
                f"{exc}. ¿Es una hoja de otra ejecución? Cada juez debe rellenar una copia de "
                f"{storage.blind_sheet_path(run_id, runs_root)}"
            ) from exc
        human = build_human_summary(judged, records)
    summaries = summarize(records)
    tolerances = sorted({float(t) for r in records if (t := r.get("scale_tolerance")) is not None})
    path = storage.report_path(run_id, runs_root)
    path.write_text(
        render_markdown(run_id, summaries, human=human, scale_tolerances=tolerances),
        encoding="utf-8",
    )
    console.print(f"Informe → {path}")
    return path
