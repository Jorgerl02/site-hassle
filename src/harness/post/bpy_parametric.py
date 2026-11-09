"""Parametric furniture builder executed INSIDE Blender (4.x / 5.x), variant E:

    BLENDER_BIN --background --python bpy_parametric.py -- --spec SPEC.json --out OUT.glb [--draco]

Reads the box list written by ``harness.post.parametric_spec.write_spec`` (cm, X = width,
Y = depth with the front at -Y, Z = height, ``pos_cm`` = box centre), builds every box as
6 quads (4 own vertices each) in ONE mesh and bakes a planar, per-face projection of the
cleaned photo into the UVs (see :func:`planar_uv`), applies a Principled BSDF with the
photo as Base Color on every face and exports a GLB (metres, +Y up).

A box with ``"shape": "cylinder"`` (variant E ``pedestal``) is built instead as the
elliptic cylinder inscribed in it: :data:`CYLINDER_SEGMENTS` smooth side quads whose UVs
wrap a photo strip mirrored around the circumference (no seam, see :func:`wrap_u`) plus
two flat n-gon caps projected planarly (see :func:`_cylinder`).

Only the stdlib is used at import time: the geometry helpers are unit-tested outside
Blender, ``bpy`` is imported inside :func:`main`.
Blender docs consulted: https://docs.blender.org/api/4.5/ (Mesh.from_pydata, uv_layers,
ShaderNodeTexImage, BlendDataImages.load, bpy.ops.export_scene.gltf) on 2026-11-08;
verified against Blender 5.2.3 LTS (``Material.use_nodes`` is deprecated in 5.x and new
materials already carry a Principled BSDF node tree).
"""

from __future__ import annotations

import argparse
import json
import math
import sys

CM_TO_M = 0.01

Vec3 = tuple[float, float, float]
UV = tuple[float, float]

# Quad faces of a box, CCW seen from outside; vertex order in _box_vertices.
# (face name, vertex indices)
BOX_FACES: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("bottom", (0, 3, 2, 1)),
    ("top", (4, 5, 6, 7)),
    ("front", (0, 1, 5, 4)),
    ("right", (1, 2, 6, 5)),
    ("back", (2, 3, 7, 6)),
    ("left", (3, 0, 4, 7)),
)
FACE_NORMALS: dict[str, Vec3] = {
    "bottom": (0.0, 0.0, -1.0),
    "top": (0.0, 0.0, 1.0),
    "front": (0.0, -1.0, 0.0),
    "right": (1.0, 0.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
}
# Top/bottom faces sample this fraction of the photo's rows, starting at the top edge.
TOP_BAND = 0.15
# With a side band, top/bottom faces sample the band's rows BAND_V0..BAND_V0 + BAND_V_SPAN.
BAND_V0 = 0.2
BAND_V_SPAN = 0.6
# Cylinders: segments around (multiple of 4 so the ellipse's extremes are vertices and the
# mesh bbox is exactly the box). 64 keeps the silhouette smooth at 4N - 4 triangles each.
CYLINDER_SEGMENTS = 64
# Angle of the cylinders' texture mirror lines (see :func:`wrap_u`).
WRAP_PHASE = math.pi / 4


def script_argv(argv: list[str]) -> list[str]:
    return argv[argv.index("--") + 1 :] if "--" in argv else []


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bpy_parametric")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--draco", action="store_true")
    return parser.parse_args(argv)


def _box_vertices(box: dict) -> list[tuple[float, float, float]]:
    (sx, sy, sz), (px, py, pz) = box["size_cm"], box["pos_cm"]
    x0, x1 = (px - sx / 2) * CM_TO_M, (px + sx / 2) * CM_TO_M
    y0, y1 = (py - sy / 2) * CM_TO_M, (py + sy / 2) * CM_TO_M
    z0, z1 = (pz - sz / 2) * CM_TO_M, (pz + sz / 2) * CM_TO_M
    return [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]  # fmt: skip


