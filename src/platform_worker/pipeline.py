"""One piece end to end: photos → checks → interpretation and route → generation →
post-processing → (library material) → geometry → renders and contact sheet → delivery
(GLB 2K + USDZ, preview GLB + USDZ) → Storage → rows → automatic publishing or review.

Reuses the harness: ``validate_input``/``explain`` (via ``intake``), the parametric variant
E, ``postprocess``, ``measure_candidate``, ``apply_material``, ``render_views``,
``deliver`` and the VLM judge. The photo interpretation (``interpret``) fills the optional
answers the customer skipped and decides the route (``intake.decide_route``). Organic
pieces get ``ORGANIC_CANDIDATES`` candidates from the provider, each post-processed with
the guarded fit-to-box; the lowest ``max_error`` is ``selected``. Every successful
candidate gets renders, contact sheet, GLB 2K + USDZ and preview (GLB + USDZ for iOS
Quick Look), so the admin can pick either: the selected one under
``{piece_id}/{attempt}/``, the others under ``{piece_id}/{attempt}/cand_{n}/`` (see
:func:`storage_prefix`). The selected candidate then goes through
``autopublish.decide``: ``ready`` (customer notified) or ``review`` (admin notified).

Storage paths stored in ``piece_models`` are relative to their bucket (``models``:
``glb_path``/``usdz_path``; ``previews``: ``preview_path``, with the preview USDZ next to
it under the same name and ``.usdz``; ``renders``: ``render_paths``).

``piece_models.meta`` keys written here: ``interpretation`` (the photo reading plus
``effective`` answers, ``source`` and ``conflict``), ``dimension_warnings``, ``routing``,
``material``, ``deliver`` (with ``warnings`` and ``optimize_error``), ``warnings`` (every
warning for the admin) and, on the selected row, ``auto_review``.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from PIL import Image, ImageOps

from harness.core.config import resolve_scale_tolerance
from harness.core.models import GeometryMetrics, Piece
from harness.eval.geometry import measure_candidate
from harness.eval.judge import judge_candidate
from harness.eval.render import VIEWS, render_views
from harness.post import materials
from harness.post.blender_post import postprocess
from harness.post.deliver import DeliverError, deliver
from harness.post.materials import apply_material, detect_material, photo_mean_color
from harness.prep.clean import clean_image
from harness.variants.e_parametric import ParametricVariant
from platform_worker import autopublish, intake
from platform_worker.config import load_settings
from platform_worker.interpret import (
    Interpretation,
    Interpreter,
    SilhouetteInterpreter,
    check_dimensions,
)
from platform_worker.providers.base import Provider

ORGANIC_CANDIDATES = 2
DELIVER_MAX_TRIS = 60_000
DELIVER_MAX_TEX = 2048
PREVIEW_MAX_TRIS = 15_000
PREVIEW_MAX_TEX = 512
PREVIEW_FILENAME = "model_preview.glb"
PREVIEW_USDZ_FILENAME = "model_preview.usdz"  # iOS Quick Look (``ios-src``) next to the GLB
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
STATUS_READY = "ready"  # published automatically (``autopublish``)
STATUS_GENERATING = "generating"
# Returned when the final write found the piece no longer ``generating`` on this attempt
# (an admin or the customer moved it meanwhile): nothing is published nor notified.
STATUS_SUPERSEDED = "superseded"
STATUS_NEEDS_PHOTOS = "needs_photos"
STATUS_FAILED = "failed"
STATUS_REJECTED = "rejected"  # excluded categories (lámpara, metal, vidrio)
# Returned when a piece without photos yet, or deferred by the daily budget, goes back to
# the queue.
STATUS_QUEUED = "queued"
# Notice sent to the web (admin) when the daily provider budget runs out (once a day).
NOTICE_BUDGET = "budget"

# Same cap as the form and the ``piece_photos`` trigger: the first 4 photos by position.
MAX_PHOTOS = 4
THUMB_STEM = "thumb"

# Daily provider budget (USD) over every organic piece; ``WORKER_DAILY_BUDGET_USD``.
DEFAULT_DAILY_BUDGET_USD = 20.0
BUDGET_MESSAGE = "Daily generation budget reached; we'll retry tomorrow."
MADRID = ZoneInfo("Europe/Madrid")

# A piece can be claimed the instant it is inserted, before its ``piece_photos`` rows exist:
# while it is younger than ``PHOTOS_GRACE`` (from ``created_at``) it goes back to ``queued``;
# after that it becomes ``needs_photos``. Time-based on purpose: ``claim_next_piece()``
# clears ``error`` on every claim, so a counter kept in the row would never advance.
PHOTOS_GRACE = timedelta(minutes=10)
WAITING_PHOTOS_MESSAGE = "Waiting for the piece's photos."
NO_PHOTOS_ERROR = (
    "We didn't receive any photos for this piece. Upload at least one photo to continue."
)
PROVIDER_MAX_PX = 2048  # raw-photo fallback for providers (fal base64 limit ≈ 6 MB)
NOTIFY_TIMEOUT_SECONDS = 10.0
# Workdir file with the forced parametric kind + params (``ParametricVariant`` reads it).
E_OVERRIDES_FILENAME = "e_overrides.json"
# Material swap: the post-processed mesh is kept under this name, the material version
# takes ``model_post.glb`` (what renders and delivery read).
POST_GLB = "model_post.glb"
POST_RAW_GLB = "model_post_raw.glb"
MATERIAL_GLB = "model_material.glb"

log = logging.getLogger(__name__)


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
    metrics: GeometryMetrics | None = None
    material: dict[str, Any] | None = None


@dataclass
class MaterialPlan:
    """Library material for this attempt: ``material_id`` (None = keep the mesh's own
    texture), where it came from (``admin`` note, ``detected`` in the name/notes, or
    ``admin_off``) and whether it applies to route E (only the admin's choice does)."""

    material_id: str | None
    source: str | None
    target_rgb: tuple[int, int, int] | None = None
    target_error: str | None = None
    real_size_cm: tuple[float, float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.material_id, "source": self.source}
        if self.target_rgb is not None:
            out["target_rgb"] = list(self.target_rgb)
        if self.target_error:
            out["target_error"] = self.target_error
        return out


def piece_workdir(root: Path, piece_id: str, attempt: int) -> Path:
    """``<root>/{piece_id}/{attempt}/`` (root = ``runs/platform`` by default)."""
    path = Path(root) / str(piece_id) / str(attempt)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _suffix(storage_path: str) -> str:
    suffix = Path(storage_path).suffix.lower()
    return suffix if suffix else ".jpg"


def check_photo_path(path: str, user_id: str, piece_id: str) -> str:
    """``path`` if it lives directly under ``{user_id}/{piece_id}/``, else PhotoPathError."""
    prefix = f"{user_id}/{piece_id}/"
    name = path[len(prefix) :] if path.startswith(prefix) else ""
    if not name or ".." in path or "/" in name or "\\" in path:
        raise PhotoPathError(f"Ruta de foto no válida: {path!r}")
    return path


def download_photos(
    db: Any, storage: Any, piece_id: str, work: Path, *, user_id: str | None = None
) -> list[Path]:
    """The first ``MAX_PHOTOS`` photo rows by ``position`` (the thumbnail never counts).
    With ``user_id``, every path must be under ``{user_id}/{piece_id}/`` (no «..»)."""
    photos_dir = work / "photos"
    if photos_dir.exists():
        shutil.rmtree(photos_dir)
    rows = [
        r
        for r in db.list_photos(piece_id)
        if Path(str(r.get("storage_path") or "")).stem != THUMB_STEM
    ]
    rows = sorted(rows, key=lambda r: int(r.get("position") or 0))[:MAX_PHOTOS]
    if user_id is not None:
        for row in rows:
            check_photo_path(str(row.get("storage_path") or ""), str(user_id), str(piece_id))
    paths: list[Path] = []
    for n, row in enumerate(rows, start=1):
        dst = photos_dir / f"{n}{_suffix(row['storage_path'])}"
        storage.download("photos", row["storage_path"], dst)
        paths.append(dst)
    return paths


def oriented_copy(photo: Path, dst_dir: Path) -> Path:
    """``photo`` with its EXIF orientation applied (the same file when it has none)."""
    with Image.open(photo) as img:
        if img.getexif().get(0x0112, 1) in (None, 1):
            return Path(photo)
        upright = ImageOps.exif_transpose(img)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{Path(photo).stem}.jpg"
        upright.convert("RGB").save(dst, "JPEG", quality=95)
    return dst


def provider_photo(photo: Path, dst: Path, max_px: int = PROVIDER_MAX_PX) -> Path:
    """Raw photo downscaled to ≤ ``max_px`` on its long side, as JPEG."""
    with Image.open(photo) as img:
        out = ImageOps.exif_transpose(img).convert("RGB")
    out.thumbnail((max_px, max_px))
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, "JPEG", quality=90)
    return dst


