"""Synthetic orthographic views from one cleaned photo, plus a silhouette sanity check.

Front view choice: the cleaned photo is the only real evidence of the piece, so it is used as
``front`` when its silhouette already matches width/height within tolerance (i.e. it looks
frontal). Otherwise (typically a 3/4 product shot) Gemini also synthesises the front view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from harness.core.models import Piece

VIEW_NAMES = ("front", "side", "back", "three_quarter")
ASPECT_TOLERANCE = 0.10
WHITE_THRESHOLD = 240  # a pixel with every RGB channel above this counts as background
MIN_VIEWS = 2
VIEWS_DIRNAME = "views"

_VIEW_DESCRIPTIONS = {
    "front": (
        "a straight-on orthographic FRONT view (camera perpendicular to the front face, "
        "no perspective)",
        "width {w:g} cm × height {h:g} cm",
    ),
    "side": (
        "a straight-on orthographic SIDE view from the left (camera perpendicular to the "
        "side face, no perspective)",
        "depth {d:g} cm × height {h:g} cm",
    ),
    "back": (
        "a straight-on orthographic BACK view (camera perpendicular to the back face, "
        "no perspective)",
        "width {w:g} cm × height {h:g} cm",
    ),
    "three_quarter": (
        "an orthographic THREE-QUARTER view from the front-left at 45° and slightly above",
        "width {w:g} cm, depth {d:g} cm and height {h:g} cm",
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
        "Pure white background (#FFFFFF), no shadows, no reflections, no floor, no additional "
        "objects, props or text. Neutral, even studio lighting. Centre the whole object in the "
        "frame with a small margin, nothing cropped."
        + (f" Object: {piece.description}." if piece.description else "")
    )


def silhouette_aspect(image: Path, white_threshold: int = WHITE_THRESHOLD) -> float | None:
    """Width/height of the bounding box of non-white pixels; ``None`` if the image is blank."""
    with Image.open(image) as img:
        rgb = img.convert("RGB")
    # Per channel: 255 where the channel is darker than the threshold, then OR the channels.
    mask = rgb.point(lambda v: 255 if v <= white_threshold else 0).convert("L")
    mask = mask.point(lambda v: 255 if v > 0 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    return (right - left) / (bottom - top)


def expected_aspect(view: str, piece: Piece) -> float | None:
    """Expected silhouette width/height per view; ``None`` when not checkable (3/4 view)."""
    if view in ("front", "back"):
        return piece.width_cm / piece.height_cm
    if view == "side":
        return piece.depth_cm / piece.height_cm
    return None


def _check_one(view: str, path: Path, piece: Piece) -> dict[str, Any]:
    expected = expected_aspect(view, piece)
    aspect = silhouette_aspect(path)
    result: dict[str, Any] = {"path": str(path), "aspect": aspect, "expected": expected}
    if aspect is None:
        return {**result, "ok": False, "error": None, "reason": f"{view}: imagen sin objeto"}
    if expected is None:
        return {**result, "ok": True, "error": None, "reason": f"{view}: sin medida que comprobar"}
    error = abs(aspect / expected - 1)
    ok = error <= ASPECT_TOLERANCE
    reason = (
        f"{view}: proporción {aspect:.3f} vs {expected:.3f} esperada "
        f"(desviación {error:.1%}, tolerancia {ASPECT_TOLERANCE:.0%})"
    )
    return {**result, "ok": ok, "error": error, "reason": reason}


@dataclass
class ViewCheck:
    passed: dict[str, Path]  # views to feed downstream, in VIEW_NAMES order
    checks: dict[str, dict[str, Any]]  # per view: path, aspect, expected, error, ok, reason
    degraded: bool = False  # True → multiview abandoned, front only
    reasons: list[str] = field(default_factory=list)  # why views were dropped / degraded

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": {k: str(v) for k, v in self.passed.items()},
            "checks": self.checks,
            "degraded": self.degraded,
            "reasons": self.reasons,
        }


def check_views(views: dict[str, Path], piece: Piece) -> ViewCheck:
    """Drop views whose silhouette aspect deviates > 10 % from the piece's measurements
    (front/back vs width/height, side vs depth/height; 3/4 only needs a visible object).
    With fewer than 2 survivors, or without a passing front, degrade to the front view only."""
    ordered = [v for v in VIEW_NAMES if v in views] + [v for v in views if v not in VIEW_NAMES]
    checks = {v: _check_one(v, Path(views[v]), piece) for v in ordered}
    passed = {v: Path(views[v]) for v in ordered if checks[v]["ok"]}
    reasons = [c["reason"] for c in checks.values() if not c["ok"]]

    degraded = False
    if "front" not in passed:
        degraded = True
        reasons.append("la vista frontal no pasa la comprobación: se degrada a solo frontal")
    elif len(passed) < MIN_VIEWS:
        degraded = True
        reasons.append(
            f"solo {len(passed)} vista(s) válida(s) (< {MIN_VIEWS}): se degrada a solo frontal"
        )
    if degraded:
        passed = {"front": Path(views["front"])} if "front" in views else {}
    return ViewCheck(passed=passed, checks=checks, degraded=degraded, reasons=reasons)


def front_is_frontal(clean_front: Path, piece: Piece) -> bool:
    return bool(_check_one("front", Path(clean_front), piece)["ok"])


def generate_views(
    clean_front: Path,
    piece: Piece,
    workdir: Path,
    *,
    client: ImageEditor | None = None,
) -> dict[str, Path]:
    """Write ``front``, ``side``, ``back`` and ``three_quarter`` PNGs under ``workdir/views``.

    ``front`` is a copy of the cleaned photo when it already looks frontal (see module doc);
    every other view is one ``client.edit`` call on the cleaned photo. ``client`` defaults to a
    ``GeminiImageClient`` built from settings; read its ``calls`` for costs.
    """
    if client is None:
        from harness.clients.gemini_image import GeminiImageClient
        from harness.core.config import Settings

        client = GeminiImageClient(Settings.load().gemini_api_key)

    out = Path(workdir) / VIEWS_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    views: dict[str, Path] = {}
    for view in VIEW_NAMES:
        dst = out / f"{view}.png"
        if view == "front" and front_is_frontal(clean_front, piece):
            with Image.open(clean_front) as img:
                img.convert("RGB").save(dst)
        else:
            client.edit(Path(clean_front), view_prompt(view, piece), dst)
        views[view] = dst
    return views


__all__ = [
    "ASPECT_TOLERANCE",
    "VIEW_NAMES",
    "ViewCheck",
    "check_views",
    "expected_aspect",
    "front_is_frontal",
    "generate_views",
    "silhouette_aspect",
    "view_prompt",
]