def bounds(vertices: list[tuple[float, float, float]]) -> tuple[tuple[float, ...], ...]:
    mins = tuple(min(v[i] for v in vertices) for i in range(3))
    maxs = tuple(max(v[i] for v in vertices) for i in range(3))
    return mins, maxs


def planar_uv(
    normal: Vec3,
    v: Vec3,
    mins: Vec3,
    maxs: Vec3,
    box_z: tuple[float, float, tuple[float, float]] | None = None,
    side_band: tuple[float, float] | None = None,
) -> UV:
    """Planar UV of point ``v`` on a face with outward ``normal``, relative to the piece
    bounding box ``(mins, maxs)``. Blender UV convention: (0, 0) = bottom-left of the image.

    The photo is a front view of the whole piece, so every face samples the region of the
    photo that corresponds to it in that view; the UV is a pure function of the position
    and the face axis, so both triangles of a quad share one mapping (no diagonal seams):

    - front/back (normal ±Y): u = X, v = Z across the WHOLE piece bbox (a straight
      projection through the piece; legs sample the photo's leg region).
    - right/left (normal ±X): the same photo stretched across depth, mirrored so that the
      edge shared with the front face samples the same photo column as the front face
      (right: u = 1 - Y, left: u = Y; seamless at the front corners, seam at the back).
    - top/bottom (normal ±Z): the top ``TOP_BAND`` rows of the photo (the top surface in
      a front/3-4 view) stretched across X-Y; the front edge samples the top row, so it
      matches the front face's upper edge.

    Optional photo-region hints (variant E ``panel_table``): ``box_z = (z0, z1, (v0, v1))``
    maps the box's own height ``z0..z1`` onto photo rows ``v0..v1`` for its vertical faces
    (instead of the whole piece height), and ``side_band = (u0, u1)`` squeezes the u of
    right/left faces into that column band of the photo (a solid region of material);
    with a band, top/bottom faces also sample it (rows ``BAND_V0``..``+BAND_V_SPAN``).
    """

    def norm(i: int) -> float:
        span = maxs[i] - mins[i]
        return (v[i] - mins[i]) / span if span > 0 else 0.0

    def vert() -> float:
        if box_z is None:
            return norm(2)
        z0, z1, (v0, v1) = box_z
        t = (v[2] - z0) / (z1 - z0) if z1 > z0 else 0.0
        return v0 + (v1 - v0) * t

    axis = max(range(3), key=lambda i: abs(normal[i]))
    if axis == 1:  # front / back
        return norm(0), vert()
    if axis == 0:  # right / left
        u = 1.0 - norm(1) if normal[0] > 0 else norm(1)
        if side_band is not None:
            u = side_band[0] + (side_band[1] - side_band[0]) * u
        return u, vert()
    if side_band is not None:  # top / bottom inside the solid band (no top-band patchwork)
        u = side_band[0] + (side_band[1] - side_band[0]) * norm(0)
        return u, BAND_V0 + BAND_V_SPAN * norm(1)
    return norm(0), 1.0 - TOP_BAND * norm(1)  # top / bottom


def wrap_u(theta: float, u0: float, u1: float, phase: float = WRAP_PHASE) -> float:
    """u of a cylinder vertex at angle ``theta`` (0 = +X, CCW seen from above, front = -Y
    at 3π/2): the half centred on ``theta = phase + 3π/2`` runs ``u0`` → ``u1`` from left
    to right by arc length (as in the photo), the other half runs back mirrored, so u is
    continuous and 2π-periodic (no jump, no seam; the two mirror lines sit at ``phase``
    and ``phase + π``). The default phase puts them on the silhouette of the
    three-quarter view (camera at +X -Y), which therefore shows the strip unmirrored."""
    t = (theta - phase) % (2 * math.pi)
    return u0 + (u1 - u0) * abs(t - math.pi) / math.pi


