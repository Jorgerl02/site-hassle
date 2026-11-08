"""Variant E — parametric: classify the piece, build it from boxes in Blender and project
the cleaned photo on it. No external API, cost 0, always exactly one candidate.

Only for rectilinear pieces: with ``piece.rectilinear is False`` it returns zero candidates
and ``notes="no aplicable: pieza orgánica"`` (recorded as ``not_applicable`` and excluded
from E's denominator). ``rectilinear is None`` (unknown) runs."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

from harness.core import storage
from harness.core.blender import BlenderNotAvailable, run_blender_script
from harness.core.config import Settings
from harness.core.models import Candidate, Piece, VariantResult
from harness.core.variant import NOT_APPLICABLE_PREFIX
from harness.post import parametric_spec
from harness.prep import clean

BPY_PARAMETRIC_SCRIPT = Path(__file__).resolve().parent.parent / "post" / "bpy_parametric.py"
SPEC_FILENAME = "parametric_spec.json"
TEXTURE_FILENAME = "texture.png"
LOG_FILENAME = "parametric_blender.log"
LOG_TAIL_CHARS = 4000
WHITE = (255, 255, 255)
CROP_THRESHOLD = 8  # per-channel distance from white still considered background
FILL_THRESHOLD = 16  # max-channel distance from white below which a pixel is background
FILL_ERODE = 2  # px eroded from the object mask so the anti-aliased halo is refilled too


def crop_to_content(src: Path, dst: Path, threshold: int = CROP_THRESHOLD) -> Path:
    """Crop ``src`` to the bounding box of its non-white pixels and save it as ``dst``.

    ``clean_image`` pads the object on a white square with a margin; the parametric UVs map
    the whole texture onto the piece's bounding box, so the padding must go. If the image
    is entirely white it is saved unchanged.
    """
    with Image.open(src) as img:
        rgb = img.convert("RGB")
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, WHITE)).convert("L")
    bbox = diff.point(lambda v: 255 if v > threshold else 0).getbbox()
    out = rgb.crop(bbox) if bbox else rgb
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return dst


def _erode(mask: np.ndarray, iterations: int) -> np.ndarray:
    """4-neighbour binary erosion; outside the image counts as background."""
    if iterations <= 0:
        return mask.copy()
    out = np.pad(mask, iterations, constant_values=False)
    for _ in range(iterations):
        nxt = out.copy()
        nxt[1:, :] &= out[:-1, :]
        nxt[:-1, :] &= out[1:, :]
        nxt[:, 1:] &= out[:, :-1]
        nxt[:, :-1] &= out[:, 1:]
        out = nxt
    return out[iterations:-iterations, iterations:-iterations]


def _fill_rows(arr: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Every pixel of a row takes the colour of the nearest ``mask`` pixel in that row.

    Returns ``(filled, rows_with_object)``; rows without object pixels are left unchanged.
    """
    h, w = mask.shape
    idx = np.broadcast_to(np.arange(w), (h, w))
    left = np.maximum.accumulate(np.where(mask, idx, -1), axis=1)
    right = np.minimum.accumulate(np.where(mask, idx, w)[:, ::-1], axis=1)[:, ::-1]
    d_left = np.where(left >= 0, idx - left, w + 1)
    d_right = np.where(right < w, right - idx, w + 1)
    src = np.clip(np.where(d_left <= d_right, left, right), 0, w - 1)
    has = mask.any(axis=1)
    filled = arr.copy()
    filled[has] = np.take_along_axis(arr, src[:, :, None], axis=1)[has]
    return filled, has


