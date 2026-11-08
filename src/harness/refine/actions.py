"""Action handlers of the refinement loop: ``fit_box``, ``regenerate``, ``retexture``.

Each handler takes a :class:`RefineContext` and the step dict being recorded and writes its
results into ``step`` as soon as they are known, so a cost billed by a provider survives a
later failure (e.g. post-processing). Handlers raise on failure; the orchestrator
(``harness.refine.refine_candidate``) records the status. A handler may set
``step["status"] = "skipped"`` when nothing was sent to a provider.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.models import Piece

if TYPE_CHECKING:
    from harness.refine import RefineProviders

REGEN_SCRATCH_DIRNAME = "_refine_regen"
RETEX_FILENAME = "model_retex.glb"
REFINE_ORIGIN_KEY = "refine_origin"


class StepFailed(RuntimeError):
    pass


@dataclass
class RefineContext:
    piece: Piece
    variant: str
    workdir: Path
    providers: RefineProviders
    fit_guard: float
    current: int
    # Regenerations of this call that billed but left no candidate behind (count to the cap).
    lost_regenerations: int = 0
    blocked: set[str] = field(default_factory=set)  # actions unavailable for the whole call

    def cand_dir(self, index: int | None = None) -> Path:
        return self.workdir / f"cand_{self.current if index is None else index}"


def candidate_indices(workdir: Path) -> list[int]:
    indices = []
    for path in Path(workdir).glob("cand_*"):
        suffix = path.name.removeprefix("cand_")
        if path.is_dir() and suffix.isdigit():
            indices.append(int(suffix))
    return sorted(indices)


def regenerations_in_workdir(workdir: Path) -> int:
    """Candidates created by refinement in this piece/variant (cap is per workdir)."""
    return sum(
        1
        for index in candidate_indices(workdir)
        if REFINE_ORIGIN_KEY in storage.read_meta(Path(workdir) / f"cand_{index}")
    )


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


def repost(ctx: RefineContext, cand_dir: Path, glb_in: Path) -> dict[str, Any]:
    """Post-process ``glb_in`` into the candidate's ``model_post.glb`` with ``fit_box=True``
    and refresh the ``post`` block of its ``meta.json``."""
    try:
        result = ctx.providers.postprocess(
            glb_in,
            storage.model_post_path(cand_dir),
            ctx.piece,
            fit_box=True,
            fit_guard=ctx.fit_guard,
            blender_bin=ctx.providers.blender_bin,
        )
    except (BlenderNotAvailable, subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
        raise StepFailed(f"postprocesado fallido: {exc}") from exc
    post = _post_block(result)
    meta = storage.read_meta(cand_dir)
    meta["post"] = post
    storage.write_meta(cand_dir, meta)
    return post


def fit_box(ctx: RefineContext, step: dict[str, Any]) -> None:
    cand_dir = ctx.cand_dir()
    step["cost_usd"] = 0.0
    step["post"] = repost(ctx, cand_dir, storage.model_path(cand_dir))


def retexture(ctx: RefineContext, step: dict[str, Any]) -> None:
    retexturer = ctx.providers.retexturer
    if retexturer is None:
        ctx.blocked.add("retexture")
        step["status"] = "skipped"
        step["detail"] = "sin proveedor de retexturizado"
        return
    cand_dir = ctx.cand_dir()
    image = next((p for p in ctx.piece.images if Path(p).is_file()), None)
    outcome = retexturer.retexture(
        storage.model_path(cand_dir),
        image_ref=image,
        text_prompt=ctx.piece.description or ctx.piece.name,
        dst_glb=cand_dir / RETEX_FILENAME,
    )
    step["cost_usd"] = outcome.cost_usd
    step["glb_path"] = str(outcome.glb_path)
    meta = storage.read_meta(cand_dir)
    meta["retexture"] = {
        "glb_path": str(outcome.glb_path),
        "cost_usd": outcome.cost_usd,
        "task_id": outcome.meta.get("task_id"),
    }
    storage.write_meta(cand_dir, meta)
    step["post"] = repost(ctx, cand_dir, outcome.glb_path)


def regenerate(ctx: RefineContext, step: dict[str, Any]) -> None:
    """Run the variant with ``N + 1`` candidates in a scratch dir; keep only ``cand_<N+1>``."""
    try:
        variant_obj = ctx.providers.get_variant(ctx.variant)
    except KeyError as exc:
        ctx.blocked.add("regenerate")
        step["status"] = "skipped"
        step["detail"] = f"variante no registrada: {exc}"
        return
    workdir = ctx.workdir
    new_index = max(candidate_indices(workdir)) + 1
    scratch = workdir / REGEN_SCRATCH_DIRNAME
    target = workdir / f"cand_{new_index}"
    shutil.rmtree(scratch, ignore_errors=True)
    try:
        # From here on the provider may bill: a failure counts as a (lost) regeneration.
        ctx.lost_regenerations += 1
        result = variant_obj.run(ctx.piece, scratch, candidates=new_index)
        cost = sum(c.cost_usd for c in result.candidates)
        step["cost_usd"] = cost
        produced = scratch / f"cand_{new_index}"
        if not storage.model_path(produced).is_file():
            raise StepFailed(
                f"la variante no produjo cand_{new_index} ({result.notes or 'sin notas'})"
            )
        shutil.move(str(produced), str(target))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    ctx.lost_regenerations -= 1  # now counted through refine_origin in the workdir

    produced_cand = next((c for c in result.candidates if c.index == new_index), None)
    meta = storage.read_meta(target)
    if produced_cand is not None:
        meta.update(produced_cand.model_dump(mode="json"))
    meta.update(
        piece_id=ctx.piece.id,
        variant=ctx.variant,
        index=new_index,
        glb_path=str(storage.model_path(target)),
    )
    meta[REFINE_ORIGIN_KEY] = {
        "from_candidate": ctx.current,
        "generated_candidates": new_index,
        "cost_usd": cost,
    }
    storage.write_meta(target, meta)
    step["new_candidate"] = new_index
    ctx.current = new_index
    step["post"] = repost(ctx, target, storage.model_path(target))


HANDLERS: dict[str, Callable[[RefineContext, dict[str, Any]], None]] = {
    "fit_box": fit_box,
    "regenerate": regenerate,
    "retexture": retexture,
}