def _lerp(span: tuple[float, float], t: float) -> float:
    return span[0] + (span[1] - span[0]) * t


def _cylinder(
    box: dict, mins: Vec3, maxs: Vec3, base: int, segments: int = CYLINDER_SEGMENTS
) -> tuple[list[Vec3], list[tuple[int, ...]], list[list[UV]], list[bool]]:
    """Elliptic cylinder inscribed in ``box``: ``segments`` side quads sharing their ring
    vertices (smooth) + top and bottom n-gon caps with their own vertices (flat, so the
    rim edge stays sharp). Face indices start at ``base``.

    UVs: the side wraps ``uv_u`` (default: its own X extent in the piece's front
    projection) with :func:`wrap_u` and spans ``uv_v`` bottom→top (default: its Z extent
    in the piece bbox). The top cap is projected planarly (X → u, front → back = v) onto
    ``cap_uv`` (default: the side's strip), the bottom cap onto the side's strip."""

    def norm(i: int, value: float) -> float:
        span = maxs[i] - mins[i]
        return (value - mins[i]) / span if span > 0 else 0.0

    (sx, sy, sz), (px, py, pz) = box["size_cm"], box["pos_cm"]
    rx, ry = sx / 2 * CM_TO_M, sy / 2 * CM_TO_M
    cx, cy = px * CM_TO_M, py * CM_TO_M
    z0, z1 = (pz - sz / 2) * CM_TO_M, (pz + sz / 2) * CM_TO_M
    taper = float(box.get("taper", 1.0))
    uv_u = tuple(box["uv_u"]) if box.get("uv_u") else (norm(0, cx - rx), norm(0, cx + rx))
    uv_v = tuple(box["uv_v"]) if box.get("uv_v") else (norm(2, z0), norm(2, z1))
    cap = box.get("cap_uv")
    cap_uv = (tuple(cap[0]), tuple(cap[1])) if cap else (uv_u, uv_v)
    thetas = [2 * math.pi * i / segments for i in range(segments)]
    rings = {
        "bottom": [
            (cx + taper * rx * math.cos(t), cy + taper * ry * math.sin(t), z0) for t in thetas
        ],
        "top": [(cx + rx * math.cos(t), cy + ry * math.sin(t), z1) for t in thetas],
    }
    verts = rings["bottom"] + rings["top"]
    faces: list[tuple[int, ...]] = []
    uvs: list[list[UV]] = []
    smooth: list[bool] = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((base + i, base + j, base + segments + j, base + segments + i))
        ui, uj = wrap_u(thetas[i], *uv_u), wrap_u(thetas[j], *uv_u)
        uvs.append([(ui, uv_v[0]), (uj, uv_v[0]), (uj, uv_v[1]), (ui, uv_v[1])])
        smooth.append(True)

    def cap_face(ring: list[Vec3], r: float, region, order: list[int]) -> None:
        start = base + len(verts)
        verts.extend(ring[k] for k in order)
        faces.append(tuple(range(start, start + segments)))
        ru, rv = r * rx, r * ry
        uvs.append(
            [
                (
                    _lerp(region[0], (ring[k][0] - cx + ru) / (2 * ru) if ru > 0 else 0.5),
                    _lerp(region[1], (ring[k][1] - cy + rv) / (2 * rv) if rv > 0 else 0.5),
                )
                for k in order
            ]
        )
        smooth.append(False)

    cap_face(rings["top"], 1.0, cap_uv, list(range(segments)))  # CCW from above: +Z
    cap_face(rings["bottom"], taper, (uv_u, uv_v), list(range(segments))[::-1])  # -Z
    return verts, faces, uvs, smooth


