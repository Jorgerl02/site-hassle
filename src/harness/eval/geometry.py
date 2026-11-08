"""Geometric checks of a generated GLB against the piece's catalogue dimensions.

Axis rule (same as the post-processing in ``harness.post``): glTF is +Y-up, so HEIGHT is the
Y extent, compared with ``height_cm`` as is. The two horizontal extents (X, Z) are paired
with ``width_cm``/``depth_cm`` by sorted size (largest with largest), which forgives a
rotation about the vertical axis. Consequence: a model lying on its side gets a large
``err_height``; a model turned 90° on the floor is not penalised.

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
class GeometryResult:
    metrics: GeometryMetrics | None
    source: str | None  # "trimesh" | "post_meta" | None
    error: str | None  # candidate-attributable failure, if metrics is None


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


def measure(mesh: trimesh.Trimesh, piece: Piece) -> GeometryMetrics:
    ex, ey, ez = (float(e) * GLB_UNITS_TO_CM for e in mesh.extents)
    width, height, depth = match_extents((ex, ey, ez), piece)
    return GeometryMetrics(
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


def measure_glb(path: Path, piece: Piece) -> GeometryMetrics:
    return measure(load_mesh(path), piece)


def metrics_from_post_meta(meta_path: Path, piece: Piece) -> GeometryMetrics:
    """Build metrics from Blender's ``post_meta.json`` (signed errors width/height/depth).

    Topology is unknown there: ``watertight=False``, ``n_components=0`` and
    ``n_faces = tris_after``. Raises ``ValueError``/``KeyError`` if malformed.
    """
    data = json.loads(Path(meta_path).read_text(encoding="utf-8"))
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
        return GeometryResult(measure_glb(glb, piece), "trimesh", None)
    except Exception as exc:  # trimesh raises many types on unreadable files (e.g. Draco)
        load_error = str(exc) or type(exc).__name__
    meta_path = glb.with_name(POST_META_FILENAME)
    if meta_path.is_file():
        try:
            return GeometryResult(metrics_from_post_meta(meta_path, piece), "post_meta", None)
        except (KeyError, TypeError, ValueError) as exc:
            return GeometryResult(
                None, None, f"GLB ilegible y {POST_META_FILENAME} inválido: {exc!r}"
            )
    return GeometryResult(None, None, f"GLB ilegible: {load_error}")
