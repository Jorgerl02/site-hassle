"""Synthetic orthographic views from one cleaned photo, plus a silhouette sanity check.

The view set mirrors Tripo's multiview slots: ``front, left, back, right`` (in that order).
Every view, front included, is synthesised by the image model from the cleaned photo on a flat
pure green (#00FF00) background, so the silhouette can be keyed on green and light/white/chrome
furniture keeps its edges. The cleaned real photo (white background) is the front-only fallback.

Slot rule: only slot-correct prefixes go downstream — ``[front, left]``, ``[front, left, back]``
or ``[front, left, back, right]``. A view that is missing or fails its check is dropped together
with every later slot. Fewer than 2 surviving views → degrade to the cleaned photo alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
from PIL import Image

from harness.clients.gemini_image import GeminiImageError
from harness.core.models import Piece

VIEW_NAMES = ("front", "left", "back", "right")  # == Tripo MULTIVIEW_SLOTS
ASPECT_TOLERANCE = 0.10
MIN_VIEWS = 2
VIEWS_DIRNAME = "views"

SilhouetteMethod = Literal["green", "white"]
GREEN_KEY = (0, 255, 0)
GREEN_DISTANCE = 120.0  # RGB Euclidean distance to pure green below which a pixel is background
WHITE_THRESHOLD = 240  # "white" method: every channel above this counts as background

_VIEW_DESCRIPTIONS = {
    "front": (
        "a straight-on orthographic FRONT view (camera perpendicular to the front face, "
        "no perspective)",
        "width {w:g} cm × height {h:g} cm",
    ),
    "left": (
        "a straight-on orthographic LEFT side view (camera on the object's left, perpendicular "
        "to the side face, no perspective)",
        "depth {d:g} cm × height {h:g} cm",
    ),
    "back": (
        "a straight-on orthographic BACK view (camera perpendicular to the back face, "
        "no perspective)",
        "width {w:g} cm × height {h:g} cm",
    ),
    "right": (
        "a straight-on orthographic RIGHT side view (camera on the object's right, "
        "perpendicular to the side face, no perspective)",
        "depth {d:g} cm × height {h:g} cm",
    ),
}


class ImageEditor(Protocol):
    def edit(self, image: Path, prompt: str, dst: Path) -> Path: ...


def view_prompt(view: str, piece: Piece) -> str:
    """Prompt asking for ``view`` of the SAME piece shown in the reference photo."""
    framing, visible = _VIEW_DESCRIPTIONS[view]
    dims = dict(w=piece.width_cm, h=piece.height_cm, d=piece.depth_cm)
    return (
        f"Using the attached photo as the only reference, render {framing} of the SAME object: "
        f"identical design, materials, colours and details — do not redesign or restyle it. "
        f"The real piece measures {piece.width_cm:g} cm wide, {piece.height_cm:g} cm high and "
        f"{piece.depth_cm:g} cm deep; in this view the visible silhouette must keep the "
        f"proportions {visible.format(**dims)}. "
        "Flat, uniform pure green background (#00FF00, chroma key) filling the whole frame, "
        "no gradient, no shadows, no reflections, no floor, no additional objects, props or "
        "text. Neutral, even studio lighting. Centre the whole object in the frame with a "
        "small margin, nothing cropped."
        + (f" Object: {piece.description}." if piece.description else "")
    )


def _object_mask(image: Path, method: SilhouetteMethod) -> np.ndarray:
    with Image.open(image) as img:
        rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    if method == "green":
        distance = np.sqrt(((rgb - np.array(GREEN_KEY, dtype=np.float32)) ** 2).sum(axis=-1))
        return distance > GREEN_DISTANCE
    return (rgb <= WHITE_THRESHOLD).any(axis=-1)


def silhouette_aspect(image: Path, method: SilhouetteMethod = "green") -> float | None:
    """Width/height of the object's bounding box; ``None`` if no object pixels.

    ``green``: background keyed on #00FF00 (synthesised views). ``white``: background is any
    pixel with every channel > 240 (the cleaned real photo)."""
    mask = _object_mask(image, method)
    rows, cols = np.flatnonzero(mask.any(axis=1)), np.flatnonzero(mask.any(axis=0))
    if rows.size == 0:
        return None
    return float((cols[-1] - cols[0] + 1) / (rows[-1] - rows[0] + 1))


def expected_aspect(view: str, piece: Piece) -> float:
    """Expected silhouette width/height: front/back = width/height, left/right = depth/height."""
    if view in ("front", "back"):
        return piece.width_cm / piece.height_cm
    return piece.depth_cm / piece.height_cm


def _check_one(view: str, path: Path, piece: Piece, method: SilhouetteMethod) -> dict[str, Any]:
    expected = expected_aspect(view, piece)
    aspect = silhouette_aspect(path, method)
    result: dict[str, Any] = {
        "path": str(path),
        "silhouette_method": method,
        "aspect": aspect,
        "expected": expected,
    }
    if aspect is None:
        return {**result, "ok": False, "error": None, "reason": f"{view}: imagen sin objeto"}
    error = float(abs(aspect / expected - 1))
    ok = bool(error <= ASPECT_TOLERANCE)
    reason = (
        f"{view}: proporción {aspect:.3f} vs {expected:.3f} esperada "
        f"(desviación {error:.1%}, tolerancia {ASPECT_TOLERANCE:.0%})"
    )
    return {**result, "ok": ok, "error": error, "reason": reason}


@dataclass
class ViewCheck:
    passed: dict[str, Path]  # images to feed Tripo, in slot order (front, left, back, right)
    checks: dict[str, dict[str, Any]]  # per view: path, silhouette_method, aspect, ok, reason…
    degraded: bool = False  # True → multiview abandoned, cleaned photo only
    reasons: list[str] = field(default_factory=list)  # why views were dropped / degraded

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": {k: str(v) for k, v in self.passed.items()},
            "checks": self.checks,
            "degraded": self.degraded,
            "reasons": self.reasons,
        }


def check_views(
    views: dict[str, Path],
    piece: Piece,
    *,
    fallback_front: Path | None = None,
    method: SilhouetteMethod = "green",
) -> ViewCheck:
    """Check every synthesised view (aspect within 10 % of the measurements) and keep the
    longest slot-correct prefix of ``front, left, back, right`` that passes. With fewer than
    2 views kept, degrade to ``{"front": fallback_front}`` (the cleaned real photo; empty if
    not given) — never to a synthesised front that failed its check."""
    checks = {v: _check_one(v, Path(views[v]), piece, method) for v in VIEW_NAMES if v in views}
    reasons = [c["reason"] for c in checks.values() if not c["ok"]]

    passed: dict[str, Path] = {}
    for slot_index, view in enumerate(VIEW_NAMES):
        if view in checks and checks[view]["ok"]:
            passed[view] = Path(views[view])
            continue
        if view not in views:
            reasons.append(f"{view}: no se generó")
        for later in VIEW_NAMES[slot_index + 1 :]:
            if later in checks and checks[later]["ok"]:
                checks[later]["dropped_by_prefix"] = True
                reasons.append(f"{later}: descartada porque falla una vista anterior ({view})")
        break

    degraded = len(passed) < MIN_VIEWS
    if degraded:
        reasons.append(
            f"solo {len(passed)} vista(s) en orden de slots (< {MIN_VIEWS}): "
            "se degrada a solo la foto limpia"
        )
        passed = {"front": Path(fallback_front)} if fallback_front is not None else {}
    return ViewCheck(passed=passed, checks=checks, degraded=degraded, reasons=reasons)


def generate_views(
    clean_front: Path,
    piece: Piece,
    workdir: Path,
    *,
    client: ImageEditor | None = None,
) -> dict[str, Path]:
    """Synthesise ``front``, ``left``, ``back`` and ``right`` PNGs under ``workdir/views`` with
    one ``client.edit`` call each on the cleaned photo. A view whose call fails
    (``GeminiImageError``, which wraps SDK errors) is skipped; the client still records the
    call and its cost in ``client.calls``. ``client`` defaults to a ``GeminiImageClient``."""
    if client is None:
        from harness.clients.gemini_image import GeminiImageClient
        from harness.core.config import Settings

        client = GeminiImageClient(Settings.load().gemini_api_key)

    out = Path(workdir) / VIEWS_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    views: dict[str, Path] = {}
    for view in VIEW_NAMES:
        dst = out / f"{view}.png"
        try:
            client.edit(Path(clean_front), view_prompt(view, piece), dst)
        except GeminiImageError:
            continue
        views[view] = dst
    return views


__all__ = [
    "ASPECT_TOLERANCE",
    "VIEW_NAMES",
    "ViewCheck",
    "check_views",
    "expected_aspect",
    "generate_views",
    "silhouette_aspect",
    "view_prompt",
]
