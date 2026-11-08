"""Input photo cleaning: background removal, crop to object, square pad on white."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

CROP_MARGIN = 0.08  # fraction of the object's larger side
ALPHA_THRESHOLD = 16  # alpha above this counts as object
MIN_LONG_SIDE_PX = 1000
# The larger side of the object's bounding box (the larger of its two axes) must span at
# least this fraction of the image's longer side. A bbox criterion instead of a pixel-area
# one lets sparse silhouettes (floor lamps, coat racks) pass while still rejecting tiny,
# far-away objects. Requiring it on the short axis too would reject well-framed elongated
# pieces: a 35x176 cm coat rack (p25, 14 % wide) or a 165x60 cm headboard (p12, 21 % tall).
MIN_BBOX_FRACTION = 0.25
# Percentiles of the mask's pixel coordinates used as the robust bounding box, so a stray
# rembg speck far from the object does not inflate it.
BBOX_PERCENTILES = (0.5, 99.5)
BACKGROUND = (255, 255, 255)


@lru_cache(maxsize=1)
def _session():
    from rembg import new_session  # heavy import (onnxruntime); loads rembg's default model

    return new_session()


def _remove_background(image: Image.Image) -> Image.Image:
    """Return an RGBA image whose alpha is the object mask (rembg default model)."""
    from rembg import remove

    return remove(image, session=_session()).convert("RGBA")


def _object_mask(rgba: Image.Image) -> Image.Image:
    return rgba.getchannel("A").point(lambda a: 255 if a > ALPHA_THRESHOLD else 0)


def clean_image(src: Path, dst: Path, size: int = 1024) -> Path:
    """Remove the background, crop to the alpha bbox with 8 % margin, pad to a square
    on a neutral white background and resize to ``size``×``size``. Writes ``dst``."""
    with Image.open(src) as img:
        rgba = _remove_background(img.convert("RGB"))

    bbox = _object_mask(rgba).getbbox()
    if bbox is None:
        raise ValueError(f"No se detecta ningún objeto en {src}")
    left, top, right, bottom = bbox
    margin = round(CROP_MARGIN * max(right - left, bottom - top))
    cropped = rgba.crop((left - margin, top - margin, right + margin, bottom + margin))

    side = max(cropped.size)
    square = Image.new("RGBA", (side, side), (*BACKGROUND, 0))
    square.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
    canvas = Image.new("RGB", (side, side), BACKGROUND)
    canvas.paste(square, mask=square.getchannel("A"))
    canvas = canvas.resize((size, size), Image.Resampling.LANCZOS)

    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst)
    return dst


def validate_input(path: Path) -> list[str]:
    """Return a list of problems (empty if the photo is usable)."""
    problems: list[str] = []
    with Image.open(path) as img:
        long_side = max(img.size)
        if long_side < MIN_LONG_SIDE_PX:
            problems.append(
                f"Resolución insuficiente: lado mayor {format_int(long_side)} px "
                f"(< {format_int(MIN_LONG_SIDE_PX)} px)"
            )
        mask = _object_mask(_remove_background(img.convert("RGB")))

    problems.extend(_object_size_problems(mask))
    return problems


def format_int(value: int) -> str:
    """Spanish thousands separator: 1000 → "1.000"."""
    return f"{value:,}".replace(",", ".")


def format_pct(fraction: float) -> str:
    """Spanish percentage with a space before the sign: 0.25 → "25 %"."""
    return f"{fraction * 100:.0f} %"


def _robust_bbox_size(mask: Image.Image) -> tuple[int, int] | None:
    """Width and height of the mask's coordinate-percentile box, or None if empty."""
    ys, xs = np.nonzero(np.asarray(mask))
    if xs.size == 0:
        return None
    x_lo, x_hi = np.percentile(xs, BBOX_PERCENTILES)
    y_lo, y_hi = np.percentile(ys, BBOX_PERCENTILES)
    return round(x_hi - x_lo) + 1, round(y_hi - y_lo) + 1


def _object_size_problems(mask: Image.Image) -> list[str]:
    """Check the object's robust bounding box against ``MIN_BBOX_FRACTION`` of the long side."""
    size = _robust_bbox_size(mask)
    if size is None:
        return ["Objeto no detectado: la eliminación de fondo no encuentra ninguna pieza"]
    box_w, box_h = size
    long_side = max(mask.size)
    if max(box_w, box_h) < MIN_BBOX_FRACTION * long_side:
        return [
            f"Objeto demasiado pequeño en la foto: caja envolvente {format_int(box_w)}×"
            f"{format_int(box_h)} px ({format_pct(box_w / long_side)} × "
            f"{format_pct(box_h / long_side)} del lado mayor de la imagen; "
            f"su lado mayor debe ocupar ≥ {format_pct(MIN_BBOX_FRACTION)})"
        ]
    return []
