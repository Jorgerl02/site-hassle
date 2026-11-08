"""Blender-side render script. Runs INSIDE Blender, never imported by the harness.

    blender --background --python bpy_render.py -- <model.glb> <out_dir> <size>

Writes ``front.png``, ``side.png``, ``back.png``, ``three_quarter.png`` and ``top.png``
(``size``×``size``, white background) framing the whole object.

Engine: Workbench. It has no sampling (no noise, identical output on every run), no shader
compilation and renders each view in well under a second, versus seconds per view and
sample-dependent noise for Eevee. Cost: no PBR reflections, so metal/glass are shown by
base colour and texture only; the judge prompt says so.

Orientation: the glTF importer maps glTF +Y up to Blender +Z and the glTF front (+Z) to
Blender -Y, so "front" looks from -Y towards +Y.
"""

import math
import sys
from pathlib import Path

import bpy  # type: ignore[import-not-found]
from mathutils import Vector  # type: ignore[import-not-found]

VIEWS = {
    "front": Vector((0.0, -1.0, 0.0)),
    "side": Vector((1.0, 0.0, 0.0)),
    "back": Vector((0.0, 1.0, 0.0)),
    "three_quarter": Vector((1.0, -1.0, 0.6)),
    "top": Vector((0.0, 0.0, 1.0)),
}
LENS_MM = 50.0
SENSOR_MM = 36.0
MARGIN = 1.15


def parse_args() -> tuple[Path, Path, int]:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 3:
        raise SystemExit("uso: -- <model.glb> <out_dir> <size>")
    return Path(argv[0]), Path(argv[1]), int(argv[2])


def setup_scene(size: int):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"  # keep pure white as white
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "TEXTURE"
    shading.show_backface_culling = False
    world = bpy.data.worlds.new("white")
    world.color = (1.0, 1.0, 1.0)  # Workbench renders the world colour as background
    scene.world = world
    return scene


def bounds(objects) -> tuple[Vector, float]:
    corners = [obj.matrix_world @ Vector(c) for obj in objects for c in obj.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    center = (lo + hi) / 2
    radius = max((c - center).length for c in corners)
    return center, max(radius, 1e-4)


def main() -> None:
    glb, out_dir, size = parse_args()
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = setup_scene(size)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    bpy.context.view_layer.update()  # make matrix_world reflect the imported hierarchy
    meshes = [o for o in scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit(f"{glb}: sin objetos de malla")
    center, radius = bounds(meshes)

    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = LENS_MM
    cam_data.sensor_width = SENSOR_MM
    cam_data.clip_start = radius * 0.01
    cam_data.clip_end = radius * 100
    camera = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    half_fov = math.atan(SENSOR_MM / 2 / LENS_MM)
    distance = radius * MARGIN / math.sin(half_fov)

    for name, direction in VIEWS.items():
        direction = direction.normalized()
        camera.location = center + direction * distance
        if name == "top":
            camera.rotation_euler = (0.0, 0.0, 0.0)  # look down -Z, front at the bottom
        else:
            camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(out_dir / f"{name}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