def contact_sheet(renders: list[Path], photo: Path | None, dst: Path) -> Path:
    """One row: the first photo, then the four renders, each fitted in a white square."""
    tiles = ([photo] if photo is not None else []) + list(renders)
    sheet = Image.new("RGB", (CONTACT_TILE * len(tiles), CONTACT_TILE), (255, 255, 255))
    for i, path in enumerate(tiles):
        with Image.open(path) as img:
            tile = ImageOps.exif_transpose(img).convert("RGBA")
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
        cand.metrics = result.metrics
    else:
        cand.geometry = {"source": None, "error": result.error}
        cand.max_error = post.max_abs_error


def _organic_images(photos: list[Path], work: Path) -> list[Path]:
    """Cleaned first photo (background removed, white square) as the provider input; if the
    cleaning finds no object, the raw photo downscaled to ≤ 2048 px JPEG."""
    try:
        return [clean_image(photos[0], work / "clean" / "1.png")]
    except ValueError:
        return [provider_photo(photos[0], work / "clean" / "1_raw.jpg")]


def write_e_overrides(work: Path, piece_id: str, kind: str, params: dict[str, Any]) -> Path:
    """``{piece_id: {"kind", **params}}`` for ``ParametricVariant(overrides_path=…)``: the
    only way to hand E a kind *with* params (``kind_overrides`` carries the kind only)."""
    path = Path(work) / E_OVERRIDES_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({piece_id: {"kind": kind, **params}}, indent=2), encoding="utf-8")
    return path


