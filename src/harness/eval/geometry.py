"""Geometric checks of a generated GLB against the piece's catalogue dimensions.

Axis-matching rule: image-to-3D generators do not agree on orientation (some export the
piece lying down or rotated 90° about the up axis), so the three measured bounding-box
extents are matched to the three catalogue dimensions **by sorted size**: the largest
measured extent is compared with the largest catalogue dimension, the middle with the
middle and the smallest with the smallest. ``width_cm``/``height_cm``/``depth_cm`` in the
result are the measured extents assigned to each catalogue dimension under that rule.
Consequence: a model in the wrong orientation is NOT penalised here (the VLM judge and the
renders catch it); a model with the right size but swapped proportions is.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from harness.core import storage
from harness.core.models import GeometryMetrics, Piece

GLB_UNITS_TO_CM = 100.0  # glTF units are metres


def model_for_candidate(cand_dir: Path) -> Path:
    """Post-processed GLB if present, else the raw one."""
    post = storage.model_post_path(cand_dir)
    return post if post.exists() else storage.model_path(cand_dir)


def load_mesh(path: Path) -> trimesh.Trimesh:
    """Load a GLB as a single mesh (scene graph transforms applied, geometries concatenated)."""
    loaded = trimesh.load(Path(path))
    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise ValueError(f"{path}: la escena no contiene geometría")
        mesh = loaded.to_geometry()
    else:
        mesh = loaded
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path}: no contiene una malla con caras")
    return mesh


def match_extents(
    measured_cm: tuple[float, float, float], target_cm: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Assign measured extents to target dims by sorted size; returns them in target order."""
    measured_sorted = sorted(measured_cm)
    target_rank = np.argsort(np.asarray(target_cm), kind="stable")
    assigned = [0.0, 0.0, 0.0]
    for rank, target_index in enumerate(target_rank):
        assigned[int(target_index)] = float(measured_sorted[rank])
    return assigned[0], assigned[1], assigned[2]


def measure(mesh: trimesh.Trimesh, piece: Piece) -> GeometryMetrics:
    extents = tuple(float(e) * GLB_UNITS_TO_CM for e in mesh.extents)
    target = (piece.width_cm, piece.height_cm, piece.depth_cm)
    width, height, depth = match_extents(extents, target)  # type: ignore[arg-type]
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
