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
cannot be regenerated (the step is recorded as skipped). The ``MAX_EXTRA_CANDIDATES`` cap is
per piece/variant workdir: it counts the ``cand_*`` metas carrying ``refine_origin`` (plus
attempts of the current call that billed but left no candidate), whichever candidate starts
the call. Billed cost and the new index are recorded on the step before post-processing, so a
later failure does not lose them. Handlers live in ``harness.refine.actions``.

Retexture writes ``model_retex.glb`` next to ``model.glb`` (which is kept) and re-postprocesses
it into ``model_post.glb``. Every re-postprocess uses ``fit_box=True`` and refreshes the
``post`` block of the candidate's ``meta.json`` (the previous one stays in ``refine.json``).
Caveat: a later CLI re-post (``harness run --post``) starts from ``model.glb`` and would drop
the retexture; re-post from ``model_retex.glb`` when it exists. The Meshy data-URI limit
(100 MB) is checked on the raw GLB bytes; the base64 payload is ~1.33× larger.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from harness.clients.meshy import GenerationOutcome
from harness.core import storage
from harness.core.models import DEFAULT_SAMPLE_CSV, SCALE_TOLERANCE, Piece, load_pieces
from harness.core.variant import Variant
from harness.post.bpy_post import DEFAULT_FIT_GUARD
from harness.refine.actions import HANDLERS, RefineContext, regenerations_in_workdir
from harness.refine.rules import (
    MAX_EXTRA_CANDIDATES,
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
logger = logging.getLogger(__name__)


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
    warnings: list[str] = field(default_factory=list)
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
            "warnings": self.warnings,
        }


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

    ctx = RefineContext(
        piece=piece,
        variant=variant,
        workdir=workdir,
        providers=providers,
        fit_guard=fit_guard,
        current=candidate,
    )
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
        path=start_dir / REFINE_FILENAME,
    )
    tried: set[tuple[int, str]] = set()  # (candidate, action) already attempted

    # Each action runs at most once per candidate (≤ 3 candidates incl. regenerated ones),
    # so this safety bound is never the limiter.
    for _ in range(max_rounds + 8):
        issues = diagnose(meta, row, tolerance=tolerance, guard=fit_guard)
        report.issues_after = issues
        planned = plan(
            issues,
            # The +2 cap is per piece/variant workdir, whichever candidate started the call.
            regenerations_done=regenerations_in_workdir(workdir) + ctx.lost_regenerations,
            max_regenerations=MAX_EXTRA_CANDIDATES,
            can_retexture=providers.retexturer is not None,
            paid_budget=max_rounds - report.paid_actions,
        )
        planned = [
            a for a in planned if (ctx.current, a.kind) not in tried and a.kind not in ctx.blocked
        ]
        if not planned:
            break
        action = planned[0]
        tried.add((ctx.current, action.kind))
        step: dict[str, Any] = {
            "action": action.kind,
            "candidate": ctx.current,
            "reason": action.reason,
            "paid": action.paid,
            "at": datetime.now(UTC).isoformat(),
            "post_before": meta.get("post") or None,
        }
        try:
            HANDLERS[action.kind](ctx, step)
            step.setdefault("status", "ok")
        except Exception as exc:  # noqa: BLE001 — recorded; the loop moves on
            step["status"] = "failed"
            step["detail"] = str(exc)
        # A failed paid attempt counts (the provider may have billed it); a skip does not.
        if action.paid and step["status"] != "skipped":
            report.paid_actions += 1
        report.cost_usd += float(step.get("cost_usd") or 0.0)
        report.steps.append(step)
        if ctx.current != candidate:
            row = None  # the regenerated candidate has not been evaluated
        meta = storage.read_meta(ctx.cand_dir())
        _write_refine(report)
    report.final_candidate = ctx.current
    report.issues_after = diagnose(meta, row, tolerance=tolerance, guard=fit_guard)
    _write_refine(report)
    return report


def _write_refine(report: RefineReport) -> None:
    """Append (or update in place) this call's entry in ``refine.json``.

    A corrupt file is kept aside as ``refine.json.corrupt`` and the history restarts, with a
    warning in the report.
    """
    path = report.path
    assert path is not None
    history: list[dict[str, Any]] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            history = list(data["history"])
        except (ValueError, KeyError, TypeError) as exc:
            backup = path.with_name(path.name + ".corrupt")
            path.replace(backup)
            warning = (
                f"{path.name} corrupto ({exc!r}); copiado a {backup.name}, historial reiniciado"
            )
            report.warnings.append(warning)
            logger.warning(warning)
    history = [h for h in history if not isinstance(h, dict) or h.get("call_id") != report.call_id]
    history.append(report.to_dict())
    path.write_text(
        json.dumps({"history": history}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