def _apply_material(cand: CandidateRun, plan: MaterialPlan, *, blender_bin: Path | None) -> None:
    """Swap ``model_post.glb`` for the library-material version (the original is kept as
    ``model_post_raw.glb``). A failure keeps the mesh's own texture and records why."""
    if plan.material_id is None:
        return
    post = cand.cand_dir / POST_GLB
    out = cand.cand_dir / MATERIAL_GLB
    record: dict[str, Any] = {**plan.to_dict(), "applied": False}
    try:
        info = apply_material(
            post,
            out,
            material_id=plan.material_id,
            target_rgb=plan.target_rgb,
            real_size_cm=plan.real_size_cm,
            blender_bin=blender_bin,
        )
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"[:ERROR_MAX_CHARS]
        record["warnings"] = [
            f"No se pudo aplicar el material «{plan.material_id}»: se entrega la textura "
            f"original ({type(exc).__name__})"
        ]
        cand.material = record
        return
    shutil.move(post, cand.cand_dir / POST_RAW_GLB)
    shutil.move(out, post)
    record["applied"] = True
    record["warnings"] = list(info.get("warnings") or [])
    record["info"] = {k: v for k, v in info.items() if k != "warnings"}
    cand.material = record


def generate_candidates(
    piece: Piece,
    routing: intake.Routing,
    photos: list[Path],
    work: Path,
    *,
    provider: Provider | None,
    blender_bin: Path | None,
    before_provider_call: Callable[[int, float], bool] | None = None,
    material: MaterialPlan | None = None,
) -> list[CandidateRun]:
    """Candidates of one attempt. Route E builds one candidate with ``routing.kind`` and
    ``routing.params`` (or E's classification when ``routing.kind`` is None). For organic
    pieces ``before_provider_call(index, spent)`` (``spent`` = this piece's provider cost
    so far) runs before every provider call: False before the first one raises
    :class:`BudgetExhausted`; later, it stops generating. ``material`` replaces the mesh's
    materials after the post-processing (provider meshes; on E only the admin's choice)."""
    plan = material if material is not None and material.material_id else None
    if routing.route == intake.ROUTE_E:
        overrides = (
            write_e_overrides(work, piece.id, routing.kind, routing.params)
            if routing.kind
            else None
        )
        variant = ParametricVariant(
            blender_bin=blender_bin, overrides_path=overrides, kind_overrides=None
        )
        result = variant.run(piece, work / "E", candidates=1)
        runs: list[CandidateRun] = []
        for c in result.candidates:
            cand = CandidateRun(c.index, c.glb_path.parent, c.cost_usd, c.seconds, c.meta)
            post = postprocess(c.glb_path, cand.cand_dir / POST_GLB, piece, blender_bin=blender_bin)
            cand.post = _post_meta(post)
            _measure(cand, piece, post)
            if plan is not None and plan.source == "admin":
                _apply_material(cand, plan, blender_bin=blender_bin)
            runs.append(cand)
        return runs

    if provider is None:
        raise NoProviderError(NO_PROVIDER_ERROR)
    images = _organic_images(photos, work)
    runs = []
    for index in range(1, ORGANIC_CANDIDATES + 1):
        spent = sum(c.cost_usd for c in runs)
        if before_provider_call is not None and not before_provider_call(index, spent):
            if index == 1:
                raise BudgetExhausted(BUDGET_MESSAGE)
            log.warning("Presupuesto diario agotado: la pieza sigue con %d candidato(s)", index - 1)
            break
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
                cand.cand_dir / POST_GLB,
                piece,
                blender_bin=blender_bin,
                fit_box=True,
            )
            cand.post = _post_meta(post)
            _measure(cand, piece, post)
            if plan is not None:
                _apply_material(cand, plan, blender_bin=blender_bin)
        except Exception as exc:  # one failed candidate must not lose the other
            cand.error = f"{type(exc).__name__}: {exc}"[:ERROR_MAX_CHARS]
        runs.append(cand)
    return runs


def provider_call_cost(provider: Provider | None) -> float:
    """Estimated USD of one provider call: Tripo from its credit table
    (``TripoSettings.estimated_cost_usd``), fal from its price table, else 0."""
    settings = getattr(provider, "settings", None)
    estimate = getattr(settings, "estimated_cost_usd", None)
    if callable(estimate):
        return float(estimate())
    endpoint = getattr(provider, "endpoint", None)
    if endpoint is not None:
        from platform_worker.providers.fal import USD_PER_MODEL

        return float(USD_PER_MODEL.get(endpoint, 0.0))
    return 0.0


