"""Blender-side render script. Runs INSIDE Blender, never imported by the harness.

    blender --background --python bpy_render.py -- <model.glb> <out_dir> <size>

Writes ``front.png``, ``side.png``, ``back.png``, ``three_quarter.png`` and ``top.png``
(``size``×``size``, white background) framing the whole object.

Engine: Workbench. It has no sampling (no noise, identical output on every run), no shader
compilation and renders each view in well under a second, versus seconds per view and
sample-dependent noise for Eevee. Cost: no PBR reflections, so metal/glass are shown by
base colour and texture only; the judge prompt says so.

Lighting (measured 2026-11-08, Blender 5.2.3): the "Default" studio light with shadows,
cavity and specular left a textured object ~30 % darker than its albedo (Workbench lights
in view space from above, so the faces seen from the front get little light), which lowered
the "materiales" score of every variant. Now: ``light="STUDIO"`` with the bundled
``paint.sl`` studio light (soft, frontal), ``show_shadows``/``show_cavity``/
``show_specular_highlight`` off, ``view_transform="Standard"``, ``look="None"``,
``exposure=0.15``, ``gamma=1``; world white, film opaque. FLAT lighting reproduces the
albedo exactly but loses every shape cue; ``paint.sl`` keeps the shading gradient and lands
within a few percent of FLAT. Mean luminance (Rec.709 on sRGB values) of the non-white
pixels, front view at 1024 px, run ``mcp-higgsfield`` vs the cleaned photo (lum / sat):

    piece / variant        photo          before (Default)   after (paint.sl, +0.15 EV)
    p04 MG_TRELLIS2        0.458 / 0.392  0.302 / 0.462      0.449 (-2 %) / 0.529
    p09 MG_TRELLIS2        0.241 / 0.241  0.221 / 0.201      0.253 (+5 %) / 0.347
    p13 HF_TRIPO_CLEAN     0.682 / 0.103  0.477 / 0.076      0.661 (-3 %) / 0.107

Saturation matches on p13 (+4 %). On p04/p09 MG_TRELLIS2 it ends +35 %/+44 % above the
photo, but their FLAT (unlit albedo) render is already 0.50/0.33: the excess is in the
generated texture, not in the lighting, and the judge should see it (the old specular
highlights were washing it out). ``pick_studio_light`` falls back
to ``Default`` if a Blender build lacks ``paint.sl``.

Orientation: the glTF importer maps glTF +Y up to Blender +Z and the glTF front (+Z) to
Blender -Y, so "front" looks from -Y towards +Y.

Textures: Workbench ``color_type="TEXTURE"`` shows "the texture from the active image
texture node" of each material (``View3DShading.color_type``, docs.blender.org/api/4.5,
consulted 2026-11-08). A PBR material imported from glTF has several image nodes (base
colour, normal, metallic-roughness...) and the active one is arbitrary, so before rendering
``activate_albedo_textures`` makes active the image node that feeds the Principled BSDF
``Base Color`` input (searching upstream through intermediate nodes such as Mix), falling
back to any image node. The selection (``albedo_image_node``) is pure Python over duck-typed
nodes (``.type``, ``.inputs``, ``socket.name``, ``socket.links``, ``link.from_node``) so it
is unit-tested outside Blender.

``bpy``/``mathutils`` are imported lazily so the helpers can be imported by the tests.
"""

import math
import sys
from pathlib import Path

VIEWS = {
    "front": (0.0, -1.0, 0.0),
    "side": (1.0, 0.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "three_quarter": (1.0, -1.0, 0.6),
    "top": (0.0, 0.0, 1.0),
}
LENS_MM = 50.0
SENSOR_MM = 36.0
MARGIN = 1.15


STUDIO_LIGHT = "paint.sl"
FALLBACK_STUDIO_LIGHT = "Default"
EXPOSURE = 0.15

IMAGE_NODE = "TEX_IMAGE"
PRINCIPLED_NODE = "BSDF_PRINCIPLED"
BASE_COLOR = "Base Color"


def _upstream_image(socket, seen: set[int]):
    """First image-texture node found walking upstream from ``socket`` (breadth-first)."""
    queue = [link.from_node for link in getattr(socket, "links", ())]
    while queue:
        node = queue.pop(0)
        if id(node) in seen:
            continue
        seen.add(id(node))
        if node.type == IMAGE_NODE:
            return node
        for inp in getattr(node, "inputs", ()):
            queue.extend(link.from_node for link in getattr(inp, "links", ()))
    return None


def albedo_image_node(nodes):
    """Image node feeding a Principled BSDF ``Base Color``; else any image node; else None."""
    nodes = list(nodes)
    seen: set[int] = set()
    for node in nodes:
        if node.type != PRINCIPLED_NODE:
            continue
        for inp in node.inputs:
            if inp.name == BASE_COLOR:
                found = _upstream_image(inp, seen)
                if found is not None:
                    return found
    return next((n for n in nodes if n.type == IMAGE_NODE), None)


def activate_albedo_textures(materials) -> int:
    """Set ``node_tree.nodes.active`` to the albedo image node; returns materials changed."""
    changed = 0
    for mat in materials:
        tree = getattr(mat, "node_tree", None)
        if tree is None:
            continue
        node = albedo_image_node(tree.nodes)
        if node is not None:
            tree.nodes.active = node
            changed += 1
    return changed


def pick_studio_light(available, preferred: str = STUDIO_LIGHT) -> str:
    """``preferred`` if Blender ships it, else the always-present ``Default`` light."""
    return preferred if preferred in set(available) else FALLBACK_STUDIO_LIGHT


def parse_args() -> tuple[Path, Path, int]:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 3:
        raise SystemExit("uso: -- <model.glb> <out_dir> <size>")
    return Path(argv[0]), Path(argv[1]), int(argv[2])


def setup_scene(size: int):
    import bpy  # type: ignore[import-not-found]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    view = scene.view_settings
    view.view_transform = "Standard"  # keep pure white as white, no filmic desaturation
    view.look = "None"
    view.exposure = EXPOSURE
    view.gamma = 1.0
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.studio_light = pick_studio_light(
        sl.name for sl in bpy.context.preferences.studio_lights
    )
    shading.show_shadows = False
    shading.show_cavity = False
    shading.show_specular_highlight = False
    shading.color_type = "TEXTURE"
    shading.show_backface_culling = False
    world = bpy.data.worlds.new("white")
    world.color = (1.0, 1.0, 1.0)  # Workbench renders the world colour as background
    scene.world = world
    return scene


def bounds(objects):
    from mathutils import Vector  # type: ignore[import-not-found]

    corners = [obj.matrix_world @ Vector(c) for obj in objects for c in obj.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    center = (lo + hi) / 2
    radius = max((c - center).length for c in corners)
    return center, max(radius, 1e-4)


def main() -> None:
    import bpy  # type: ignore[import-not-found]
    from mathutils import Vector  # type: ignore[import-not-found]

    glb, out_dir, size = parse_args()
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = setup_scene(size)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    bpy.context.view_layer.update()  # make matrix_world reflect the imported hierarchy
    meshes = [o for o in scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit(f"{glb}: sin objetos de malla")
    center, radius = bounds(meshes)
    n_tex = activate_albedo_textures(bpy.data.materials)
    print(f"[bpy_render] albedo activo en {n_tex} material(es)")

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
        direction = Vector(direction).normalized()
        camera.location = center + direction * distance
        if name == "top":
            camera.rotation_euler = (0.0, 0.0, 0.0)  # look down -Z, front at the bottom
        else:
            camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(out_dir / f"{name}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
