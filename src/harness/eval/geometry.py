"""Geometric checks of a generated GLB against the piece's catalogue dimensions.

Axis rule (same as the post-processing in ``harness.post``): glTF is +Y-up, so HEIGHT is the
Y extent, compared with ``height_cm`` as is. The two horizontal extents (X, Z) are paired
with ``width_cm``/``depth_cm`` by sorted size (largest with largest), which forgives a
rotation about the vertical axis. Consequence: a model lying on its side gets a large
``err_height``; a model turned 90° on the floor is not penalised.

Scale rule (also the same as ``harness.post``): generators output models at an arbitrary
native scale, so before comparing, the mesh is rescaled uniformly by
``max(target_cm) / max(raw_extents_cm)``. The metric therefore measures PROPORTIONS, and a
raw GLB and its post-processed (pre-scaled) copy get identical metrics. The raw extents and
the factor are kept in ``Measurement``/``GeometryResult`` for the record.

If trimesh cannot read the GLB (e.g. Draco-compressed output of the post-processing), the
errors written by Blender in ``post_meta.json`` next to it are used instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import trimesh

from harness.core import storage
from harness.core.models import GeometryMetrics, Piece

GLB_UNITS_TO_CM = 100.0  # glTF units are metres
POST_META_FILENAME = "post_meta.json"  # written by harness.post next to model_post.glb


class CandidateGeometryError(ValueError):
    """The candidate itself is broken (missing, unreadable or empty model)."""


@dataclass(frozen=True)
class Measurement:
    metrics: GeometryMetrics  # after the uniform rescale
    raw_extents_cm: tuple[float, float, float]  # glTF X, Y, Z before rescaling
    scale_factor: float


@dataclass(frozen=True)
class GeometryResult:
    metrics: GeometryMetrics | None
    source: str | None  # "trimesh" | "post_meta" | None
    error: str | None  # candidate-attributable failure, if metrics is None
    raw_extents_cm: tuple[float, float, float] | None = None
    scale_factor: float | None = None


def model_for_candidate(cand_dir: Path) -> Path:
    """Post-processed GLB if present, else the raw one."""
    post = storage.model_post_path(cand_dir)
    return post if post.exists() else storage.model_path(cand_dir)


def load_mesh(path: Path) -> trimesh.Trimesh:
    """Load a GLB as a single mesh (scene graph transforms applied, geometries concatenated)."""
    loaded = trimesh.load(Path(path))
    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise CandidateGeometryError(f"{Path(path).name}: la escena no contiene geometría")
        mesh = loaded.to_geometry()
    else:
        mesh = loaded
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise CandidateGeometryError(f"{Path(path).name}: no contiene una malla con caras")
    return mesh


def match_extents(
    extents_xyz_cm: tuple[float, float, float], piece: Piece
) -> tuple[float, float, float]:
    """(width, height, depth) measured: height = Y; X/Z paired with width/depth by size."""
    x, y, z = extents_xyz_cm
    small, large = sorted((x, z))
    if piece.width_cm >= piece.depth_cm:
        return large, y, small
    return small, y, large


def uniform_scale_factor(raw_extents_cm: tuple[float, float, float], piece: Piece) -> float:
    """``max(target_cm) / max(raw_extents_cm)``, the rule of ``bpy_post``."""
    longest = max(raw_extents_cm)
    if longest <= 0:
        raise CandidateGeometryError("caja envolvente degenerada (extensión nula)")
    return max(piece.width_cm, piece.height_cm, piece.depth_cm) / longest


def measure_details(mesh: trimesh.Trimesh, piece: Piece) -> Measurement:
    ex, ey, ez = (float(e) * GLB_UNITS_TO_CM for e in mesh.extents)
    raw = (ex, ey, ez)
    factor = uniform_scale_factor(raw, piece)
    width, height, depth = match_extents((ex * factor, ey * factor, ez * factor), piece)
    metrics = GeometryMetrics(
        width_cm=width,
        height_cm=height,
        depth_cm=depth,
        err_width=(width - piece.width_cm) / piece.width_cm,
        err_height=(height - piece.height_cm) / piece.height_cm,
        err_depth=(depth - piece.depth_cm) / piece.depth_cm,
        watertight=bool(mesh.is_watertight),
        n_components=len(mesh.split(only_watertight=False)),
        n_faces=len(mesh.faces),
    )
    return Measurement(metrics, raw, factor)


def measure(mesh: trimesh.Trimesh, piece: Piece) -> GeometryMetrics:
    """Metrics after the uniform rescale (scale-invariant)."""
    return measure_details(mesh, piece).metrics


def measure_glb(path: Path, piece: Piece) -> GeometryMetrics:
    return measure(load_mesh(path), piece)


def _post_meta(meta_path: Path) -> dict:
    return json.loads(Path(meta_path).read_text(encoding="utf-8"))


def metrics_from_post_meta(meta_path: Path, piece: Piece) -> GeometryMetrics:
    """Build metrics from Blender's ``post_meta.json`` (signed errors width/height/depth,
    already measured after the same uniform rescale).

    Topology is unknown there: ``watertight=False``, ``n_components=0`` and
    ``n_faces = tris_after``. Raises ``ValueError``/``KeyError`` if malformed.
    """
    data = _post_meta(meta_path)
    errors = {axis: float(data["errors"][axis]) for axis in ("width", "height", "depth")}
    return GeometryMetrics(
        width_cm=piece.width_cm * (1 + errors["width"]),
        height_cm=piece.height_cm * (1 + errors["height"]),
        depth_cm=piece.depth_cm * (1 + errors["depth"]),
        err_width=errors["width"],
        err_height=errors["height"],
        err_depth=errors["depth"],
        watertight=False,
        n_components=0,
        n_faces=int(data.get("tris_after") or 0),
    )


def measure_candidate(glb: Path, piece: Piece) -> GeometryResult:
    """Metrics of a candidate GLB, falling back to ``post_meta.json`` if trimesh fails."""
    glb = Path(glb)
    if not glb.is_file():
        return GeometryResult(None, None, f"no existe el modelo {glb.name}")
    try:
        mesh = load_mesh(glb)
        m = measure_details(mesh, piece)
        return GeometryResult(m.metrics, "trimesh", None, m.raw_extents_cm, m.scale_factor)
    except Exception as exc:  # trimesh raises many types on unreadable files (e.g. Draco)
        load_error = str(exc) or type(exc).__name__
    meta_path = glb.with_name(POST_META_FILENAME)
    if meta_path.is_file():
        try:
            metrics = metrics_from_post_meta(meta_path, piece)
            data = _post_meta(meta_path)
            raw = data.get("raw_cm") or {}
            raw_xyz = (
                (float(raw["width"]), float(raw["height"]), float(raw["depth"]))
                if all(k in raw for k in ("width", "height", "depth"))
                else None
            )
            factor = data.get("scale_factor")
            return GeometryResult(
                metrics,
                "post_meta",
                None,
                raw_xyz,
                float(factor) if factor is not None else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return GeometryResult(
                None, None, f"GLB ilegible y {POST_META_FILENAME} inválido: {exc!r}"
            )
    return GeometryResult(None, None, f"GLB ilegible: {load_error}")