def material_plan(
    piece_row: dict[str, Any], routing: intake.Routing, photos: list[Path]
) -> MaterialPlan:
    """Which library material this attempt gets: the admin's ``material:<id>`` in
    ``review_note`` wins (any route; ``material:none`` turns detection off); else, for
    provider meshes only, the material named in the name/notes (``detect_material``). E
    keeps the photo projection unless the admin chose (ruling 2026-11-09). The colour target
    is the first photo's mean colour (rembg); failing that, the material's own colour."""
    chosen = intake.material_from_note(piece_row.get("review_note"))
    material_id: str | None = None
    source: str | None = None
    if chosen == intake.MATERIAL_NONE:
        source = "admin_off"
    elif chosen is not None:
        try:
            materials.get_material(chosen)
            material_id, source = chosen, "admin"
        except Exception:
            log.warning("Material desconocido en la nota del admin: %r", chosen)
    if source is None and routing.route == intake.ROUTE_ORGANIC:
        detected = detect_material(
            str(piece_row.get("name") or ""), str(piece_row.get("notes") or "")
        )
        if detected:
            material_id, source = detected, "detected"
    plan = MaterialPlan(material_id, source)
    if material_id is None:
        return plan
    plan.real_size_cm = (
        float(piece_row["width_cm"]),
        float(piece_row["height_cm"]),
        float(piece_row["depth_cm"]),
    )
    try:
        plan.target_rgb = photo_mean_color(photos[0])
    except Exception as exc:
        plan.target_error = f"{type(exc).__name__}: {exc}"[:300]
    return plan


class NoProviderError(RuntimeError):
    """An organic piece arrived and the worker has no provider configured."""


class BudgetExhausted(RuntimeError):
    """The daily provider budget is spent before the first provider call of a piece."""


class PhotoPathError(ValueError):
    """A ``piece_photos.storage_path`` outside ``{user_id}/{piece_id}/``."""


def daily_budget_usd(settings: dict[str, str | None] | None = None) -> float:
    """``WORKER_DAILY_BUDGET_USD`` (default 20); an unreadable value falls back to 20."""
    env = settings if settings is not None else load_settings()
    raw = env.get("WORKER_DAILY_BUDGET_USD")
    try:
        value = float(str(raw).replace(",", ".")) if raw else DEFAULT_DAILY_BUDGET_USD
    except ValueError:
        log.warning("WORKER_DAILY_BUDGET_USD no es un número (%r); uso 20", raw)
        return DEFAULT_DAILY_BUDGET_USD
    return value if value >= 0 else DEFAULT_DAILY_BUDGET_USD


def next_madrid_midnight(now: datetime | None = None) -> datetime:
    """Next 00:00 Europe/Madrid (the budget day boundary), as an aware datetime."""
    local = (now or _utcnow()).astimezone(MADRID)
    tomorrow = (local + timedelta(days=1)).date()
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=MADRID)


# Day (Madrid) of the last budget notice sent by this process: the admin hears it once.
_budget_notice_day: date | None = None


def storage_prefix(piece_id: str, attempt: int, candidate: int, *, selected: bool) -> str:
    """Selected candidate: ``{piece_id}/{attempt}`` (Global Constraints paths); every other
    candidate: ``{piece_id}/{attempt}/cand_{n}``. Consumers read the row's paths."""
    base = f"{piece_id}/{attempt}"
    return base if selected else f"{base}/cand_{candidate}"


@dataclass
class CandidateOutputs:
    """Local files of one delivered candidate (renders, contact sheet, deliver result)."""

    renders: dict[str, Path]  # harness view → PNG (every ``VIEWS`` entry)
    contact: Path
    result: Any  # harness.post.deliver.DeliverResult

    @property
    def deliverable(self) -> bool:
        r = self.result
        return bool(
            r.glb_path is not None and r.usdz_path is not None and r.preview_glb_path is not None
        )

    def deliver_meta(self) -> dict[str, Any]:
        r = self.result
        return {
            "glb_bytes": r.glb_bytes,
            "usdz_bytes": r.usdz_bytes,
            "usdz_error": r.usdz_error,
            "tris_after": r.tris_after,
            "max_tris": r.max_tris,
            "max_tex": r.max_tex,
            "within_limit": r.within_limit,
            "preview_glb_bytes": r.preview_glb_bytes,
            "preview_usdz_bytes": r.preview_usdz_bytes,
            "preview_tris_after": r.preview_tris_after,
            "optimize_error": r.optimize_error,
            "warnings": list(r.warnings or []),
        }


def build_outputs(
    piece: Piece,
    cand: CandidateRun,
    photos: list[Path],
    *,
    blender_bin: Path | None,
    provenance: dict[str, Any],
) -> CandidateOutputs:
    """Renders + contact sheet, and ONE ``deliver`` (GLB 2K + USDZ + preview GLB/USDZ,
    ``strict=False``: an optimizer failure ships the plain GLB with a warning)."""
    renders_dir = cand.cand_dir / "renders"
    rendered = render_views(cand.cand_dir / POST_GLB, renders_dir, blender_bin=blender_bin)
    by_view = {p.stem: p for p in rendered}
    contact = contact_sheet(
        [by_view[view] for view in RENDER_VIEWS],
        photos[0] if photos else None,
        renders_dir / CONTACT_FILENAME,
    )
    result = deliver(
        cand.cand_dir,
        piece,
        max_tris=DELIVER_MAX_TRIS,
        max_tex=DELIVER_MAX_TEX,
        out_dir=cand.cand_dir / "deliver",
        blender_bin=blender_bin,
        provenance=provenance,
        preview=True,
        preview_max_tris=PREVIEW_MAX_TRIS,
        preview_max_tex=PREVIEW_MAX_TEX,
        strict=False,
    )
    return CandidateOutputs(by_view, contact, result)


