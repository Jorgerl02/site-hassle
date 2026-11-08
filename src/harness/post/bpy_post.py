"""Post-processing executed INSIDE Blender (4.x):

    BLENDER_BIN --background --python bpy_post.py -- --in IN.glb --out OUT.glb --meta META.json
        --width W --height H --depth D [--max-tris 150000] [--max-tex 2048] [--draco-level 6]

Steps: import GLB → bake transforms and join meshes → uniform scale so the bounding box on
the piece's largest axis equals its target measurement → signed relative error per axis →
origin at the centre of the base (min Z) placed at world origin → Decimate to ≤ max-tris
triangles → clamp textures to ≤ max-tex px → export GLB with Draco → write META.json.

Axis mapping (glTF Y-up is converted to Blender Z-up on import): X = width, Y = depth,
Z = height. Units: glTF metres, targets in cm.

``bpy`` is imported lazily so that the argument parser can be unit-tested outside Blender.
Blender docs consulted: https://docs.blender.org/api/4.5/ (bpy.ops.import_scene.gltf,
bpy.ops.export_scene.gltf, DecimateModifier, Image.scale) on 2026-11-08.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

DEFAULT_MAX_TRIS = 150_000
DEFAULT_MAX_TEX = 2048
DEFAULT_DRACO_LEVEL = 6
AXES = ("width", "depth", "height")  # Blender X, Y, Z


def script_argv(argv: list[str]) -> list[str]:
    """Arguments after ``--`` (Blender's own arguments come before it)."""
    return argv[argv.index("--") + 1 :] if "--" in argv else []


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bpy_post")
    parser.add_argument("--in", dest="glb_in", required=True)
    parser.add_argument("--out", dest="glb_out", required=True)
    parser.add_argument("--meta", dest="meta", required=True)
    parser.add_argument("--width", type=float, required=True)
    parser.add_argument("--height", type=float, required=True)
    parser.add_argument("--depth", type=float, required=True)
    parser.add_argument("--max-tris", dest="max_tris", type=int, default=DEFAULT_MAX_TRIS)
    parser.add_argument("--max-tex", dest="max_tex", type=int, default=DEFAULT_MAX_TEX)
    parser.add_argument("--draco-level", dest="draco_level", type=int, default=DEFAULT_DRACO_LEVEL)
    return parser.parse_args(argv)


def relative_errors(measured_cm: dict[str, float], target_cm: dict[str, float]) -> dict[str, float]:
    """Signed ``(measured - target) / target`` per axis."""
    return {k: (measured_cm[k] - target_cm[k]) / target_cm[k] for k in target_cm}


def clamp_size(width: int, height: int, max_px: int) -> tuple[int, int]:
    """Keep aspect ratio so that the longer side is ≤ ``max_px``."""
    longest = max(width, height)
    if longest <= max_px:
        return width, height
    factor = max_px / longest
    return max(1, round(width * factor)), max(1, round(height * factor))


# --------------------------------------------------------------------------- Blender side


def _clear_scene(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _join_meshes(bpy, Matrix):  # noqa: N803 — mathutils class passed in
    """Bake world transforms into mesh data, drop non-mesh objects and join into one."""
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("El GLB no contiene mallas")
    for obj in meshes:
        world = obj.matrix_world.copy()
        obj.data = obj.data.copy()  # single user, instances may share data
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_basis = Matrix.Identity(4)
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def _bbox(obj):
    xs, ys, zs = zip(*(v.co[:] for v in obj.data.vertices), strict=True)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _tri_count(obj) -> int:
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def _decimate(bpy, obj, max_tris: int) -> int:
    for _ in range(3):  # collapse is approximate; retry with a tighter ratio
        tris = _tri_count(obj)
        if tris <= max_tris:
            return tris
        mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = (max_tris / tris) * 0.98
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return _tri_count(obj)


def _clamp_textures(bpy, max_px: int) -> list[dict]:
    report = []
    for image in bpy.data.images:
        if image.type != "IMAGE" or image.size[0] == 0:
            continue
        w, h = int(image.size[0]), int(image.size[1])
        new_w, new_h = clamp_size(w, h, max_px)
        if (new_w, new_h) != (w, h):
            image.scale(new_w, new_h)
            if image.packed_file is not None:
                image.pack()  # re-pack the resized buffer so the exporter uses it
        report.append({"name": image.name, "before": [w, h], "after": [new_w, new_h]})
    return report


def main(argv: list[str]) -> int:
    import bpy  # only available inside Blender
    from mathutils import Matrix

    args = parse_args(script_argv(argv))
    start = time.monotonic()
    target = {"width": args.width, "depth": args.depth, "height": args.height}

    _clear_scene(bpy)
    bpy.ops.import_scene.gltf(filepath=args.glb_in)
    obj = _join_meshes(bpy, Matrix)
    tris_before = _tri_count(obj)

    (x0, y0, z0), (x1, y1, z1) = _bbox(obj)
    raw_cm = {"width": (x1 - x0) * 100, "depth": (y1 - y0) * 100, "height": (z1 - z0) * 100}
    main_axis = max(target, key=target.get)
    if raw_cm[main_axis] <= 0:
        raise RuntimeError(f"Caja envolvente degenerada en el eje {main_axis}")
    factor = target[main_axis] / raw_cm[main_axis]

    # Scale about the base centre, then move that point to the world origin.
    base = ((x0 + x1) / 2, (y0 + y1) / 2, z0)
    obj.data.transform(Matrix.Scale(factor, 4) @ Matrix.Translation([-c for c in base]))
    obj.data.update()

    (x0, y0, z0), (x1, y1, z1) = _bbox(obj)
    measured_cm = {"width": (x1 - x0) * 100, "depth": (y1 - y0) * 100, "height": (z1 - z0) * 100}
    errors = relative_errors(measured_cm, target)

    tris_after = _decimate(bpy, obj, args.max_tris)
    textures = _clamp_textures(bpy, args.max_tex)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=args.glb_out,
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_yup=True,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=args.draco_level,
    )

    meta = {
        "glb_in": args.glb_in,
        "glb_out": args.glb_out,
        "target_cm": target,
        "raw_cm": raw_cm,
        "measured_cm": measured_cm,
        "scale_axis": main_axis,
        "scale_factor": factor,
        "errors": errors,
        "tris_before": tris_before,
        "tris_after": tris_after,
        "max_tris": args.max_tris,
        "textures": textures,
        "draco": True,
        "blender_version": bpy.app.version_string,
        "seconds": time.monotonic() - start,
    }
    with open(args.meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"[bpy_post] OK {args.glb_out} errors={errors} tris={tris_before}->{tris_after}")
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv)
    except Exception as exc:  # noqa: BLE001 — surface any failure as a non-zero exit
        import traceback

        traceback.print_exc()
        print(f"[bpy_post] ERROR {exc}", file=sys.stderr)
        code = 1
    sys.exit(code)
