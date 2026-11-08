"""Refinement loop for one candidate: diagnose → plan → apply, one action at a time.

``refine_candidate`` re-diagnoses after every action and applies the first planned action
not yet tried, so the order is always ``fit_box`` (free), ``regenerate`` (paid),
``retexture`` (paid). At most ``max_rounds`` paid actions are attempted per call (a failed
paid attempt counts: the provider may have billed it). The history is appended to
``refine.json`` in the starting candidate's directory.

Regeneration: variants only expose ``run(piece, workdir, candidates=N)``, so to get one more
candidate the variant is run with ``N + 1`` candidates (N = highest existing index) in a
scratch directory next to the candidates and only ``cand_<N+1>`` is moved into the real
workdir. Existing candidates are never overwritten, and seeded variants (Tripo:
seed = index) get a new seed; the price is that API variants bill all ``N + 1`` generations
(acceptable for now; the cost is recorded). Imported variants that are not in the registry
cannot be regenerated (the step is recorded as skipped). Each regeneration counts against
``MAX_EXTRA_CANDIDATES`` across calls (read back from ``refine.json``).

Retexture writes ``model_retex.glb`` next to ``model.glb`` (which is kept) and re-postprocesses
it into ``model_post.glb``. Every re-postprocess uses ``fit_box=True`` and refreshes the
``post`` block of the candidate's ``meta.json`` (the previous one stays in ``refine.json``).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from harness.clients.meshy import GenerationOutcome
from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.models import DEFAULT_SAMPLE_CSV, SCALE_TOLERANCE, Piece, load_pieces
from harness.core.variant import Variant
from harness.post.bpy_post import DEFAULT_FIT_GUARD
from harness.refine.rules import (
    MAX_EXTRA_CANDIDATES,
    Action,
    Issue,
    diagnose,
    plan,
)

__all__ = [
    "REFINE_FILENAME",
    "RefineProviders",
    "RefineReport",
    "Retexturer",
    "diagnose",
    "load_scores_row",
    "plan",
    "refine_candidate",
]

REFINE_FILENAME = "refine.json"
REGEN_SCRATCH_DIRNAME = "_refine_regen"
RETEX_FILENAME = "model_retex.glb"


class Retexturer(Protocol):
    """Same interface for every retexture provider (Meshy today)."""

    def retexture(
        self,
        model_url_or_path: str | Path,
        *,
        image_ref: Path | None = None,
        text_prompt: str | None = None,
        dst_glb: Path,
    ) -> GenerationOutcome: ...


def _default_postprocess(*args: Any, **kwargs: Any) -> Any:
    # Resolved at call time so the Blender wrapper is imported lazily (and patchable).
    from harness.post import blender_post

    return blender_post.postprocess(*args, **kwargs)


def _default_get_variant(name: str) -> Variant:
    from harness.core.registry import get_variant

    return get_variant(name)


@dataclass
class RefineProviders:
    """External effects of the loop, injectable for tests."""

    get_variant: Callable[[str], Variant] = _default_get_variant
    retexturer: Retexturer | None = None
    postprocess: Callable[..., Any] = _default_postprocess
    blender_bin: Path | None = None

    @classmethod
    def from_settings(cls, settings: Any = None) -> RefineProviders:
        """Meshy retexture only when ``MESHY_API_KEY`` is set; Blender from ``BLENDER_BIN``."""
        from harness.core.config import Settings

        settings = settings or Settings.load()
        retexturer = None
        if settings.meshy_api_key:
            from harness.clients.meshy import MeshyClient

            retexturer = MeshyClient(settings.meshy_api_key)
        return cls(retexturer=retexturer, blender_bin=settings.blender_bin)


@dataclass
class RefineReport:
    run_id: str
    piece_id: str
    variant: str
    candidate: int
    final_candidate: int
    issues_before: list[Issue]
    issues_after: list[Issue]
    steps: list[dict[str, Any]] = field(default_factory=list)
    paid_actions: int = 0
    cost_usd: float = 0.0
    path: Path | None = None
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "started_at": self.started_at,
            "run_id": self.run_id,
            "piece_id": self.piece_id,
            "variant": self.variant,
            "candidate": self.candidate,
            "final_candidate": self.final_candidate,
            "issues_before": [i.to_dict() for i in self.issues_before],
            "issues_after": [i.to_dict() for i in self.issues_after],
            "steps": self.steps,
            "paid_actions": self.paid_actions,
            "cost_usd": self.cost_usd,
        }


class _StepFailed(RuntimeError):
    pass


def load_scores_row(
    run_id: str, piece_id: str, variant: str, candidate: int, *, root: Path = storage.RUNS_ROOT
) -> dict[str, Any] | None:
    """Last row of ``scores.jsonl`` for this candidate, or ``None``."""
    path = Path(root) / run_id / "eval" / "scores.jsonl"
    if not path.is_file():
        return None
    found = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (
            row.get("piece_id") == piece_id
            and row.get("variant") == variant
            and int(row.get("candidate", -1)) == candidate
        ):
            found = row
    return found


def _find_piece(piece_id: str, pieces_csv: Path) -> Piece:
    for piece in load_pieces(pieces_csv):
        if piece.id == piece_id:
            return piece
    raise KeyError(f"La pieza {piece_id} no está en {pieces_csv}")


def _post_block(result: Any) -> dict[str, Any]:
    """Same shape as the CLI post step, plus the guard outcome from ``post_meta.json``."""
    raw = getattr(result, "raw", {}) or {}
    return {
        "ok": True,
        "glb_path": str(result.glb_path),
        "seconds": result.seconds,
        "errors": result.errors,
        "errors_axis": result.errors_axis,
        "scale_factor": result.scale_factor,
        "draco": result.draco,
        "fit_box_requested": True,
        "fit_box_applied": result.fit_box_applied,
        "fit_factors": result.fit_factors,
        "fit_skip_reason": raw.get("fit_skip_reason"),
        "errors_before_fit": result.errors_before_fit,
        "triangles_before": result.tris_before,
        "triangles_after": result.tris_after,
    }


def _candidate_indices(workdir: Path) -> list[int]:
    indices = []
    for path in Path(workdir).glob("cand_*"):
        suffix = path.name.removeprefix("cand_")
        if path.is_dir() and suffix.isdigit():
            indices.append(int(suffix))
    return sorted(indices)


def _previous_regenerations(refine_path: Path) -> int:
    if not refine_path.is_file():
        return 0
    data = json.loads(refine_path.read_text(encoding="utf-8"))
    return sum(
        1
        for run in data.get("history", [])
        for step in run.get("steps", [])
        if step.get("action") == "regenerate" and step.get("status") == "ok"
    )


def refine_candidate(
    run_id: str,
    piece_id: str,
    variant: str,
    candidate: int,
    *,
    max_rounds: int = 2,
    providers: RefineProviders | None = None,
    piece: Piece | None = None,
    pieces_csv: Path = DEFAULT_SAMPLE_CSV,
    root: Path = storage.RUNS_ROOT,
    tolerance: float = SCALE_TOLERANCE,
    fit_guard: float = DEFAULT_FIT_GUARD,
) -> RefineReport:
    """Diagnose and fix one candidate; never attempts more than ``max_rounds`` paid actions."""
    providers = providers or RefineProviders.from_settings()
    piece = piece or _find_piece(piece_id, pieces_csv)
    workdir = Path(root) / run_id / piece_id / variant
    start_dir = workdir / f"cand_{candidate}"
    if not start_dir.is_dir():
        raise FileNotFoundError(f"No existe el candidato {start_dir}")
    refine_path = start_dir / REFINE_FILENAME
    regenerations = _previous_regenerations(refine_path)

    current = candidate
    meta = storage.read_meta(start_dir)
    row = load_scores_row(run_id, piece_id, variant, candidate, root=root)
    issues_before = diagnose(meta, row, tolerance=tolerance, guard=fit_guard)
    report = RefineReport(
        run_id=run_id,
        piece_id=piece_id,
        variant=variant,
        candidate=candidate,
        final_candidate=candidate,
        issues_before=issues_before,
        issues_after=issues_before,
        path=refine_path,
    )
    tried: set[tuple[int, str]] = set()  # (candidate, action) already attempted or blocked
    blocked_global: set[str] = set()

    def repost(cand_dir: Path, glb_in: Path) -> dict[str, Any]:
        try:
            result = providers.postprocess(
                glb_in,
                storage.model_post_path(cand_dir),
                piece,
                fit_box=True,
                fit_guard=fit_guard,
                blender_bin=providers.blender_bin,
            )
        except (BlenderNotAvailable, subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
            raise _StepFailed(f"postprocesado fallido: {exc}") from exc
        post = _post_block(result)
        cand_meta = storage.read_meta(cand_dir)
        cand_meta["post"] = post
        storage.write_meta(cand_dir, cand_meta)
        return post

    def apply(action: Action) -> dict[str, Any]:
        nonlocal current, regenerations
        cand_dir = workdir / f"cand_{current}"
        if action.kind == "fit_box":
            post = repost(cand_dir, storage.model_path(cand_dir))
            return {"post": post, "cost_usd": 0.0}
        if action.kind == "retexture":
            assert providers.retexturer is not None
            image = next((p for p in piece.images if Path(p).is_file()), None)
            outcome = providers.retexturer.retexture(
                storage.model_path(cand_dir),
                image_ref=image,
                text_prompt=piece.description or piece.name,
                dst_glb=cand_dir / RETEX_FILENAME,
            )
            cand_meta = storage.read_meta(cand_dir)
            cand_meta["retexture"] = {
                "glb_path": str(outcome.glb_path),
                "cost_usd": outcome.cost_usd,
                "task_id": outcome.meta.get("task_id"),
            }
            storage.write_meta(cand_dir, cand_meta)
            post = repost(cand_dir, outcome.glb_path)
            return {"post": post, "cost_usd": outcome.cost_usd, "glb_path": str(outcome.glb_path)}
        # regenerate
        try:
            variant_obj = providers.get_variant(variant)
        except KeyError as exc:
            blocked_global.add("regenerate")
            return {"status": "skipped", "detail": f"variante no registrada: {exc}"}
        new_index = max(_candidate_indices(workdir)) + 1
        scratch = workdir / REGEN_SCRATCH_DIRNAME
        shutil.rmtree(scratch, ignore_errors=True)
        try:
            result = variant_obj.run(piece, scratch, candidates=new_index)
            cost = sum(c.cost_usd for c in result.candidates)
            produced = scratch / f"cand_{new_index}"
            if not storage.model_path(produced).is_file():
                raise _StepFailed(
                    f"la variante no produjo cand_{new_index} ({result.notes or 'sin notas'})"
                )
            target = workdir / f"cand_{new_index}"
            shutil.move(str(produced), str(target))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        cand_meta = storage.read_meta(target)
        cand_meta.update(
            index=new_index,
            glb_path=str(storage.model_path(target)),
            refine_origin={
                "from_candidate": current,
                "generated_candidates": new_index,
                "cost_usd": cost,
            },
        )
        storage.write_meta(target, cand_meta)
        regenerations += 1
        current = new_index
        post = repost(target, storage.model_path(target))
        return {"post": post, "cost_usd": cost, "new_candidate": new_index}

    meta_now, row_now = meta, row
    # Each action runs at most once per candidate (≤ 3 candidates incl. regenerated ones),
    # so this safety bound is never the limiter.
    for _ in range(max_rounds + 8):
        issues = diagnose(meta_now, row_now, tolerance=tolerance, guard=fit_guard)
        planned = plan(
            issues,
            regenerations_done=regenerations,
            max_regenerations=MAX_EXTRA_CANDIDATES,
            can_retexture=providers.retexturer is not None,
            paid_budget=max_rounds - report.paid_actions,
        )
        planned = [
            a for a in planned if (current, a.kind) not in tried and a.kind not in blocked_global
        ]
        report.issues_after = issues
        if not planned:
            break
        action = planned[0]
        tried.add((current, action.kind))
        step: dict[str, Any] = {
            "action": action.kind,
            "candidate": current,
            "reason": action.reason,
            "paid": action.paid,
            "at": datetime.now(UTC).isoformat(),
            "post_before": (meta_now.get("post") or None),
        }
        try:
            outcome = apply(action)
            step["status"] = outcome.pop("status", "ok")
            step.update(outcome)
        except Exception as exc:  # noqa: BLE001 — recorded; the loop moves on
            step["status"] = "failed"
            step["detail"] = str(exc)
        # A failed paid attempt counts (the provider may have billed it); a skip does not.
        if action.paid and step["status"] != "skipped":
            report.paid_actions += 1
        report.cost_usd += float(step.get("cost_usd", 0.0) or 0.0)
        report.steps.append(step)
        meta_now = storage.read_meta(workdir / f"cand_{current}")
        if current != candidate:
            row_now = None  # the new candidate has not been evaluated
        _write_refine(refine_path, report)
    report.final_candidate = current
    report.issues_after = diagnose(meta_now, row_now, tolerance=tolerance, guard=fit_guard)
    _write_refine(refine_path, report)
    return report


def _write_refine(path: Path, report: RefineReport) -> None:
    """Append (or update in place) this call's entry in ``refine.json``."""
    data: dict[str, Any] = {"history": []}
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
    entry = report.to_dict()
    history = [h for h in data.get("history", []) if h.get("call_id") != report.call_id]
    history.append(entry)
    data["history"] = history
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
