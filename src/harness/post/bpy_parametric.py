"""Parametric furniture builder executed INSIDE Blender (4.x), variant E:

    BLENDER_BIN --background --python bpy_parametric.py -- --spec SPEC.json --out OUT.glb [--draco]

Reads the box list written by ``harness.post.parametric_spec.write_spec`` (cm, X = width,
Y = depth with the front at -Y, Z = height, ``pos_cm`` = box centre), builds every box as
quads in ONE mesh, assigns UVs that project the cleaned photo onto the front (and back)
faces as seen from the front, the top/bottom faces from above and the sides from the side
(a box projection baked into UVs, so the glTF exporter keeps it), applies a Principled BSDF
with the photo as Base Color and exports a GLB (metres, +Y up).

Only the stdlib is used at import time: the geometry helpers are unit-tested outside
Blender, ``bpy`` is imported inside :func:`main`.
Blender docs consulted: https://docs.blender.org/api/4.5/ (Mesh.from_pydata, uv_layers,
ShaderNodeTexImage, BlendDataImages.load, bpy.ops.export_scene.gltf) on 2026-11-08.
"""

from __future__ import annotations

import argparse
import json
import sys

CM_TO_M = 0.01

Vec3 = tuple[float, float, float]
UV = tuple[float, float]

# Quad faces of a box, CCW seen from outside; vertex order in _box_vertices.
# (face name, vertex indices, outward axis)
BOX_FACES: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("bottom", (0, 3, 2, 1)),
    ("top", (4, 5, 6, 7)),
    ("front", (0, 1, 5, 4)),
    ("right", (1, 2, 6, 5)),
    ("back", (2, 3, 7, 6)),
    ("left", (3, 0, 4, 7)),
)


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


def _uv(face: str, v: tuple[float, float, float], mins, maxs) -> tuple[float, float]:
    def norm(i: int) -> float:
        span = maxs[i] - mins[i]
        return (v[i] - mins[i]) / span if span > 0 else 0.0

    if face in ("front", "back"):
        return norm(0), norm(2)  # photo seen from the front: u = X, v = Z
    if face in ("top", "bottom"):
        return norm(0), 1.0 - norm(1)  # seen from above: front edge at the bottom of the image
    return norm(1), norm(2)  # sides: u = Y, v = Z


def build_geometry(
    boxes: list[dict],
) -> tuple[list[Vec3], list[tuple[int, ...]], list[list[UV]]]:
    """All boxes as one mesh: (vertices in m, quad faces, per-face loop UVs)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    face_names: list[str] = []
    for box in boxes:
        base = len(verts)
        verts.extend(_box_vertices(box))
        for name, idx in BOX_FACES:
            faces.append(tuple(base + i for i in idx))
            face_names.append(name)
    mins, maxs = bounds(verts)
    uvs = [
        [_uv(name, verts[i], mins, maxs) for i in face]
        for name, face in zip(face_names, faces, strict=True)
    ]
    return verts, faces, uvs


# --------------------------------------------------------------------------- Blender side


def _material(bpy, texture: str | None):
    mat = bpy.data.materials.new("parametric")
    mat.use_nodes = True
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
