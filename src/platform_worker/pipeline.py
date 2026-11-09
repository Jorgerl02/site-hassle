"""One piece end to end: photos → checks → route → generation → post-processing → geometry
→ renders and contact sheet → delivery (GLB 2K + USDZ, preview GLB) → Storage → rows.

Reuses the harness: ``validate_input``/``explain`` (via ``intake``), ``rule_classify``, the
parametric variant E, ``postprocess``, ``measure_candidate``, ``render_views`` and
``deliver``. Organic pieces get ``ORGANIC_CANDIDATES`` candidates from the provider, each
post-processed with the guarded fit-to-box; the lowest ``max_error`` is ``selected``.

Storage paths stored in ``piece_models`` are relative to their bucket (``models``:
``glb_path``/``usdz_path``; ``previews``: ``preview_path``; ``renders``: ``render_paths``).
"""

from __future__ import annotations

import shutil
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from harness.core.models import Piece
from harness.eval.geometry import measure_candidate
from harness.eval.render import render_views
from harness.post.blender_post import postprocess
from harness.post.deliver import deliver
from harness.prep.clean import clean_image
from harness.variants.e_parametric import ParametricVariant
from harness.variants.f_router import rule_classify
from platform_worker import intake
from platform_worker.providers.base import Provider

ORGANIC_CANDIDATES = 2
DELIVER_MAX_TRIS = 60_000
DELIVER_MAX_TEX = 2048
PREVIEW_MAX_TRIS = 15_000
PREVIEW_MAX_TEX = 512
PREVIEW_FILENAME = "model_preview.glb"
CONTACT_FILENAME = "contact.jpg"
# Harness render name → name in the ``renders`` bucket (Global Constraints).
RENDER_VIEWS: dict[str, str] = {
    "front": "front",
    "side": "left",
    "back": "back",
    "three_quarter": "three_quarter",
}
CONTACT_TILE = 512
ERROR_MAX_CHARS = 2000
NO_PROVIDER_ERROR = (
    "Las piezas orgánicas necesitan un proveedor de generación (PROVIDER=tripo o fal en el "
    "worker). De momento solo se generan piezas rectilíneas."
)

STATUS_REVIEW = "review"
STATUS_NEEDS_PHOTOS = "needs_photos"
STATUS_FAILED = "failed"


@dataclass
class CandidateRun:
    index: int
    cand_dir: Path
    cost_usd: float = 0.0
    seconds: float = 0.0
    gen_meta: dict[str, Any] = field(default_factory=dict)
    post: dict[str, Any] | None = None
    geometry: dict[str, Any] | None = None
    max_error: float | None = None
    error: str | None = None


def piece_workdir(root: Path, piece_id: str, attempt: int) -> Path:
    """``<root>/{piece_id}/{attempt}/`` (root = ``runs/platform`` by default)."""
    path = Path(root) / str(piece_id) / str(attempt)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _suffix(storage_path: str) -> str:
    suffix = Path(storage_path).suffix.lower()
    return suffix if suffix else ".jpg"


def download_photos(db: Any, storage: Any, piece_id: str, work: Path) -> list[Path]:
    photos_dir = work / "photos"
    if photos_dir.exists():
        shutil.rmtree(photos_dir)
    paths: list[Path] = []
    for n, row in enumerate(db.list_photos(piece_id), start=1):
        dst = photos_dir / f"{n}{_suffix(row['storage_path'])}"
        storage.download("photos", row["storage_path"], dst)
        paths.append(dst)
    return paths


def contact_sheet(renders: list[Path], photo: Path | None, dst: Path) -> Path:
    """One row: the first photo, then the four renders, each fitted in a white square."""
    tiles = ([photo] if photo is not None else []) + list(renders)
    sheet = Image.new("RGB", (CONTACT_TILE * len(tiles), CONTACT_TILE), (255, 255, 255))
    for i, path in enumerate(tiles):
        with Image.open(path) as img:
            tile = img.convert("RGBA")
        tile.thumbnail((CONTACT_TILE, CONTACT_TILE))
        x = i * CONTACT_TILE + (CONTACT_TILE - tile.width) // 2
        y = (CONTACT_TILE - tile.height) // 2
        sheet.paste(tile, (x, y), tile)
    dst.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dst, "JPEG", quality=85)
    return dst


def _post_meta(post: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "seconds": post.seconds,
        "errors": post.errors,
        "errors_before_fit": post.errors_before_fit,
        "fit_box_applied": post.fit_box_applied,
        "fit_factors": post.fit_factors,
        "triangles_before": post.tris_before,
        "triangles_after": post.tris_after,
    }