def build_mesh(
    boxes: list[dict],
    side_band: tuple[float, float] | None = None,
) -> tuple[list[Vec3], list[tuple[int, ...]], list[list[UV]], list[bool]]:
    """:func:`build_geometry` plus a per-face smooth-shading flag (cylinder sides only)."""
    corners: list[list[Vec3]] = [_box_vertices(box) for box in boxes]
    mins, maxs = bounds([v for box in corners for v in box])
    verts: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[list[UV]] = []
    smooth: list[bool] = []
    for spec_box, box in zip(boxes, corners, strict=True):
        if spec_box.get("shape", "box") == "cylinder":
            c_verts, c_faces, c_uvs, c_smooth = _cylinder(spec_box, mins, maxs, len(verts))
            verts.extend(c_verts)
            faces.extend(c_faces)
            uvs.extend(c_uvs)
            smooth.extend(c_smooth)
            continue
        uv_v = spec_box.get("uv_v")
        box_z = (box[0][2], box[4][2], (float(uv_v[0]), float(uv_v[1]))) if uv_v else None
        band = side_band if uv_v else None  # the band only applies to hinted (panel) boxes
        for name, idx in BOX_FACES:
            base = len(verts)
            quad = [box[i] for i in idx]
            verts.extend(quad)
            faces.append(tuple(range(base, base + 4)))
            uvs.append([planar_uv(FACE_NORMALS[name], v, mins, maxs, box_z, band) for v in quad])
            smooth.append(False)
    return verts, faces, uvs, smooth


def build_geometry(
    boxes: list[dict],
    side_band: tuple[float, float] | None = None,
) -> tuple[list[Vec3], list[tuple[int, ...]], list[list[UV]]]:
    """All boxes as one mesh: (vertices in m, faces, per-face loop UVs).

    Every quad of a box gets its own 4 vertices (24 per box) so faces never share
    UV-split corners; UVs come from :func:`planar_uv` against the bbox of the whole piece.
    Cylinder boxes are built by :func:`_cylinder` (quads + two n-gon caps).
    """
    verts, faces, uvs, _ = build_mesh(boxes, side_band)
    return verts, faces, uvs


# --------------------------------------------------------------------------- Blender side


def _material(bpy, texture: str | None):
    mat = bpy.data.materials.new("parametric")
    if bpy.app.version < (5, 0, 0):
        mat.use_nodes = True  # deprecated (always on) in 5.x
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.7
    if texture:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(texture, check_existing=True)
        tex.extension = "EXTEND"
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1.0)
    return mat


def main(argv: list[str]) -> int:
    import bpy  # only available inside Blender

    args = parse_args(script_argv(argv))
    with open(args.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    if not spec.get("boxes"):
        raise RuntimeError("La especificación no contiene cajas")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    band = (spec.get("extra") or {}).get("side_band")
    verts, faces, uvs, smooth = build_mesh(spec["boxes"], tuple(band) if band else None)
    mesh = bpy.data.meshes.new(spec.get("kind", "parametric"))
    mesh.from_pydata(verts, [], faces)
    mesh.polygons.foreach_set("use_smooth", smooth)
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly, face_uvs in zip(mesh.polygons, uvs, strict=True):
        for loop_index, uv in zip(poly.loop_indices, face_uvs, strict=True):
            uv_layer.data[loop_index].uv = uv
    mesh.validate()
    mesh.update()

    obj = bpy.data.objects.new(spec.get("kind", "parametric"), mesh)
    bpy.context.scene.collection.objects.link(obj)
    texture = spec.get("texture")
    obj.data.materials.append(_material(bpy, texture))

    bpy.ops.export_scene.gltf(
        filepath=args.out,
        export_format="GLB",
        export_yup=True,
        export_draco_mesh_compression_enable=bool(args.draco),
    )
    print(f"[bpy_parametric] OK {args.out} boxes={len(spec['boxes'])} faces={len(faces)}")
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv)
    except Exception as exc:  # noqa: BLE001 — surface any failure as a non-zero exit
        import traceback

        traceback.print_exc()
        print(f"[bpy_parametric] ERROR {exc}", file=sys.stderr)
        code = 1
    sys.exit(code)