def upload_outputs(storage: Any, outputs: CandidateOutputs, *, prefix: str) -> dict[str, Any]:
    """Upload one candidate under ``prefix``: ``models`` (``model_web.glb``,
    ``model.usdz``), ``previews`` (``model_preview.glb`` + ``model_preview.usdz``) and
    ``renders`` (four views + contact sheet). Returns the bucket-relative paths."""
    r = outputs.result
    glb_path = storage.upload("models", f"{prefix}/model_web.glb", r.glb_path)
    usdz_path = (
        storage.upload("models", f"{prefix}/model.usdz", r.usdz_path)
        if r.usdz_path is not None
        else None
    )
    preview_path = (
        storage.upload("previews", f"{prefix}/{PREVIEW_FILENAME}", r.preview_glb_path)
        if r.preview_glb_path is not None
        else None
    )
    if r.preview_usdz_path is not None:
        storage.upload("previews", f"{prefix}/{PREVIEW_USDZ_FILENAME}", r.preview_usdz_path)
    render_paths: dict[str, str] = {}
    for harness_view, name in RENDER_VIEWS.items():
        render_paths[name] = storage.upload(
            "renders", f"{prefix}/{name}.png", outputs.renders[harness_view]
        )
    render_paths["contact"] = storage.upload(
        "renders", f"{prefix}/{CONTACT_FILENAME}", outputs.contact
    )
    return {
        "glb_path": glb_path,
        "usdz_path": usdz_path,
        "preview_path": preview_path,
        "preview_usdz": r.preview_usdz_path is not None,
        "render_paths": render_paths,
    }


