"""Parametric furniture builder executed INSIDE Blender (4.x / 5.x), variant E:

    BLENDER_BIN --background --python bpy_parametric.py -- --spec SPEC.json --out OUT.glb [--draco]

Reads the box list written by ``harness.post.parametric_spec.write_spec`` (cm, X = width,
Y = depth with the front at -Y, Z = height, ``pos_cm`` = box centre), builds every box as
6 quads (4 own vertices each) in ONE mesh and bakes a planar, per-face projection of the
cleaned photo into the UVs (see :func:`planar_uv`), applies a Principled BSDF with the
photo as Base Color on every face and exports a GLB (metres, +Y up).

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


def planar_uv(normal: Vec3, v: Vec3, mins: Vec3, maxs: Vec3) -> UV:
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
    """

    def norm(i: int) -> float:
        span = maxs[i] - mins[i]
        return (v[i] - mins[i]) / span if span > 0 else 0.0

    axis = max(range(3), key=lambda i: abs(normal[i]))
    if axis == 1:  # front / back
        return norm(0), norm(2)
    if axis == 0:  # right / left
        return (1.0 - norm(1) if normal[0] > 0 else norm(1)), norm(2)
    return norm(0), 1.0 - TOP_BAND * norm(1)  # top / bottom


def build_geometry(
    boxes: list[dict],
) -> tuple[list[Vec3], list[tuple[int, ...]], list[list[UV]]]:
    """All boxes as one mesh: (vertices in m, quad faces, per-face loop UVs).

    Every quad gets its own 4 vertices (24 per box) so faces never share UV-split corners;
    UVs come from :func:`planar_uv` against the bbox of the whole piece.
    """
    corners: list[list[Vec3]] = [_box_vertices(box) for box in boxes]
    mins, maxs = bounds([v for box in corners for v in box])
    verts: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[list[UV]] = []
    for box in corners:
        for name, idx in BOX_FACES:
            base = len(verts)
            quad = [box[i] for i in idx]
            verts.extend(quad)
            faces.append(tuple(range(base, base + 4)))
            uvs.append([planar_uv(FACE_NORMALS[name], v, mins, maxs) for v in quad])
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

    verts, faces, uvs = build_geometry(spec["boxes"])
    mesh = bpy.data.meshes.new(spec.get("kind", "parametric"))
    mesh.from_pydata(verts, [], faces)
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
