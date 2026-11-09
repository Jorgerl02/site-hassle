"""Real PBR material swap executed INSIDE Blender (5.x):

    BLENDER_BIN --background --python bpy_materials.py -- --in IN.glb --out OUT.glb
        --meta META.json --material-id travertine --color Color.jpg [--normal NormalGL.jpg]
        [--normal-strength 0.5] [--roughness-map Roughness.jpg] [--roughness 1.0]
        [--metallic 0.0] --tile-cm 60 [--real-size W H D] [--uv-mode auto|box|mesh]
        [--vertical-grain]

Steps: import the GLB → measure the world bounding box of every mesh → decide, per mesh,
whether its UVs can carry a tileable texture (``--uv-mode auto``: see
:func:`uv_usable`) or must be replaced by a box projection (:func:`box_uv`) → scale the UVs
so one texture repeat covers ``--tile-cm`` of the real piece (:func:`repeats_per_unit`) →
replace EVERY material with one Principled BSDF fed by the given maps (Color as sRGB,
Roughness and NormalGL as Non-Color; no Roughness map means a constant ``--roughness``) →
export a plain GLB (no Draco, images kept in their source format) → META.json.

The maps arrive already prepared by ``harness.post.materials`` (Color tone-matched to the
photo, Roughness remapped to the wanted mean), so this script only wires them.

Why box projection by default for generated meshes: Tripo / TRELLIS UVs are texture
atlases (hundreds of charts with arbitrary rotation and scale) and the parametric variant's
UVs point at photo regions; neither has a physical scale, so a tileable PBR map on them
shows seams at every chart and a random grain size. A box projection in world metres gives
a uniform, real-size grain with seams only where the dominant axis of the normal changes.

Pure-Python helpers (numpy only) are importable outside Blender and unit-tested;
``bpy`` is imported inside :func:`main`.
Docs consulted on 2026-11-09 (Blender 5.2 Python API): ``Mesh.uv_layers`` /
``MeshUVLoopLayer.uv`` (``foreach_set("vector", …)``), ``Mesh.loops`` / ``polygons``
(``foreach_get``), ``ShaderNodeNormalMap.inputs["Strength"]``,
``Image.colorspace_settings.name = "Non-Color"``, ``bpy.ops.export_scene.gltf``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

try:  # imported as part of the harness package (tests, wrapper)
    from harness.post.bpy_post import script_argv
except ImportError:  # running inside Blender: the sibling module is on the script dir
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bpy_post import script_argv  # type: ignore[no-redef]

UV_MODES = ("auto", "box", "mesh")
# Mesh UVs are kept (``auto``) only when they look like a physical unwrap.
UV_MAX_DENSITY_CV = 0.25  # area-weighted coefficient of variation of texel density
UV_MAX_ANISOTROPY = 1.25  # median stretch ratio of the UV map per triangle
UV_MAX_SPLIT_FRACTION = 0.05  # vertices carrying more than one UV (chart borders)
CM_PER_M = 100.0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bpy_materials")
    parser.add_argument("--in", dest="glb_in", required=True)
    parser.add_argument("--out", dest="glb_out", required=True)
    parser.add_argument("--meta", dest="meta", required=True)
    parser.add_argument("--material-id", dest="material_id", required=True)
    parser.add_argument("--color", dest="color", required=True)
    parser.add_argument("--normal", dest="normal", default=None)
    parser.add_argument("--normal-strength", dest="normal_strength", type=float, default=0.0)
    parser.add_argument("--roughness-map", dest="roughness_map", default=None)
    parser.add_argument("--roughness", dest="roughness", type=float, default=1.0)
    parser.add_argument("--metallic", dest="metallic", type=float, default=0.0)
    parser.add_argument("--tile-cm", dest="tile_cm", type=float, required=True)
    parser.add_argument(
        "--real-size", dest="real_size", type=float, nargs=3, default=None,
        metavar=("W", "H", "D"), help="Medidas reales en cm (ancho, alto, fondo)",
    )  # fmt: skip
    parser.add_argument("--uv-mode", dest="uv_mode", choices=UV_MODES, default="auto")
    parser.add_argument("--vertical-grain", dest="vertical_grain", action="store_true")
    ns = parser.parse_args(argv)
    if ns.tile_cm <= 0:
        parser.error("--tile-cm debe ser > 0")
    if ns.real_size is not None and min(ns.real_size) <= 0:
        parser.error("--real-size debe ser > 0 en los tres ejes")
    for name in ("roughness", "metallic"):
        if not 0.0 <= getattr(ns, name) <= 1.0:
            parser.error(f"--{name} debe estar entre 0 y 1")
    if ns.normal_strength < 0:
        parser.error("--normal-strength debe ser ≥ 0")
    return ns


# --------------------------------------------------------------------------- pure helpers


def repeats_per_unit(
    extent_units: tuple[float, float, float] | list[float],
    real_size_cm: tuple[float, float, float] | list[float] | None,
    tile_cm: float,
) -> float:
    """Texture repeats per model unit so one repeat covers ``tile_cm`` of the real piece.

    ``extent_units`` is the model's bounding box (any axis order); ``real_size_cm`` the
    real (width, height, depth). Their largest sides are matched, which is independent of
    the model's orientation. Without real dimensions the model is taken to be in metres
    (glTF's unit). Example: a model 1 unit wide that is really 120 cm, with a 60 cm tile →
    120 cm per unit / 60 cm = 2 repeats per unit.
    """
    if tile_cm <= 0:
        raise ValueError("tile_cm debe ser > 0")
    largest = max(float(v) for v in extent_units)
    if largest <= 0:
        raise ValueError("La malla no tiene extensión")
    cm_per_unit = CM_PER_M if real_size_cm is None else max(real_size_cm) / largest
    return cm_per_unit / tile_cm


def box_uv(
    points: np.ndarray, normals: np.ndarray, scale: float, *, vertical_grain: bool = False
) -> np.ndarray:
    """Box (cube) projection: each loop takes the two coordinates orthogonal to the
    dominant axis of its face normal, times ``scale`` (repeats per unit).

    ``points`` (N, 3) world positions of the loops, ``normals`` (N, 3) their face normals.
    Axis convention (Blender Z-up): top/bottom faces use (x, y); faces looking along ±X use
    (y, z); faces looking along ±Y use (x, z). The horizontal coordinate is flipped on the
    negative-facing side so the texture is not mirrored when seen from outside.
    ``vertical_grain`` swaps U and V on the side faces (±X, ±Y): a scan whose veins / grain
    run along U (Travertine009, the wood planks) then runs vertically on legs and columns,
    as in vein-cut stone and solid-wood legs, and the box-projection seams between side
    faces fall along the grain, where they are hardly visible.
    """
    points = np.asarray(points, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    axis = np.argmax(np.abs(normals), axis=1)
    sign = np.where(normals[np.arange(len(normals)), axis] < 0, -1.0, 1.0)
    uv = np.empty((len(points), 2), dtype=np.float64)
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    on_x, on_y, on_z = axis == 0, axis == 1, axis == 2
    uv[on_x, 0], uv[on_x, 1] = sign[on_x] * y[on_x], z[on_x]
    uv[on_y, 0], uv[on_y, 1] = -sign[on_y] * x[on_y], z[on_y]
    uv[on_z, 0], uv[on_z, 1] = x[on_z], sign[on_z] * y[on_z]
    if vertical_grain:
        side = ~on_z
        uv[side] = uv[side][:, ::-1].copy()
    return uv * scale


def triangle_uv_stats(tri_xyz: np.ndarray, tri_uv: np.ndarray) -> dict[str, float]:
    """Texel-density statistics of a UV map over triangles.

    ``tri_xyz`` (N, 3, 3) and ``tri_uv`` (N, 3, 2). Per triangle the 2×2 Jacobian from the
    triangle's own plane to UV space gives two singular values s1 ≥ s2: density
    √(s1·s2) (UV units per model unit) and anisotropy s1 / s2. Returns the area-weighted
    mean density (``density``), its coefficient of variation (``density_cv``), the median
    anisotropy and the 3D / UV areas. Degenerate triangles are ignored.
    """
    tri_xyz = np.asarray(tri_xyz, dtype=np.float64)
    tri_uv = np.asarray(tri_uv, dtype=np.float64)
    e1 = tri_xyz[:, 1] - tri_xyz[:, 0]
    e2 = tri_xyz[:, 2] - tri_xyz[:, 0]
    len1 = np.linalg.norm(e1, axis=1)
    area3d = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    d1 = tri_uv[:, 1] - tri_uv[:, 0]
    d2 = tri_uv[:, 2] - tri_uv[:, 0]
    area_uv = 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    ok = (area3d > 1e-12) & (area_uv > 1e-14) & (len1 > 1e-12)
    empty = {
        "density": 0.0,
        "density_cv": float("inf"),
        "anisotropy": float("inf"),
        "area_3d": float(area3d.sum()),
        "area_uv": float(area_uv.sum()),
        "triangles": int(ok.sum()),
    }
    if not ok.any():
        return empty
    e1, e2, len1, d1, d2, w = e1[ok], e2[ok], len1[ok], d1[ok], d2[ok], area3d[ok]
    xhat = e1 / len1[:, None]
    e2x = np.einsum("ij,ij->i", e2, xhat)
    e2y = np.linalg.norm(e2 - e2x[:, None] * xhat, axis=1)
    # P maps the local 2D frame of the triangle to its edges: columns (len1, 0), (e2x, e2y).
    p = np.zeros((len(w), 2, 2))
    p[:, 0, 0], p[:, 0, 1], p[:, 1, 1] = len1, e2x, e2y
    uvm = np.stack([d1, d2], axis=2)  # columns d1, d2
    jac = uvm @ np.linalg.inv(p)
    sv = np.linalg.svd(jac, compute_uv=False)
    s1, s2 = sv[:, 0], np.maximum(sv[:, 1], 1e-12)
    density = np.sqrt(s1 * s2)
    mean = float(np.average(density, weights=w))
    cv = float(np.sqrt(np.average((density - mean) ** 2, weights=w)) / mean) if mean else 0.0
    return {
        "density": mean,
        "density_cv": cv,
        "anisotropy": float(np.median(s1 / s2)),
        "area_3d": float(area3d.sum()),
        "area_uv": float(area_uv.sum()),
        "triangles": int(ok.sum()),
    }


def split_vertex_fraction(loop_vertex: np.ndarray, loop_uv: np.ndarray) -> float:
    """Fraction of vertices whose loops carry more than one distinct UV (chart borders)."""
    loop_vertex = np.asarray(loop_vertex)
    if loop_vertex.size == 0:
        return 0.0
    rounded = np.round(np.asarray(loop_uv, dtype=np.float64), 5)
    pairs = np.unique(np.column_stack([loop_vertex, rounded]), axis=0)
    verts, counts = np.unique(pairs[:, 0], return_counts=True)
    return float((counts > 1).sum() / len(verts))


def uv_usable(stats: dict[str, float], split_fraction: float) -> bool:
    """True when the mesh's own UVs look like a physical unwrap a tileable map can use:
    uniform density, little stretch and few chart borders."""
    return (
        stats.get("triangles", 0) > 0
        and stats["density_cv"] <= UV_MAX_DENSITY_CV
        and stats["anisotropy"] <= UV_MAX_ANISOTROPY
        and split_fraction <= UV_MAX_SPLIT_FRACTION
    )


def file_size(path: str) -> int | None:
    return os.path.getsize(path) if os.path.isfile(path) else None


# --------------------------------------------------------------------------- Blender side


def _clear_scene(bpy) -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _world_loops(obj) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(loop positions, loop face normals, loop vertex indices, loop polygon indices) in
    world space."""
    mesh = obj.data
    n_verts, n_loops, n_polys = len(mesh.vertices), len(mesh.loops), len(mesh.polygons)
    co = np.empty(n_verts * 3)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    loop_vert = np.empty(n_loops, dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", loop_vert)
    starts = np.empty(n_polys, dtype=np.int64)
    totals = np.empty(n_polys, dtype=np.int64)
    mesh.polygons.foreach_get("loop_start", starts)
    mesh.polygons.foreach_get("loop_total", totals)
    poly_normals = np.empty(n_polys * 3)
    mesh.polygons.foreach_get("normal", poly_normals)
    poly_normals = poly_normals.reshape(-1, 3)
    loop_poly = np.empty(n_loops, dtype=np.int64)
    loop_poly[np.repeat(starts, totals) + _offsets(totals)] = np.repeat(np.arange(n_polys), totals)

    mw = np.array(obj.matrix_world, dtype=np.float64)
    world = co @ mw[:3, :3].T + mw[:3, 3]
    nrm = poly_normals @ np.linalg.inv(mw[:3, :3])  # (M^-1)^T applied to row vectors
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    return world[loop_vert], nrm[loop_poly], loop_vert, loop_poly


def _offsets(totals: np.ndarray) -> np.ndarray:
    """0, 1, … within each polygon (so loop_start + offset = loop index)."""
    ends = np.cumsum(totals)
    return np.arange(int(ends[-1]) if len(ends) else 0) - np.repeat(ends - totals, totals)


def _loop_triangles(obj, loop_pos: np.ndarray, loop_uv: np.ndarray):
    mesh = obj.data
    mesh.calc_loop_triangles()
    n = len(mesh.loop_triangles)
    loops = np.empty(n * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("loops", loops)
    loops = loops.reshape(-1, 3)
    return loop_pos[loops], loop_uv[loops], n


def _uv_layer(mesh):
    if not mesh.uv_layers:
        layer = mesh.uv_layers.new(name="UVMap")
    else:
        layer = mesh.uv_layers.active or mesh.uv_layers[0]
    mesh.uv_layers.active = layer
    layer.active_render = True
    return layer


def _retile(obj, mode: str, rpu: float, vertical_grain: bool) -> dict:
    """Rewrite the UVs of ``obj``: rescale its own unwrap or box-project in world units."""
    mesh = obj.data
    loop_pos, loop_nrm, loop_vert, _ = _world_loops(obj)
    report: dict = {"object": obj.name, "requested": mode}
    had_uvs = bool(mesh.uv_layers)
    current = None
    if had_uvs:
        layer = mesh.uv_layers.active or mesh.uv_layers[0]
        current = np.empty(len(mesh.loops) * 2)
        layer.uv.foreach_get("vector", current)
        current = current.reshape(-1, 2)
        tri_xyz, tri_uv, _ = _loop_triangles(obj, loop_pos, current)
        stats = triangle_uv_stats(tri_xyz, tri_uv)
        split = split_vertex_fraction(loop_vert, current)
        report.update({"uv_stats": stats, "split_fraction": split})
        usable = uv_usable(stats, split)
    else:
        usable = False
    report["mesh_uv_usable"] = usable
    use_mesh = had_uvs and (mode == "mesh" or (mode == "auto" and usable))
    if use_mesh:
        density = report["uv_stats"]["density"] or 1.0
        new_uv = current * (rpu / density)
        report["used"] = "mesh"
    else:
        new_uv = box_uv(loop_pos, loop_nrm, rpu, vertical_grain=vertical_grain)
        report["used"] = "box"
    layer = _uv_layer(mesh)
    layer.uv.foreach_set("vector", new_uv.astype(np.float32).ravel())
    mesh.update()
    return report


def _load_image(bpy, path: str, colorspace: str):
    image = bpy.data.images.load(path, check_existing=True)
    image.colorspace_settings.name = colorspace
    image.pack()
    return image


def _build_material(bpy, args: argparse.Namespace):
    mat = bpy.data.materials.new(name=f"PBR_{args.material_id}")
    if not mat.node_tree:  # Blender 4.x needs use_nodes; 5.x materials come with a tree
        mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Metallic"].default_value = args.metallic
    bsdf.inputs["Roughness"].default_value = args.roughness

    color = nodes.new("ShaderNodeTexImage")
    color.image = _load_image(bpy, args.color, "sRGB")
    color.location = (-500, 300)
    links.new(color.outputs["Color"], bsdf.inputs["Base Color"])
    nodes.active = color  # Workbench TEXTURE shading shows the active image node

    if args.roughness_map:
        rough = nodes.new("ShaderNodeTexImage")
        rough.image = _load_image(bpy, args.roughness_map, "Non-Color")
        rough.location = (-500, 0)
        links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])

    if args.normal and args.normal_strength > 0:
        normal_img = nodes.new("ShaderNodeTexImage")
        normal_img.image = _load_image(bpy, args.normal, "Non-Color")
        normal_img.location = (-700, -300)
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.inputs["Strength"].default_value = args.normal_strength
        normal_map.location = (-300, -300)
        links.new(normal_img.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def main(argv: list[str]) -> int:
    import bpy  # only available inside Blender

    args = parse_args(script_argv(argv))
    start = time.monotonic()
    _clear_scene(bpy)
    bpy.ops.import_scene.gltf(filepath=args.glb_in)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("El GLB no contiene mallas")

    corners = []
    for obj in meshes:
        mw = np.array(obj.matrix_world, dtype=np.float64)
        co = np.empty(len(obj.data.vertices) * 3)
        obj.data.vertices.foreach_get("co", co)
        corners.append(co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
    pts = np.concatenate(corners)
    extent = (pts.max(axis=0) - pts.min(axis=0)).tolist()
    rpu = repeats_per_unit(extent, args.real_size, args.tile_cm)

    uv_reports = [_retile(obj, args.uv_mode, rpu, args.vertical_grain) for obj in meshes]
    old_materials = {m.name for m in bpy.data.materials}
    mat = _build_material(bpy, args)
    for obj in meshes:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    for name in old_materials:  # drop the generated textures with their materials
        old = bpy.data.materials.get(name)
        if old is not None and old.users == 0:
            bpy.data.materials.remove(old)
    for image in list(bpy.data.images):
        if image.users == 0:
            bpy.data.images.remove(image)

    if os.path.exists(args.glb_out):
        os.remove(args.glb_out)
    bpy.ops.export_scene.gltf(
        filepath=args.glb_out,
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_yup=True,
        export_image_format="AUTO",
    )
    tris = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        tris += len(obj.data.loop_triangles)
    meta = {
        "glb_in": args.glb_in,
        "glb_out": args.glb_out,
        "glb_bytes": file_size(args.glb_out),
        "material_id": args.material_id,
        "material_name": mat.name,
        "maps": {
            "color": args.color,
            "normal": args.normal if args.normal_strength > 0 else None,
            "roughness": args.roughness_map,
        },
        "roughness": args.roughness,
        "metallic": args.metallic,
        "normal_strength": args.normal_strength,
        "tile_cm": args.tile_cm,
        "real_size_cm": args.real_size,
        "extent_units": extent,
        "repeats_per_unit": rpu,
        "uv_mode": args.uv_mode,
        "vertical_grain": args.vertical_grain,
        "uv": uv_reports,
        "meshes": len(meshes),
        "tris": tris,
        "blender_version": bpy.app.version_string,
        "seconds": time.monotonic() - start,
    }
    with open(args.meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")
    used = ",".join(r["used"] for r in uv_reports)
    print(f"[bpy_materials] OK {args.material_id} uv={used} rpu={rpu:.3f} tris={tris}")
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv)
    except Exception as exc:  # noqa: BLE001 — surface any failure as a non-zero exit
        import traceback

        traceback.print_exc()
        print(f"[bpy_materials] ERROR {exc}", file=sys.stderr)
        code = 1
    sys.exit(code)