def notify_status(
    piece_id: str,
    status: str,
    *,
    settings: dict[str, str | None] | None = None,
    client: httpx.Client | None = None,
) -> bool:
    """POST ``{pieceId, status}`` to the web's ``/api/internal/notify`` (admin heads-up on
    ``review``, ``failed`` and ``budget``). Only when ``NOTIFY_URL`` and
    ``WORKER_SHARED_SECRET`` are set; returns whether the web accepted it.
    Never raises: a lost notice must not fail a finished piece."""
    try:
        # Inside the try: a broken .env must never turn a reviewed piece into ``failed``.
        env = settings if settings is not None else load_settings()
        url, secret = env.get("NOTIFY_URL"), env.get("WORKER_SHARED_SECRET")
        if not url or not secret:
            return False
        post = client.post if client is not None else httpx.post
        response = post(
            url,
            json={"pieceId": piece_id, "status": status},
            headers={"Authorization": f"Bearer {secret}"},
            timeout=NOTIFY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception as exc:
        log.warning("No se pudo avisar a la web de la pieza %s (%s): %s", piece_id, status, exc)
        return False
    log.info("Aviso enviado a la web: pieza %s en %s", piece_id, status)
    return True


def _fail(db: Any, piece_id: str, message: str, *, provider_cost_usd: float | None = None) -> str:
    """Mark the piece ``failed`` (technical ``error``; the customer sees a fixed message) and
    alert the admin. ``provider_cost_usd`` is the new accumulated cost of failed attempts
    (written only when given). A DB error here is logged, never raised (the piece then stays
    ``generating`` and the stale sweep requeues it)."""
    fields: dict[str, Any] = {"status": STATUS_FAILED, "error": message[:ERROR_MAX_CHARS]}
    if provider_cost_usd is not None:
        fields["provider_cost_usd"] = round(provider_cost_usd, 4)
    try:
        db.update_piece(piece_id, **fields)
    except Exception:
        log.exception("No se pudo marcar la pieza %s como fallida", piece_id)
        return STATUS_FAILED
    notify_status(piece_id, STATUS_FAILED)
    return STATUS_FAILED


def _heartbeat(db: Any, piece_id: str) -> None:
    """Refresh ``claimed_at`` so a long piece is never taken for orphaned. Never raises."""
    try:
        db.update_piece(piece_id, claimed_at=_utcnow().isoformat())
    except Exception as exc:
        log.warning("No se pudo renovar claimed_at de la pieza %s: %s", piece_id, exc)


def _defer_for_budget(db: Any, piece_id: str) -> str:
    """Back to ``queued`` until the next Madrid midnight; the admin is told once a day."""
    global _budget_notice_day
    db.update_piece(
        piece_id,
        status=STATUS_QUEUED,
        claimed_at=None,
        error=BUDGET_MESSAGE,
        not_before=next_madrid_midnight().isoformat(),
    )
    today = _utcnow().astimezone(MADRID).date()
    if _budget_notice_day != today and notify_status(piece_id, NOTICE_BUDGET):
        _budget_notice_day = today
    return STATUS_QUEUED


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _created_at(piece_row: dict[str, Any]) -> datetime | None:
    raw = piece_row.get("created_at")
    if isinstance(raw, datetime):
        value = raw
    else:
        try:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _wait_for_photos(db: Any, piece_row: dict[str, Any]) -> str:
    """Back to ``queued`` while the piece is younger than ``PHOTOS_GRACE`` (photos still
    uploading), else ``needs_photos``. A row without a readable ``created_at`` is never
    re-queued, so the wait is always bounded."""
    piece_id = str(piece_row["id"])
    created = _created_at(piece_row)
    if created is None or _utcnow() - created >= PHOTOS_GRACE:
        db.update_piece(piece_id, status=STATUS_NEEDS_PHOTOS, error=NO_PHOTOS_ERROR)
        return STATUS_NEEDS_PHOTOS
    db.update_piece(piece_id, status=STATUS_QUEUED, claimed_at=None, error=WAITING_PHOTOS_MESSAGE)
    return STATUS_QUEUED


def interpretation_meta(interpretation: Interpretation, routing: intake.Routing) -> dict[str, Any]:
    """``meta["interpretation"]``: the photo reading, the effective answers and where each
    one came from, and the customer-vs-photo conflicts."""
    eff = routing.effective
    return {
        **interpretation.to_dict(),
        "effective": {
            key: eff.get(key)
            for key in ("kind", "rectilinear", "support", "routing_kind", "pedestal_params")
        },
        "source": dict(eff.get("source") or {}),
        "conflict": list(eff.get("conflict") or []),
    }


def routing_meta(routing: intake.Routing) -> dict[str, Any]:
    return {
        "route": routing.route,
        "kind": routing.kind,
        "params": routing.params,
        "reasons": routing.reasons,
        "photo_overrides_support": routing.photo_overrides_support,
    }


def _make_judge(
    settings: dict[str, str | None],
    piece: Piece,
    photos: list[Path],
    outputs: CandidateOutputs,
    metrics: GeometryMetrics | None,
    tolerance: float,
) -> autopublish.Judge | None:
    """The VLM judge of the selected candidate when ``ANTHROPIC_API_KEY`` is set."""
    key = settings.get("ANTHROPIC_API_KEY")
    if not key:
        return None

    def judge() -> dict[str, Any]:
        from harness.clients.vlm import VLMClient

        renders = [outputs.renders[view] for view in VIEWS if view in outputs.renders]
        return judge_candidate(
            VLMClient(api_key=key, allow_fallback=False),
            blind_id=f"pieza-{piece.id[:8]}",
            photos=photos,
            renders=renders,
            geometry=metrics,
            tolerance=tolerance,
        )

    return judge


def _manual_without_model(
    db: Any,
    piece_row: dict[str, Any],
    *,
    attempt: int,
    interpretation: Interpretation,
    routing: intake.Routing,
    dimension_warnings: list[str],
) -> str:
    """No model can be built yet (organic, no provider, unsure reading): the piece goes to
    the admin with the reasons in a placeholder ``piece_models`` row (no files, never
    deliverable) so the review screen shows the interpretation."""
    piece_id = str(piece_row["id"])
    reasons = list(routing.reasons)
    db.delete_models(piece_id, attempt)
    db.insert_model(
        {
            "piece_id": piece_id,
            "attempt": attempt,
            "provider": None,
            "candidate": 0,
            "meta": {
                "error": "Sin modelo: " + "; ".join(reasons),
                "interpretation": interpretation_meta(interpretation, routing),
                "dimension_warnings": dimension_warnings,
                "routing": routing_meta(routing),
                "warnings": list(dimension_warnings),
                "auto_review": autopublish.AutoReview(
                    autopublish.DECISION_MANUAL, autopublish.GATE_RULES, reasons
                ).to_dict(),
            },
            "selected": False,
        }
    )
    if not _finish(db, piece_id, attempt, status=STATUS_REVIEW, error=None):
        return STATUS_SUPERSEDED
    notify_status(piece_id, STATUS_REVIEW)
    return STATUS_REVIEW


def _finish(db: Any, piece_id: str, attempt: int, **fields: Any) -> bool:
    """The final status write as a compare-and-swap on ``generating`` + this attempt, so a
    piece an admin or the customer moved meanwhile is never overwritten (False: nothing
    changed; the caller must not publish nor notify)."""
    changed = db.update_piece_if(
        piece_id, {"status": STATUS_GENERATING, "attempt": attempt}, **fields
    )
    if not changed:
        log.warning(
            "La pieza %s ya no está en generación en el intento %d: no se publica ni se avisa",
            piece_id,
            attempt,
        )
    return bool(changed)


def process_piece(
    db: Any,
    storage: Any,
    piece_row: dict[str, Any],
    *,
    provider: Provider | None,
    workdir: Path,
    blender_bin: Path | None,
    budget_usd: float | None = None,
    interpreter: Interpreter | None = None,
    settings: dict[str, str | None] | None = None,
) -> str:
    """Run one claimed piece; returns the final status (``ready|review|needs_photos|
    rejected|failed``), or ``queued`` when the piece had no photos yet or the daily
    provider budget (``budget_usd``, default ``WORKER_DAILY_BUDGET_USD``) is spent and it
    went back to the queue.

    ``interpreter`` reads the photos (default :class:`SilhouetteInterpreter`); ``settings``
    (default ``load_settings()``) gives ``AUTO_PUBLISH``, ``ANTHROPIC_API_KEY`` and the
    budget.

    Never raises for a piece-level problem: every failure ends in ``failed`` with a technical
    ``error`` (the traceback goes to ``<work>/error.log``) and a notice to the admin."""
    piece_id = str(piece_row["id"])
    attempt = int(piece_row.get("attempt") or 1)
    work = piece_workdir(workdir, piece_id, attempt)
    start = time.monotonic()
    prior_cost = float(piece_row.get("provider_cost_usd") or 0)
    runs: list[CandidateRun] = []
    # Candidates whose ``piece_models`` row exists: their cost already counts in the day's
    # spend through that row, so a failure only adds the cost of the others.
    written: set[int] = set()

    def failed_cost() -> float | None:
        """Accumulated provider cost to record on failure (None: nothing new to add)."""
        spent = sum(c.cost_usd for c in runs if c.index not in written)
        return prior_cost + spent if spent else None

    try:
        env = settings if settings is not None else load_settings()
        excluded = intake.excluded_reasons(piece_row)
        if excluded:
            # Out of scope: closed at no cost with the reason (never a photo problem).
            db.update_piece(
                piece_id, status=STATUS_REJECTED, reject_reason="\n".join(excluded), error=None
            )
            return STATUS_REJECTED

        try:
            user_id = piece_row.get("user_id")
            photos = download_photos(
                db, storage, piece_id, work, user_id=str(user_id) if user_id else None
            )
        except Exception as exc:
            return _fail(db, piece_id, f"No se pudieron descargar las fotos: {exc}")

        if not photos:
            return _wait_for_photos(db, piece_row)

        problems = intake.check(piece_row, photos)
        if problems:
            db.update_piece(piece_id, status=STATUS_NEEDS_PHOTOS, error=intake.explain(problems))
            return STATUS_NEEDS_PHOTOS

        photos = [oriented_copy(p, work / "oriented") for p in photos]
        width, height, depth = (
            float(piece_row["width_cm"]),
            float(piece_row["height_cm"]),
            float(piece_row["depth_cm"]),
        )
        interpretation = (interpreter or SilhouetteInterpreter()).interpret(
            photos,
            width_cm=width,
            height_cm=height,
            depth_cm=depth,
            name=str(piece_row.get("name") or ""),
            notes=str(piece_row.get("notes") or ""),
        )
        routing = intake.decide_route(
            piece_row, interpretation, provider_available=provider is not None
        )
        dimension_warnings = check_dimensions(interpretation, width, height, depth)
        piece = intake.build_piece(piece_row, photos, routing)
        if routing.route == intake.ROUTE_E:
            route = "E"
        else:
            route = provider.name if provider is not None else "sin proveedor"
        db.update_piece(piece_id, route=route)

        if routing.route == intake.ROUTE_MANUAL:
            return _manual_without_model(
                db, piece_row, attempt=attempt, interpretation=interpretation,
                routing=routing, dimension_warnings=dimension_warnings,
            )  # fmt: skip
        plan = material_plan(piece_row, routing, photos)

        budget = budget_usd if budget_usd is not None else daily_budget_usd(env)
        call_cost = provider_call_cost(provider)

        def before_provider_call(index: int, spent: float) -> bool:
            _heartbeat(db, piece_id)
            try:
                today = float(db.provider_spend_today())
            except Exception as exc:  # fail open: a DB blip must not stall every piece
                log.warning("No se pudo leer el gasto del día: %s", exc)
                return True
            # The next call's estimated cost (Tripo: its credit table) must fit too.
            return today + spent < budget and today + spent + call_cost <= budget

        try:
            runs = generate_candidates(
                piece, routing, photos, work,
                provider=provider, blender_bin=blender_bin,
                before_provider_call=before_provider_call, material=plan,
            )  # fmt: skip
        except NoProviderError as exc:
            return _fail(db, piece_id, str(exc))
        except BudgetExhausted:
            return _defer_for_budget(db, piece_id)

        ok = [c for c in runs if c.error is None and c.max_error is not None]
        if not ok:
            errors = "; ".join(c.error for c in runs if c.error) or "sin candidatos"
            return _fail(
                db,
                piece_id,
                f"No se pudo generar ningún modelo: {errors}",
                provider_cost_usd=failed_cost(),
            )
        organic = routing.route != intake.ROUTE_E
        provider_name = "parametric" if not organic else provider.name  # type: ignore[union-attr]
        # Every successful candidate is delivered so the admin can pick either one; a
        # delivery failure only loses that candidate.
        outputs: dict[int, CandidateOutputs] = {}
        for cand in sorted(ok, key=lambda c: c.max_error):  # type: ignore[arg-type,return-value]
            _heartbeat(db, piece_id)
            provenance = {
                "variant": route,
                "candidate": cand.index,
                "attempt": attempt,
                "provider": provider_name,
            }
            try:
                outputs[cand.index] = build_outputs(
                    piece, cand, photos, blender_bin=blender_bin, provenance=provenance
                )
            except Exception as exc:  # renders, contact sheet or delivery: lose this one only
                stage = "Entrega" if isinstance(exc, DeliverError) else "Renders"
                cand.error = f"{stage}: {type(exc).__name__}: {exc}"[:ERROR_MAX_CHARS]
                with (work / "error.log").open("a", encoding="utf-8") as fh:
                    fh.write(f"candidato {cand.index}\n{traceback.format_exc()}\n")
        delivered = [c for c in ok if c.index in outputs]
        if not delivered:
            errors = "; ".join(c.error for c in ok if c.error) or "sin candidatos"
            return _fail(
                db,
                piece_id,
                f"No se pudo renderizar ni entregar ningún modelo: {errors}",
                provider_cost_usd=failed_cost(),
            )
        selected = min(
            delivered,
            key=lambda c: (not outputs[c.index].deliverable, c.max_error),  # type: ignore[arg-type,return-value]
        )
        files: dict[int, dict[str, Any]] = {}
        for cand in delivered:
            prefix = storage_prefix(piece_id, attempt, cand.index, selected=cand is selected)
            files[cand.index] = upload_outputs(storage, outputs[cand.index], prefix=prefix)

        interp_meta = interpretation_meta(interpretation, routing)

        def warnings_of(cand: CandidateRun) -> list[str]:
            out = list(dimension_warnings)
            out += [str(w) for w in (cand.gen_meta or {}).get("warnings") or []]
            if plan.material_id and plan.target_error and cand.material is not None:
                out.append(
                    f"No se pudo medir el color de la foto ({plan.target_error}): el material "
                    f"«{plan.material_id}» conserva su color de biblioteca"
                )
            out += [str(w) for w in (cand.material or {}).get("warnings") or []]
            if cand.index in outputs:
                result = outputs[cand.index].result
                out += list(result.warnings or [])
                if result.within_limit is False:
                    mb = f"{(result.glb_bytes or 0) / 1_000_000:.1f}".replace(".", ",")
                    out.append(
                        f"El GLB pesa {mb} MB tras el reintento: supera el límite de "
                        f"{result.size_limit_bytes / 1_000_000:.0f} MB"
                    )
            return out

        tolerance = resolve_scale_tolerance()
        selected_files = files[selected.index]
        review = autopublish.decide(
            enabled=autopublish.auto_publish_enabled(env),
            attempt=attempt,
            review_note=piece_row.get("review_note"),
            route=routing.route,
            deliverable=bool(
                selected_files["glb_path"]
                and selected_files["usdz_path"]
                and selected_files["preview_path"]
            ),
            max_error=selected.max_error,
            tolerance=tolerance,
            routing=routing,
            interpretation=interpretation,
            conflicts=list(routing.effective.get("conflict") or []),
            warnings=warnings_of(selected),
            judge=_make_judge(
                env, piece, photos, outputs[selected.index], selected.metrics, tolerance
            ),
        )

        # Re-processing an attempt never leaves duplicates; the selected row goes last so
        # "newest row of the latest attempt" (admin_review_queue) is the selected one.
        db.delete_models(piece_id, attempt)
        for cand in sorted(runs, key=lambda c: (c is selected, c.index)):
            is_selected = cand is selected
            cand_files = files.get(cand.index)
            meta: dict[str, Any] = {
                "route": routing.route,
                "route_reason": "; ".join(routing.reasons),
                "provider": provider_name,
                "candidate": cand.index,
                "post": cand.post,
                "geometry": cand.geometry,
                "generation": cand.gen_meta,
                "seconds": round(cand.seconds, 3),
                "interpretation": interp_meta,
                "dimension_warnings": dimension_warnings,
                "routing": routing_meta(routing),
                "material": cand.material or plan.to_dict(),
                "warnings": warnings_of(cand),
            }
            if cand.error:
                meta["error"] = cand.error
            if cand.index in outputs:
                meta["deliver"] = {
                    **outputs[cand.index].deliver_meta(),
                    "preview_usdz": bool(cand_files and cand_files["preview_usdz"]),
                }
            if is_selected:
                meta["total_seconds"] = round(time.monotonic() - start, 3)
                meta["auto_review"] = review.to_dict()
            db.insert_model(
                {
                    "piece_id": piece_id,
                    "attempt": attempt,
                    "provider": provider_name,
                    "candidate": cand.index,
                    "preview_path": cand_files["preview_path"] if cand_files else None,
                    "glb_path": cand_files["glb_path"] if cand_files else None,
                    "usdz_path": cand_files["usdz_path"] if cand_files else None,
                    "render_paths": cand_files["render_paths"] if cand_files else None,
                    "meta": meta,
                    "max_error": cand.max_error,
                    "cost_usd": cand.cost_usd,
                    "selected": is_selected,
                }
            )
            written.add(cand.index)
        # Compare-and-swap on generating + attempt: nothing is published nor notified when
        # an admin or the customer moved the piece meanwhile. ``review_note`` is kept.
        status = STATUS_READY if review.auto else STATUS_REVIEW
        extra = {"reject_reason": None} if review.auto else {}
        if not _finish(db, piece_id, attempt, status=status, error=None, **extra):
            return STATUS_SUPERSEDED
        notify_status(piece_id, status, settings=env)
        return status
    except Exception as exc:
        (work / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        return _fail(
            db,
            piece_id,
            f"Error del worker: {type(exc).__name__}: {exc}",
            provider_cost_usd=failed_cost(),
        )
