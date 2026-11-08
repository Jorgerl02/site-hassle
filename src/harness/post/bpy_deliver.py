"""Web delivery executed INSIDE Blender (5.x):

    BLENDER_BIN --background --python bpy_deliver.py -- --in model_post.glb
        --out-glb model_web.glb --out-usdz model.usdz --meta deliver_meta.json
        [--max-tris 60000] [--max-tex 2048] [--jpeg-quality 85] [--draco-level 6]
        [--tmp-dir DIR]

Steps: import the post-processed GLB (already scaled, base centre at the origin) → bake
transforms and join meshes → Decimate to ≤ max-tris triangles → clamp textures to ≤ max-tex
px → re-encode every texture as JPEG (quality ``--jpeg-quality``), or PNG when a material
uses its Alpha output and some pixel has alpha < 1 → export ``model_web.glb``
(Draco, images as JPEG; textures that really need alpha stay PNG) → export ``model.usdz``
with the USD exporter (UsdPreviewSurface materials, textures packed in the archive, Y-up,
metres) → META.json with sizes in bytes, triangles and textures.

A USDZ failure does not abort the GLB: it is recorded as ``usdz_error`` in the meta.

Why the re-encode pre-pass: the USD exporter copies packed images in their source format,
and generators (TRELLIS-2 via Higgsfield) emit WebP textures, which USDZ / AR Quick Look do
not accept (PNG and JPEG only); it also keeps the USDZ textures as compact JPEGs.

``bpy`` is imported lazily so that the argument parser can be unit-tested outside Blender.
Docs consulted on 2026-11-08: Blender 5.2 manual "Universal Scene Description" (USDZ by
``.usdz`` extension, Export Textures, USDZ Texture Downsampling, Convert Orientation, Units)
and the RNA of ``bpy.ops.wm.usd_export`` / ``bpy.ops.export_scene.gltf`` in Blender 5.2.3.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time

try:  # imported as part of the harness package (tests, wrapper)
    from harness.post.bpy_post import clamp_size, script_argv
except ImportError:  # running inside Blender: the sibling module is on the script dir
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bpy_post import clamp_size, script_argv  # type: ignore[no-redef]

DEFAULT_MAX_TRIS = 60_000
DEFAULT_MAX_TEX = 2048
DEFAULT_JPEG_QUALITY = 85
DEFAULT_DRACO_LEVEL = 6
USDZ_DOWNSCALE_PRESETS = (256, 512, 1024, 2048, 4096)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bpy_deliver")
    parser.add_argument("--in", dest="glb_in", required=True)
    parser.add_argument("--out-glb", dest="out_glb", required=True)
    parser.add_argument("--out-usdz", dest="out_usdz", required=True)
    parser.add_argument("--meta", dest="meta", required=True)
    parser.add_argument("--max-tris", dest="max_tris", type=int, default=DEFAULT_MAX_TRIS)
    parser.add_argument("--max-tex", dest="max_tex", type=int, default=DEFAULT_MAX_TEX)
    parser.add_argument(
        "--jpeg-quality", dest="jpeg_quality", type=int, default=DEFAULT_JPEG_QUALITY
    )
    parser.add_argument("--draco-level", dest="draco_level", type=int, default=DEFAULT_DRACO_LEVEL)
    parser.add_argument("--tmp-dir", dest="tmp_dir", default=None)
    ns = parser.parse_args(argv)
    if ns.max_tris < 1:
        parser.error("--max-tris debe ser ≥ 1")
    if ns.max_tex < 1:
        parser.error("--max-tex debe ser ≥ 1")
    if not 1 <= ns.jpeg_quality <= 100:
        parser.error("--jpeg-quality debe estar entre 1 y 100")
    return ns


def usdz_downscale(max_tex: int) -> tuple[str, int]:
    """``(usdz_downscale_size, usdz_downscale_custom_size)`` for the USD exporter."""
    if max_tex in USDZ_DOWNSCALE_PRESETS:
        return str(max_tex), max_tex
    return "CUSTOM", max_tex


def file_size(path: str) -> int | None:
    return os.path.getsize(path) if os.path.isfile(path) else None


# --------------------------------------------------------------------------- Blender side


def _clear_scene(bpy) -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _join_meshes(bpy, Matrix):  # noqa: N803 — mathutils class passed in
    """Bake world transforms into mesh data, drop non-mesh objects and join into one."""
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("El GLB no contiene mallas")
    for obj in meshes:
        world = obj.matrix_world.copy()
        obj.data = obj.data.copy()
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


def _alpha_linked(bpy, image) -> bool:
    """True when some material uses this image's Alpha output (transparency in use)."""
    for mat in bpy.data.materials:
        if mat.node_tree is None:
            continue
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image == image:
                alpha = node.outputs.get("Alpha")
                if alpha is not None and alpha.is_linked:
                    return True
    return False


def _has_real_alpha(image) -> bool:
    """True when the image has 4 channels and some pixel has alpha < 1."""
    if image.channels < 4:
        return False
    import numpy as np  # bundled with Blender

    w, h = image.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(buf)
    return bool((buf[3::4] < 0.999).any())


