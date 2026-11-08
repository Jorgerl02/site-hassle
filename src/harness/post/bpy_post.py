"""Post-processing executed INSIDE Blender (4.x):

    BLENDER_BIN --background --python bpy_post.py -- --in IN.glb --out OUT.glb --meta META.json
        --width W --height H --depth D [--max-tris 150000] [--max-tex 2048]
        [--draco] [--draco-level 6] [--fit-box] [--fit-guard 0.10]

Steps: import GLB → bake transforms and join meshes → uniform scale by
max(target) / max(raw extent) over all three axes (independent of the model's orientation)
→ origin at the centre of the base (min Z) placed at world origin → Decimate to ≤ max-tris
triangles → clamp textures to ≤ max-tex px → measure (``errors_before_fit``) → optional
fit-to-box (below) → measure the final geometry (``errors`` follow the axis-matching rule
below, ``errors_axis`` compares named axes as is) → export GLB (Draco only with ``--draco``;
off by default because trimesh cannot decode it) → META.json.

Fit-to-box (``--fit-box``, off by default): if the absolute uniform-scale residual of EVERY
matched axis is ≤ ``--fit-guard`` (default 0.10), a non-uniform scale per Blender axis
(``fit_factors`` {x, y, z}) about the base-centre origin makes the bounding box match the
catalogue dimensions exactly (same axis-matching rule; the base stays at Z = 0). Otherwise
nothing is fitted and ``fit_skip_reason`` says which axes exceeded the guard. The pre-fit
residuals are always kept in ``errors_before_fit`` so the fit never hides a wrong shape.

Axis mapping (glTF Y-up is converted to Blender Z-up on import): X = width, Y = depth,
Z = height. Units: glTF metres, targets in cm.

Axis-matching rule for ``errors`` (shared with the evaluation, Task 6): HEIGHT is the
vertical extent (glTF +Y = Blender Z) compared with ``height_cm``; the two horizontal
extents are paired with ``width_cm``/``depth_cm`` by sorted size (forgives a rotation about
the vertical axis, catches a piece lying on its side). The scale factor is
``max(target_cm) / max(raw_cm)`` over all three axes.

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
DEFAULT_FIT_GUARD = 0.10  # max |residual| per matched axis for fit-to-box
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
    parser.add_argument("--draco", action="store_true", help="Draco mesh compression (off)")
    parser.add_argument("--draco-level", dest="draco_level", type=int, default=DEFAULT_DRACO_LEVEL)
    parser.add_argument(
        "--fit-box",
        dest="fit_box",
        action="store_true",
        help="Ajusta la caja envolvente a las medidas exactas si el error cabe en --fit-guard",
    )
    parser.add_argument("--fit-guard", dest="fit_guard", type=float, default=DEFAULT_FIT_GUARD)
    ns = parser.parse_args(argv)
    if ns.fit_guard < 0:
        parser.error("--fit-guard debe ser ≥ 0")
    return ns


def relative_errors(measured_cm: dict[str, float], target_cm: dict[str, float]) -> dict[str, float]:
    """Signed ``(measured - target) / target`` per NAMED axis (assumes aligned axes)."""
    return {k: (measured_cm[k] - target_cm[k]) / target_cm[k] for k in target_cm}


def matched_errors(measured_cm: dict[str, float], target_cm: dict[str, float]) -> dict[str, float]:
    """Signed errors keyed width/height/depth using the harness axis-matching rule.

    HEIGHT is the vertical extent (glTF +Y, Blender Z after import) compared with
    ``height_cm`` as is. The two horizontal extents (glTF X/Z, Blender X/Y) are paired with
    ``width_cm``/``depth_cm`` by sorted size, which forgives a rotation about the vertical
    axis but still flags a piece lying on its side. Same rule as the evaluation (Task 6).
    """
    errors = {"height": (measured_cm["height"] - target_cm["height"]) / target_cm["height"]}
    horizontal = sorted((measured_cm["width"], measured_cm["depth"]), reverse=True)
    targets = sorted(("width", "depth"), key=lambda k: target_cm[k], reverse=True)
    for name, extent in zip(targets, horizontal, strict=True):
        errors[name] = (extent - target_cm[name]) / target_cm[name]
    return errors


def uniform_scale_factor(raw_cm: dict[str, float], target_cm: dict[str, float]) -> float:
    """``max(target) / max(raw extent)`` over all three axes (rotation-independent)."""
    longest = max(raw_cm.values())
    if longest <= 0:
        raise ValueError("Caja envolvente degenerada")
    return max(target_cm.values()) / longest


def fit_guard_violations(errors: dict[str, float], guard: float) -> dict[str, float]:
    """Matched axes whose absolute residual exceeds ``guard`` (empty → the fit may apply)."""
    return {k: v for k, v in errors.items() if abs(v) > guard}


def fit_box_factors(
    measured_cm: dict[str, float], target_cm: dict[str, float], guard: float = DEFAULT_FIT_GUARD
) -> dict[str, float] | None:
    """Per-axis multipliers {x, y, z} (Blender space) that make the bounding box match the
    catalogue dimensions, or ``None`` when any matched axis is off by more than ``guard``.

    ``measured_cm`` is keyed by named Blender axis (width = X, depth = Y, height = Z), as
    ``_extents_cm`` returns it. Pairing follows :func:`matched_errors`: Z ↔ height; the
    longer horizontal extent ↔ the larger of width/depth, the shorter ↔ the smaller.
    """
    if min(measured_cm.values()) <= 0:
        return None
    if fit_guard_violations(matched_errors(measured_cm, target_cm), guard):
        return None
    horizontal = sorted(
        (("x", measured_cm["width"]), ("y", measured_cm["depth"])),
        key=lambda item: item[1],
        reverse=True,
    )
    targets = sorted(("width", "depth"), key=lambda k: target_cm[k], reverse=True)
    factors = {"z": target_cm["height"] / measured_cm["height"]}
    for (axis, extent), name in zip(horizontal, targets, strict=True):
        factors[axis] = target_cm[name] / extent
    return {axis: factors[axis] for axis in ("x", "y", "z")}


def fit_skip_reason(errors: dict[str, float], guard: float) -> str | None:
    """Human-readable reason (Spanish) why the fit was not applied, or ``None``."""
    over = fit_guard_violations(errors, guard)
    if not over:
        return None

    def pct(value: float, fmt: str) -> str:
        return f"{value * 100:{fmt}} %".replace(".", ",")

    detail = ", ".join(f"{k} {pct(v, '+.1f')}" for k, v in sorted(over.items()))
    return f"error fuera de la guarda (±{pct(guard, 'g')}): {detail}"


def clamp_size(width: int, height: int, max_px: int) -> tuple[int, int]:
    """Keep aspect ratio so that the longer side is ≤ ``max_px``."""
    longest = max(width, height)
    if longest <= max_px:
        return width, height
    factor = max_px / longest
    return max(1, round(width * factor)), max(1, round(height * factor))


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


def _extents_cm(obj) -> dict[str, float]:
    (x0, y0, z0), (x1, y1, z1) = _bbox(obj)
    return {"width": (x1 - x0) * 100, "depth": (y1 - y0) * 100, "height": (z1 - z0) * 100}


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
    raw_cm = _extents_cm(obj)
    factor = uniform_scale_factor(raw_cm, target)

    # Scale about the base centre, then move that point to the world origin.
    base = ((x0 + x1) / 2, (y0 + y1) / 2, z0)
    obj.data.transform(Matrix.Scale(factor, 4) @ Matrix.Translation([-c for c in base]))
    obj.data.update()

    tris_after = _decimate(bpy, obj, args.max_tris)
    textures = _clamp_textures(bpy, args.max_tex)

    # Uniform-scale residuals on the decimated geometry (what "errors" were before the fit).
    measured_before_cm = _extents_cm(obj)
    errors_before_fit = matched_errors(measured_before_cm, target)
    fit_factors = {"x": 1.0, "y": 1.0, "z": 1.0}
    fit_applied = False
    fit_reason: str | None = None
    if args.fit_box:
        factors = fit_box_factors(measured_before_cm, target, args.fit_guard)
        if factors is None:
            fit_reason = fit_skip_reason(errors_before_fit, args.fit_guard) or "caja degenerada"
        else:
            # Per-axis scale about the world origin = base centre, so the feet stay at Z = 0.
            obj.data.transform(Matrix.Diagonal((factors["x"], factors["y"], factors["z"], 1.0)))
            obj.data.update()
            fit_factors, fit_applied = factors, True

    # Measured on the final (decimated, possibly fitted) geometry that is exported.
    measured_cm = _extents_cm(obj)
    errors = matched_errors(measured_cm, target)
    errors_axis = relative_errors(measured_cm, target)

    bpy.ops.export_scene.gltf(
        filepath=args.glb_out,
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_yup=True,
        export_draco_mesh_compression_enable=bool(args.draco),
        export_draco_mesh_compression_level=args.draco_level,
    )

    meta = {
        "glb_in": args.glb_in,
        "glb_out": args.glb_out,
        "target_cm": target,
        "raw_cm": raw_cm,
        "measured_cm": measured_cm,
        "scale_rule": "max(target_cm) / max(raw_cm)",
        "scale_factor": factor,
        "errors_rule": "height = vertical extent; width/depth = horizontal extents by size",
        "errors": errors,
        "errors_axis": errors_axis,
        "fit_box_requested": bool(args.fit_box),
        "fit_box_applied": fit_applied,
        "fit_guard": args.fit_guard,
        "fit_factors": fit_factors,
        "fit_skip_reason": fit_reason,
        "measured_before_fit_cm": measured_before_cm,
        "errors_before_fit": errors_before_fit,
        "tris_before": tris_before,
        "tris_after": tris_after,
        "max_tris": args.max_tris,
        "textures": textures,
        "draco": bool(args.draco),
        "blender_version": bpy.app.version_string,
        "seconds": time.monotonic() - start,
    }
    with open(args.meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(
        f"[bpy_post] OK {args.glb_out} errors={errors} fit_box={fit_applied} "
        f"tris={tris_before}->{tris_after}"
    )
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