def fill_background(path: Path, threshold: int = FILL_THRESHOLD, erode: int = FILL_ERODE) -> Path:
    """Replace the white background of the (cropped) photo in place with object colours.

    The parametric UVs project the photo planarly onto boxes that do not match the
    photo's silhouette (perspective, legs elsewhere, open gaps), so any background pixel
    would show up as a grey/white patch. Each background pixel takes the colour of the
    nearest object pixel in its row (wood/stone grain runs along the rows), rows without
    object take it from their column. An image with no object is left unchanged.
    """
    with Image.open(path) as img:
        arr = np.asarray(img.convert("RGB")).copy()
    mask = (255 - arr.astype(np.int16)).max(axis=2) > threshold
    if not mask.any():
        return Path(path)
    eroded = _erode(mask, erode)
    if eroded.any():
        mask = eroded
    filled, has = _fill_rows(arr, mask)
    if not has.all():  # rows with no object: fill each column from the filled rows
        cols, _ = _fill_rows(
            filled.transpose(1, 0, 2), np.broadcast_to(has[:, None], mask.shape).T.copy()
        )
        filled = cols.transpose(1, 0, 2)
    Image.fromarray(np.ascontiguousarray(filled)).save(path)
    return Path(path)


class ParametricBuildError(RuntimeError):
    """Blender failed to build the parametric model."""


class ParametricVariant:
    name = "E"

    def __init__(self, blender_bin: Path | None = None, timeout: int = 300) -> None:
        self.blender_bin = blender_bin
        self.timeout = timeout

    def _resolve_blender(self) -> Path:
        binary = self.blender_bin if self.blender_bin is not None else Settings.load().blender_bin
        if binary is None:
            raise BlenderNotAvailable("BLENDER_BIN no está definido (.env o entorno)")
        if not Path(binary).is_file():
            raise BlenderNotAvailable(f"BLENDER_BIN no existe: {binary}")
        return Path(binary)

    def _texture(self, piece: Piece, cand: Path) -> tuple[Path, str]:
        dst = cand / TEXTURE_FILENAME
        try:
            cleaned = clean.clean_image(piece.images[0], dst)
        except ValueError:
            return piece.images[0], "original (clean_image no detectó objeto)"
        cropped = crop_to_content(cleaned, dst)
        return fill_background(cropped), "clean_image + recorte al objeto + relleno del fondo"

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        # Deterministic: ``candidates`` is ignored, there is exactly one candidate.
        if piece.rectilinear is False:
            return VariantResult(
                variant=self.name,
                piece_id=piece.id,
                candidates=[],
                notes=f"{NOT_APPLICABLE_PREFIX}: pieza orgánica",
            )
        blender_bin = self._resolve_blender()  # fail fast, before the costly photo cleaning
        start = time.monotonic()
        cand = storage.candidate_dir(workdir, 1)

        kind = parametric_spec.classify(piece)
        texture, texture_source = self._texture(piece, cand)
        spec = parametric_spec.make_spec(piece, kind, texture=Path(texture).resolve())
        spec_path = parametric_spec.write_spec(cand / SPEC_FILENAME, spec)

        glb = storage.model_path(cand)
        glb.unlink(missing_ok=True)
        run = run_blender_script(
            BPY_PARAMETRIC_SCRIPT,
            ["--spec", str(spec_path), "--out", str(glb)],
            timeout=self.timeout,
            blender_bin=blender_bin,
        )
        log = f"$ {' '.join(run.cmd)}\n[exit {run.returncode}]\n{run.stdout}\n{run.stderr}"
        (cand / LOG_FILENAME).write_text(log, encoding="utf-8")
        if not run.ok or not glb.is_file():
            raise ParametricBuildError(
                f"bpy_parametric.py falló (código {run.returncode}) para {piece.id}\n"
                f"{log[-LOG_TAIL_CHARS:]}"
            )

        candidate = Candidate(
            index=1,
            glb_path=glb,
            cost_usd=0.0,
            seconds=time.monotonic() - start,
            meta={
                "kind": kind,
                "spec_path": str(spec_path),
                "n_boxes": len(spec.boxes),
                "texture": str(texture),
                "texture_source": texture_source,
                "blender_seconds": run.seconds,
            },
        )
        return VariantResult(
            variant=self.name,
            piece_id=piece.id,
            candidates=[candidate],
            notes=f"tipo paramétrico: {kind}; 1 candidato (determinista)",
        )