def _measure(cand: CandidateRun, piece: Piece, post: Any) -> None:
    result = measure_candidate(cand.cand_dir / "model_post.glb", piece)
    if result.metrics is not None:
        cand.geometry = {"source": result.source, **result.metrics.model_dump()}
        cand.max_error = result.metrics.max_error
    else:
        cand.geometry = {"source": None, "error": result.error}
        cand.max_error = post.max_abs_error


def _organic_images(photos: list[Path], work: Path) -> list[Path]:
    """Cleaned first photo (background removed, white square) as the provider input."""
    try:
        return [clean_image(photos[0], work / "clean" / "1.png")]
    except ValueError:
        return [photos[0]]


def generate_candidates(
    piece: Piece,
    piece_row: dict[str, Any],
    route: str,
    photos: list[Path],
    work: Path,
    *,
    provider: Provider | None,
    blender_bin: Path | None,
) -> list[CandidateRun]:
    if route == "E":
        override = intake.parametric_kind_override(piece_row)
        variant = ParametricVariant(
            blender_bin=blender_bin,
            overrides_path=None,
            kind_overrides={piece.id: override} if override else None,
        )
        result = variant.run(piece, work / "E", candidates=1)
        runs: list[CandidateRun] = []
        for c in result.candidates:
            cand = CandidateRun(c.index, c.glb_path.parent, c.cost_usd, c.seconds, c.meta)
            post = postprocess(
                c.glb_path, cand.cand_dir / "model_post.glb", piece, blender_bin=blender_bin
            )
            cand.post = _post_meta(post)
            _measure(cand, piece, post)
            runs.append(cand)
        return runs

    if provider is None:
        raise NoProviderError(NO_PROVIDER_ERROR)
    images = _organic_images(photos, work)
    runs = []
    for index in range(1, ORGANIC_CANDIDATES + 1):
        cand = CandidateRun(index, work / provider.name / f"cand_{index}")
        try:
            outcome = provider.generate(images, cand.cand_dir / "model.glb", seed=index)
            cand.cost_usd, cand.seconds, cand.gen_meta = (
                outcome.cost_usd,
                outcome.seconds,
                outcome.meta,
            )
            post = postprocess(
                outcome.glb_path,
                cand.cand_dir / "model_post.glb",
                piece,
                blender_bin=blender_bin,
                fit_box=True,
            )
            cand.post = _post_meta(post)
            _measure(cand, piece, post)
        except Exception as exc:  # one failed candidate must not lose the other
            cand.error = f"{type(exc).__name__}: {exc}"[:ERROR_MAX_CHARS]
        runs.append(cand)
    return runs


class NoProviderError(RuntimeError):
    """An organic piece arrived and the worker has no provider configured."""


