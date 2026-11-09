"""One piece end to end: photos → checks → route → generation → post-processing → geometry
→ renders and contact sheet → delivery (GLB 2K + USDZ, preview GLB) → Storage → rows.

Reuses the harness: ``validate_input``/``explain`` (via ``intake``), ``rule_classify``, the
parametric variant E, ``postprocess``, ``measure_candidate``, ``render_views`` and
``deliver``. Organic pieces get ``ORGANIC_CANDIDATES`` candidates from the provider, each
post-processed with the guarded fit-to-box; the lowest ``max_error`` is ``selected``. Every
successful candidate gets renders, contact sheet, GLB 2K + USDZ and preview, so the admin can
pick either: the selected one under ``{piece_id}/{attempt}/``, the others under
``{piece_id}/{attempt}/cand_{n}/`` (see :func:`storage_prefix`).

Storage paths stored in ``piece_models`` are relative to their bucket (``models``:
``glb_path``/``usdz_path``; ``previews``: ``preview_path``; ``renders``: ``render_paths``).
"""

from __future__ import annotations

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

from harness.core.models import Piece
from harness.eval.geometry import measure_candidate
from harness.eval.render import render_views
from harness.post.blender_post import postprocess
from harness.post.deliver import deliver
from harness.prep.clean import clean_image
from harness.variants.e_parametric import ParametricVariant
from harness.variants.f_router import rule_classify
from platform_worker import intake
from platform_worker.config import load_settings
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
BUDGET_MESSAGE = "Presupuesto diario agotado; se reintenta mañana"
MADRID = ZoneInfo("Europe/Madrid")

# A piece can be claimed the instant it is inserted, before its ``piece_photos`` rows exist:
# while it is younger than ``PHOTOS_GRACE`` (from ``created_at``) it goes back to ``queued``;
# after that it becomes ``needs_photos``. Time-based on purpose: ``claim_next_piece()``
# clears ``error`` on every claim, so a counter kept in the row would never advance.
PHOTOS_GRACE = timedelta(minutes=10)
WAITING_PHOTOS_MESSAGE = "Esperando las fotos de la pieza."
NO_PHOTOS_ERROR = (
    "No se recibieron fotos de la pieza. Vuelve a subir al menos una foto para continuar."
)
PROVIDER_MAX_PX = 2048  # raw-photo fallback for providers (fal base64 limit ≈ 6 MB)
NOTIFY_TIMEOUT_SECONDS = 10.0

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


def generate_candidates(
    piece: Piece,
    piece_row: dict[str, Any],
    route: str,
    photos: list[Path],
    work: Path,
    *,
    provider: Provider | None,
    blender_bin: Path | None,
    before_provider_call: Callable[[int, float], bool] | None = None,
) -> list[CandidateRun]:
    """Candidates of one attempt. For organic pieces ``before_provider_call(index, spent)``
    (``spent`` = this piece's provider cost so far) runs before every provider call: False
    before the first one raises :class:`BudgetExhausted`; later, it stops generating."""
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


def _deliver_candidate(
    piece: Piece,
    cand: CandidateRun,
    photos: list[Path],
    storage: Any,
    *,
    prefix: str,
    blender_bin: Path | None,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Renders + contact sheet, GLB 2K/USDZ and preview of one candidate, uploaded under
    ``prefix`` in ``models``, ``previews`` and ``renders``."""
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


def process_piece(
    db: Any,
    storage: Any,
    piece_row: dict[str, Any],
    *,
    provider: Provider | None,
    workdir: Path,
    blender_bin: Path | None,
    budget_usd: float | None = None,
) -> str:
    """Run one claimed piece; returns the final status (``review|needs_photos|rejected|
    failed``), or ``queued`` when the piece had no photos yet or the daily provider budget
    (``budget_usd``, default ``WORKER_DAILY_BUDGET_USD``) is spent and it went back to the
    queue.

    Never raises for a piece-level problem: every failure ends in ``failed`` with a technical
    ``error`` (the traceback goes to ``<work>/error.log``) and a notice to the admin."""
    piece_id = str(piece_row["id"])
    attempt = int(piece_row.get("attempt") or 1)
    work = piece_workdir(workdir, piece_id, attempt)
    start = time.monotonic()
    prior_cost = float(piece_row.get("provider_cost_usd") or 0)
    runs: list[CandidateRun] = []
    models_written = False

    def failed_cost() -> float | None:
        """Accumulated provider cost to record on failure (None: nothing new to add)."""
        spent = sum(c.cost_usd for c in runs)
        return prior_cost + spent if spent and not models_written else None

    try:
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
        piece = intake.build_piece(piece_row, photos)
        decision = rule_classify(piece)
        organic = decision.route != "E"
        route = "E" if not organic else (provider.name if provider is not None else "sin proveedor")
        db.update_piece(piece_id, route=route)

        budget = budget_usd if budget_usd is not None else daily_budget_usd()

        def before_provider_call(index: int, spent: float) -> bool:
            _heartbeat(db, piece_id)
            try:
                today = float(db.provider_spend_today())
            except Exception as exc:  # fail open: a DB blip must not stall every piece
                log.warning("No se pudo leer el gasto del día: %s", exc)
                return True
            return today + spent < budget

        try:
            runs = generate_candidates(
                piece, piece_row, decision.route if not organic else "organic", photos, work,
                provider=provider, blender_bin=blender_bin,
                before_provider_call=before_provider_call,
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
        selected = min(ok, key=lambda c: c.max_error)
        provider_name = "parametric" if not organic else provider.name  # type: ignore[union-attr]
        # Every successful candidate is delivered so the admin can pick either one.
        delivered: dict[int, dict[str, Any]] = {}
        for cand in ok:
            _heartbeat(db, piece_id)
            prefix = storage_prefix(piece_id, attempt, cand.index, selected=cand is selected)
            provenance = {
                "variant": route,
                "candidate": cand.index,
                "attempt": attempt,
                "provider": provider_name,
            }
            delivered[cand.index] = _deliver_candidate(
                piece, cand, photos, storage,
                prefix=prefix, blender_bin=blender_bin, provenance=provenance,
            )  # fmt: skip

        # Re-processing an attempt never leaves duplicates; the selected row goes last so
        # "newest row of the latest attempt" (admin_review_queue) is the selected one.
        db.delete_models(piece_id, attempt)
        for cand in sorted(runs, key=lambda c: (c is selected, c.index)):
            is_selected = cand is selected
            files = delivered.get(cand.index)
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
            if files is not None:
                meta["deliver"] = files["deliver"]
            if is_selected:
                meta["total_seconds"] = round(time.monotonic() - start, 3)
            db.insert_model(
                {
                    "piece_id": piece_id,
                    "attempt": attempt,
                    "provider": provider_name,
                    "candidate": cand.index,
                    "preview_path": files["preview_path"] if files else None,
                    "glb_path": files["glb_path"] if files else None,
                    "usdz_path": files["usdz_path"] if files else None,
                    "render_paths": files["render_paths"] if files else None,
                    "meta": meta,
                    "max_error": cand.max_error,
                    "cost_usd": cand.cost_usd,
                    "selected": is_selected,
                }
            )
            models_written = True
        db.update_piece(piece_id, status=STATUS_REVIEW, error=None)
        notify_status(piece_id, STATUS_REVIEW)
        return STATUS_REVIEW
    except Exception as exc:
        (work / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        return _fail(
            db,
            piece_id,
            f"Error del worker: {type(exc).__name__}: {exc}",
            provider_cost_usd=failed_cost(),
        )