def _process_textures(bpy, max_px: int, quality: int, tmp_dir: str) -> list[dict]:
    """Clamp every texture to ``max_px`` and re-encode it as JPEG (or PNG when a material
    really uses its alpha), swapping the new image in. Besides the size win this turns the
    WebP textures some generators emit into formats USDZ / AR Quick Look accept (PNG/JPEG).
    """
    report = []
    for image in list(bpy.data.images):
        if image.type != "IMAGE" or image.size[0] == 0:
            continue
        w, h = int(image.size[0]), int(image.size[1])
        new_w, new_h = clamp_size(w, h, max_px)
        if (new_w, new_h) != (w, h):
            image.scale(new_w, new_h)
        alpha = _alpha_linked(bpy, image) and _has_real_alpha(image)
        fmt = "PNG" if alpha else "JPEG"
        safe = "".join(c if c.isalnum() else "_" for c in image.name)
        path = os.path.join(tmp_dir, f"{safe}.{'png' if alpha else 'jpg'}")
        # Image.save writes in the image's current file_format (WEBP for TRELLIS-2), not by
        # extension: set the target format explicitly.
        image.file_format = fmt
        image.save(filepath=path, quality=quality)
        encoded = bpy.data.images.load(path)
        encoded.colorspace_settings.name = image.colorspace_settings.name
        encoded.alpha_mode = image.alpha_mode
        encoded.pack()
        image.user_remap(encoded)
        report.append(
            {
                "name": image.name,
                "source_format": image.file_format,
                "before": [w, h],
                "after": [new_w, new_h],
                "alpha": alpha,
                "format": fmt,
                "encoded_bytes": os.path.getsize(path),
            }
        )
    return report


def _export_usdz(bpy, path: str, max_tex: int) -> None:
    size, custom = usdz_downscale(max_tex)
    bpy.ops.wm.usd_export(
        filepath=path,
        selected_objects_only=False,
        export_animation=False,
        export_materials=True,
        generate_preview_surface=True,
        export_textures_mode="NEW",
        overwrite_textures=True,
        export_uvmaps=True,
        export_normals=True,
        export_lights=False,
        export_cameras=False,
        triangulate_meshes=True,
        convert_orientation=True,
        export_global_forward_selection="NEGATIVE_Z",
        export_global_up_selection="Y",
        convert_scene_units="METERS",
        usdz_downscale_size=size,
        usdz_downscale_custom_size=custom,
    )


def main(argv: list[str]) -> int:
    import bpy  # only available inside Blender
    from mathutils import Matrix

    args = parse_args(script_argv(argv))
    start = time.monotonic()
    tmp_dir = args.tmp_dir or tempfile.mkdtemp(prefix="bpy_deliver_")
    os.makedirs(tmp_dir, exist_ok=True)

    _clear_scene(bpy)
    bpy.ops.import_scene.gltf(filepath=args.glb_in)
    obj = _join_meshes(bpy, Matrix)
    tris_before = _tri_count(obj)
    tris_after = _decimate(bpy, obj, args.max_tris)
    textures = _process_textures(bpy, args.max_tex, args.jpeg_quality, tmp_dir)

    for path in (args.out_glb, args.out_usdz):
        if os.path.exists(path):
            os.remove(path)
    bpy.ops.export_scene.gltf(
        filepath=args.out_glb,
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_yup=True,
        export_image_format="JPEG",
        export_image_quality=args.jpeg_quality,
        export_jpeg_quality=args.jpeg_quality,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=args.draco_level,
    )

    usdz_error = None
    try:
        _export_usdz(bpy, args.out_usdz, args.max_tex)
        if not os.path.isfile(args.out_usdz):
            usdz_error = "el exportador USD no escribió el archivo"
    except Exception as exc:  # noqa: BLE001 — the GLB is still useful without USDZ
        usdz_error = f"{type(exc).__name__}: {exc}"

    meta = {
        "glb_in": args.glb_in,
        "glb_out": args.out_glb,
        "usdz_out": args.out_usdz,
        "glb_in_bytes": file_size(args.glb_in),
        "glb_bytes": file_size(args.out_glb),
        "usdz_bytes": file_size(args.out_usdz),
        "usdz_error": usdz_error,
        "tris_before": tris_before,
        "tris_after": tris_after,
        "tris_within_limit": tris_after <= args.max_tris,
        "max_tris": args.max_tris,
        "max_tex": args.max_tex,
        "jpeg_quality": args.jpeg_quality,
        "draco": True,
        "draco_level": args.draco_level,
        "textures": textures,
        "blender_version": bpy.app.version_string,
        "seconds": time.monotonic() - start,
    }
    with open(args.meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")
    print(
        f"[bpy_deliver] OK glb={meta['glb_bytes']} B usdz={meta['usdz_bytes']} B "
        f"tris={tris_before}->{tris_after} usdz_error={usdz_error}"
    )
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv)
    except Exception as exc:  # noqa: BLE001 — surface any failure as a non-zero exit
        import traceback

        traceback.print_exc()
        print(f"[bpy_deliver] ERROR {exc}", file=sys.stderr)
        code = 1
    sys.exit(code)