def _deliver_selected(
    piece: Piece,
    cand: CandidateRun,
    photos: list[Path],
    storage: Any,
    *,
    attempt: int,
    blender_bin: Path | None,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    prefix = f"{piece.id}/{attempt}"
    renders_dir = cand.cand_dir / "renders"
    rendered = render_views(cand.cand_dir / "model_post.glb", renders_dir, blender_bin=blender_bin)
    by_view = {p.stem: p for p in rendered}
    renders = [by_view[view] for view in RENDER_VIEWS]
    contact = contact_sheet(renders, photos[0] if photos else None, renders_dir / CONTACT_FILENAME)

    full = deliver(
        cand.cand_dir,
        piece,
        max_tris=DELIVER_MAX_TRIS,
        max_tex=DELIVER_MAX_TEX,
        out_dir=cand.cand_dir / "deliver",
        blender_bin=blender_bin,
        provenance=provenance,
    )
    preview = deliver(
        cand.cand_dir,
        piece,
        max_tris=PREVIEW_MAX_TRIS,
        max_tex=PREVIEW_MAX_TEX,
        out_dir=cand.cand_dir / "preview",
        blender_bin=blender_bin,
        provenance={**provenance, "preview": True},
    )
    preview_glb = preview.glb_path.with_name(PREVIEW_FILENAME)
    shutil.copyfile(preview.glb_path, preview_glb)

    glb_path = storage.upload("models", f"{prefix}/model_web.glb", full.glb_path)
    usdz_path = (
        storage.upload("models", f"{prefix}/model.usdz", full.usdz_path)
        if full.usdz_path is not None
        else None
    )
    preview_path = storage.upload("previews", f"{prefix}/{PREVIEW_FILENAME}", preview_glb)
    render_paths: dict[str, str] = {}
    for harness_view, name in RENDER_VIEWS.items():
        render_paths[name] = storage.upload(
            "renders", f"{prefix}/{name}.png", by_view[harness_view]
        )
    render_paths["contact"] = storage.upload("renders", f"{prefix}/{CONTACT_FILENAME}", contact)
    return {
        "glb_path": glb_path,
        "usdz_path": usdz_path,
        "preview_path": preview_path,
        "render_paths": render_paths,
        "deliver": {
            "glb_bytes": full.glb_bytes,
            "usdz_bytes": full.usdz_bytes,
            "usdz_error": full.usdz_error,
            "tris_after": full.tris_after,
            "max_tris": full.max_tris,
            "max_tex": full.max_tex,
            "within_limit": full.within_limit,
            "preview_glb_bytes": preview.glb_bytes,
            "preview_tris_after": preview.tris_after,
        },
    }


def _fail(db: Any, piece_id: str, message: str) -> str:
    db.update_piece(piece_id, status=STATUS_FAILED, error=message[:ERROR_MAX_CHARS])
    return STATUS_FAILED


def process_piece(
    db: Any,
    storage: Any,
    piece_row: dict[str, Any],
    *,
    provider: Provider | None,
    workdir: Path,
    blender_bin: Path | None,
) -> str:
    """Run one claimed piece; returns the final status (``review|needs_photos|failed``).

    Never raises for a piece-level problem: every failure ends in ``failed`` with a Spanish
    ``error`` (the traceback goes to ``<work>/error.log``)."""
    piece_id = str(piece_row["id"])
    attempt = int(piece_row.get("attempt") or 1)
    work = piece_workdir(workdir, piece_id, attempt)
    start = time.monotonic()
    try:
        try:
            photos = download_photos(db, storage, piece_id, work)
        except Exception as exc:
            return _fail(db, piece_id, f"No se pudieron descargar las fotos: {exc}")

        problems = intake.check(piece_row, photos)
        if problems:
            db.update_piece(piece_id, status=STATUS_NEEDS_PHOTOS, error=intake.explain(problems))
            return STATUS_NEEDS_PHOTOS

        piece = intake.build_piece(piece_row, photos)
        decision = rule_classify(piece)
        organic = decision.route != "E"
        route = "E" if not organic else (provider.name if provider is not None else "sin proveedor")
        db.update_piece(piece_id, route=route)

        try:
            runs = generate_candidates(
                piece, piece_row, decision.route if not organic else "organic", photos, work,
                provider=provider, blender_bin=blender_bin,
            )  # fmt: skip
        except NoProviderError as exc:
            return _fail(db, piece_id, str(exc))

        ok = [c for c in runs if c.error is None and c.max_error is not None]
        if not ok:
            errors = "; ".join(c.error for c in runs if c.error) or "sin candidatos"
            return _fail(db, piece_id, f"No se pudo generar ningún modelo: {errors}")
        selected = min(ok, key=lambda c: c.max_error)
        provider_name = "parametric" if not organic else provider.name  # type: ignore[union-attr]
        provenance = {
            "variant": route,
            "candidate": selected.index,
            "attempt": attempt,
            "provider": provider_name,
        }
        delivered = _deliver_selected(
            piece, selected, photos, storage,
            attempt=attempt, blender_bin=blender_bin, provenance=provenance,
        )  # fmt: skip

        for cand in runs:
            is_selected = cand is selected
            meta: dict[str, Any] = {
                "route": decision.route,
                "route_reason": decision.reason,
                "thin": decision.thin,
                "provider": provider_name,
                "candidate": cand.index,
                "post": cand.post,
                "geometry": cand.geometry,
                "generation": cand.gen_meta,
                "seconds": round(cand.seconds, 3),
            }
            if cand.error:
                meta["error"] = cand.error
            if is_selected:
                meta["deliver"] = delivered["deliver"]
                meta["total_seconds"] = round(time.monotonic() - start, 3)
            db.insert_model(
                {
                    "piece_id": piece_id,
                    "attempt": attempt,
                    "provider": provider_name,
                    "candidate": cand.index,
                    "preview_path": delivered["preview_path"] if is_selected else None,
                    "glb_path": delivered["glb_path"] if is_selected else None,
                    "usdz_path": delivered["usdz_path"] if is_selected else None,
                    "render_paths": delivered["render_paths"] if is_selected else None,
                    "meta": meta,
                    "max_error": cand.max_error,
                    "cost_usd": cand.cost_usd,
                    "selected": is_selected,
                }
            )
        db.update_piece(piece_id, status=STATUS_REVIEW, error=None)
        return STATUS_REVIEW
    except Exception as exc:
        (work / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        return _fail(db, piece_id, f"Error del worker: {type(exc).__name__}: {exc}")
