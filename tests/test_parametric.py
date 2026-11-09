"""Parametric spec and variant E tests.

The real-Blender test is opt-in: set ``HARNESS_BLENDER_TEST_BIN=/path/to/blender`` (the
autouse fixture in conftest removes ``BLENDER_BIN``); it skips when unset.
"""

from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

import pytest
from PIL import Image

from harness.core.blender import BlenderNotAvailable, BlenderRun
from harness.core.models import Piece
from harness.post import bpy_parametric
from harness.post.parametric_spec import (
    BOX_SIDE_EDGE,
    BOX_TOP_CROP,
    KINDS,
    PEDESTAL_COLUMN_STRIP,
    PEDESTAL_RIM_STRIP,
    PEDESTAL_TOP_ROW,
    Box,
    Spec,
    bounding_box,
    build_spec,
    classify,
    classify_text,
    classify_with_params,
    make_spec,
    read_spec,
    write_spec,
)
from harness.prep import clean
from harness.variants import e_parametric
from harness.variants.e_parametric import (
    ParametricBuildError,
    ParametricVariant,
    crop_to_content,
    load_overrides,
    photo_regions,
)


def make_piece(
    tmp_path: Path, w: float, h: float, d: float, description: str = "", name: str = "X"
):
    return Piece(
        id="p99",
        name=name,
        store="Tienda",
        source_url="https://example.com",
        category="macizo_mate",
        images=[tmp_path / "1.jpg"],
        width_cm=w,
        height_cm=h,
        depth_cm=d,
        description=description,
    )


# ---------------------------------------------------------------- build_spec


def test_table_120x75x60_top_and_four_legs(piece: Piece) -> None:
    boxes = {b.name: b for b in build_spec(piece, "table")}
    assert set(boxes) == {"top", "leg_fl", "leg_fr", "leg_bl", "leg_br"}
    assert boxes["top"] == Box("top", (120.0, 60.0, 4.0), (0.0, 0.0, 73.0))
    assert boxes["leg_fl"] == Box("leg_fl", (5.0, 5.0, 71.0), (-52.5, -22.5, 35.5))
    assert boxes["leg_fr"] == Box("leg_fr", (5.0, 5.0, 71.0), (52.5, -22.5, 35.5))
    assert boxes["leg_bl"] == Box("leg_bl", (5.0, 5.0, 71.0), (-52.5, 22.5, 35.5))
    assert boxes["leg_br"] == Box("leg_br", (5.0, 5.0, 71.0), (52.5, 22.5, 35.5))


@pytest.mark.parametrize(
    "kind", ["table", "panel_table", "shelf", "sideboard", "slab", "box", "pedestal"]
)
@pytest.mark.parametrize("dims", [(120, 75, 60), (80, 180, 35), (200, 3, 90), (45, 45, 45)])
def test_union_bbox_matches_piece_dims(tmp_path: Path, kind: str, dims) -> None:
    w, h, d = dims
    boxes = build_spec(make_piece(tmp_path, w, h, d), kind)
    mins, maxs = bounding_box(boxes)
    assert mins == pytest.approx((-w / 2, -d / 2, 0.0))
    assert maxs == pytest.approx((w / 2, d / 2, h))
    assert all(s > 0 for b in boxes for s in b.size_cm)


def test_shelf_two_sides_four_boards(tmp_path: Path) -> None:
    boxes = build_spec(make_piece(tmp_path, 80, 180, 35), "shelf")
    sides = [b for b in boxes if b.name.startswith("side")]
    boards = [b for b in boxes if b.name.startswith("board")]
    assert len(sides) == 2 and len(boards) == 4
    assert all(b.size_cm[0] == 2.0 for b in sides)
    assert all(b.size_cm == (76.0, 35.0, 2.0) for b in boards)
    assert [b.pos_cm[2] for b in boards] == pytest.approx([1.0, 60.33333, 119.66667, 179.0])


def test_sideboard_body_doors_legs(tmp_path: Path) -> None:
    boxes = {b.name: b for b in build_spec(make_piece(tmp_path, 160, 80, 45), "sideboard")}
    assert boxes["body"].size_cm == (160.0, 43.0, 70.0)
    assert boxes["body"].pos_cm == (0.0, 1.0, 45.0)
    assert boxes["door_l"].size_cm == (79.75, 2.0, 70.0)
    assert boxes["door_l"].pos_cm == (-40.125, -21.5, 45.0)
    assert boxes["door_r"].pos_cm == (40.125, -21.5, 45.0)
    legs = [b for n, b in boxes.items() if n.startswith("leg")]
    assert len(legs) == 4 and all(b.size_cm == (5.0, 5.0, 10.0) for b in legs)


def test_slab_and_box_are_single_boxes(tmp_path: Path) -> None:
    p = make_piece(tmp_path, 200, 3, 90)
    assert build_spec(p, "slab") == [Box("slab", (200.0, 90.0, 3.0), (0.0, 0.0, 1.5))]
    assert len(build_spec(p, "box")) == 1


def test_unknown_kind_raises(piece: Piece) -> None:
    with pytest.raises(ValueError, match="desconocido"):
        build_spec(piece, "chair")


# ---------------------------------------------------------------- classify


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Mesa de comedor de roble macizo", "table"),
        ("Mesita auxiliar de nogal", "table"),
        ("Estantería de pino con 4 baldas", "shelf"),
        ("ESTANTERIA metálica", "shelf"),
        ("Aparador de madera con dos puertas", "sideboard"),
        ("Cómoda de 3 cajones", "sideboard"),
        ("Encimera de travertino pulido", "slab"),
        ("Losa de mármol", "slab"),
        ("Tablero de travertino para mesa", "slab"),
        ("Mesa con tablero de travertino", "table"),
        ("Sofá de tres plazas", None),
    ],
)
def test_classify_text_spanish(text: str, kind: str | None) -> None:
    assert classify_text(text) == kind


def test_classify_uses_description_then_name(tmp_path: Path) -> None:
    assert classify(make_piece(tmp_path, 120, 75, 60, "Aparador nórdico")) == "sideboard"
    assert classify(make_piece(tmp_path, 120, 75, 60, "Roble macizo", name="Mesa Oslo")) == "table"


def test_classify_by_proportions(tmp_path: Path) -> None:
    assert classify(make_piece(tmp_path, 200, 3, 90)) == "slab"
    assert classify(make_piece(tmp_path, 80, 180, 35)) == "shelf"
    assert classify(make_piece(tmp_path, 50, 50, 50)) == "box"


# ---------------------------------------------------------------- spec JSON


def test_spec_json_round_trip(piece: Piece, tmp_path: Path) -> None:
    spec = make_spec(piece, "table", texture=tmp_path / "t.png")
    path = write_spec(tmp_path / "sub" / "spec.json", spec)
    loaded = read_spec(path)
    assert loaded == spec
    assert loaded.dims_cm == (120.0, 60.0, 75.0)
    assert loaded.texture == str(tmp_path / "t.png")
    assert isinstance(loaded.boxes[0], Box)


def test_spec_rejects_bad_box() -> None:
    with pytest.raises(ValueError):
        Spec.from_dict(
            {"kind": "box", "boxes": [{"name": "a", "size_cm": [1, 2], "pos_cm": [0, 0, 0]}]}
        )


# ---------------------------------------------------------------- bpy_parametric pure helpers


def test_bpy_parametric_args() -> None:
    argv = ["blender", "--python", "x.py", "--", "--spec", "s.json", "--out", "o.glb"]
    ns = bpy_parametric.parse_args(bpy_parametric.script_argv(argv))
    assert (ns.spec, ns.out, ns.draco) == ("s.json", "o.glb", False)


def test_build_geometry_metres_and_uvs(piece: Piece) -> None:
    boxes = [b.to_dict() for b in build_spec(piece, "table")]
    verts, faces, uvs = bpy_parametric.build_geometry(boxes)
    # 6 quads per box, each with its own 4 vertices.
    assert len(verts) == 5 * 24 and len(faces) == 5 * 6
    assert all(len(f) == 4 for f in faces) and all(len(f) == 4 for f in uvs)
    assert sorted(i for f in faces for i in f) == list(range(len(verts)))
    mins, maxs = bpy_parametric.bounds(verts)
    assert mins == pytest.approx((-0.6, -0.3, 0.0))
    assert maxs == pytest.approx((0.6, 0.3, 0.75))
    assert all(0.0 <= c <= 1.0 for face in uvs for uv in face for c in uv)
    # Top box front face (index 2) spans the full width and the top 4 cm of the photo.
    front = uvs[2]
    assert sorted(u for u, _ in front) == pytest.approx([0.0, 0.0, 1.0, 1.0])
    assert sorted(v for _, v in front) == pytest.approx([71 / 75, 71 / 75, 1.0, 1.0])
    # Front-left leg (box 1) front face: the photo's bottom-left (leg) region, not 0-width.
    leg_front = uvs[6 + 2]
    us = sorted(u for u, _ in leg_front)
    assert us == pytest.approx([5 / 120, 5 / 120, 10 / 120, 10 / 120])
    assert sorted(v for _, v in leg_front) == pytest.approx([0.0, 0.0, 71 / 75, 71 / 75])


def test_every_quad_uv_is_planar(piece: Piece) -> None:
    """UVs are an affine function of position on each quad (both triangles agree)."""
    boxes = [b.to_dict() for b in build_spec(piece, "table")]
    verts, faces, uvs = bpy_parametric.build_geometry(boxes)
    for face, face_uv in zip(faces, uvs, strict=True):
        p = [verts[i] for i in face]
        # Opposite corners of a parallelogram: p0 + p2 == p1 + p3, same for UVs.
        assert [p[0][k] + p[2][k] for k in range(3)] == pytest.approx(
            [p[1][k] + p[3][k] for k in range(3)]
        )
        assert [face_uv[0][k] + face_uv[2][k] for k in range(2)] == pytest.approx(
            [face_uv[1][k] + face_uv[3][k] for k in range(2)]
        )
        assert len({tuple(round(c, 9) for c in uv) for uv in face_uv}) == 4  # no degenerate


BBOX = ((-0.5, -0.25, 0.0), (0.5, 0.25, 0.8))  # 1 m wide, 0.5 m deep, 0.8 m high


@pytest.mark.parametrize(
    ("normal", "point", "expected"),
    [
        # front (-Y) and back (+Y): u = X, v = Z over the whole piece bbox
        ((0, -1, 0), (-0.5, -0.25, 0.0), (0.0, 0.0)),
        ((0, -1, 0), (0.5, -0.25, 0.8), (1.0, 1.0)),
        ((0, -1, 0), (0.0, -0.25, 0.2), (0.5, 0.25)),
        ((0, 1, 0), (0.25, 0.25, 0.4), (0.75, 0.5)),
        # right (+X): u = 1 - Y (front edge -> u = 1, same column as the front face)
        ((1, 0, 0), (0.5, -0.25, 0.4), (1.0, 0.5)),
        ((1, 0, 0), (0.5, 0.25, 0.8), (0.0, 1.0)),
        # left (-X): u = Y (front edge -> u = 0, same column as the front face)
        ((-1, 0, 0), (-0.5, -0.25, 0.0), (0.0, 0.0)),
        ((-1, 0, 0), (-0.5, 0.0, 0.8), (0.5, 1.0)),
        # top / bottom: u = X, v = top band of the photo, front edge = top row
        ((0, 0, 1), (-0.5, -0.25, 0.8), (0.0, 1.0)),
        ((0, 0, 1), (0.5, 0.25, 0.8), (1.0, 1.0 - bpy_parametric.TOP_BAND)),
        ((0, 0, -1), (0.0, 0.0, 0.0), (0.5, 1.0 - bpy_parametric.TOP_BAND / 2)),
    ],
)
def test_planar_uv(normal, point, expected) -> None:
    assert bpy_parametric.planar_uv(normal, point, *BBOX) == pytest.approx(expected)


def test_planar_uv_front_edges_continuous() -> None:
    """Points on the front vertical/top edges get the same UV from both adjacent faces."""
    front = (0, -1, 0)
    for point, other in [
        ((0.5, -0.25, 0.3), (1, 0, 0)),
        ((-0.5, -0.25, 0.3), (-1, 0, 0)),
        ((0.1, -0.25, 0.8), (0, 0, 1)),
    ]:
        assert bpy_parametric.planar_uv(other, point, *BBOX) == pytest.approx(
            bpy_parametric.planar_uv(front, point, *BBOX)
        )


def test_planar_uv_degenerate_bbox() -> None:
    assert bpy_parametric.planar_uv((0, -1, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)) == (0.0, 0.0)


def test_box_faces_point_outwards() -> None:
    verts, faces, _ = bpy_parametric.build_geometry(
        [{"name": "b", "size_cm": [2, 2, 2], "pos_cm": [0, 0, 1]}]
    )
    expected = {"bottom": (0, 0, -1), "top": (0, 0, 1), "front": (0, -1, 0),
                "right": (1, 0, 0), "back": (0, 1, 0), "left": (-1, 0, 0)}  # fmt: skip
    for (name, _), face in zip(bpy_parametric.BOX_FACES, faces, strict=True):
        a, b, c = (verts[i] for i in face[:3])
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - b[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        assert tuple(int(round(x / max(abs(y) for y in n))) for x in n) == expected[name]


# ---------------------------------------------------------------- variant E


def test_variant_name() -> None:
    assert ParametricVariant().name == "E"


def test_variant_without_blender_raises(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here
    with pytest.raises(BlenderNotAvailable):
        ParametricVariant().run(piece, tmp_path / "E")


def _setup_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, returncode: int = 0):
    calls: list[dict] = []

    def fake_clean(src: Path, dst: Path, size: int = 1024) -> Path:
        img = Image.new("RGB", (100, 100), "white")
        img.paste((120, 80, 40), (10, 20, 90, 70))
        img.save(dst)
        return dst

    def fake_run(script: Path, args: list[str], timeout: int = 600, blender_bin=None):
        calls.append({"script": script, "args": args, "blender_bin": blender_bin})
        if returncode == 0:
            Path(args[args.index("--out") + 1]).write_bytes(b"glb")
        return BlenderRun(["blender", *args], returncode, "out", "boom", 0.5)

    monkeypatch.setattr(clean, "clean_image", fake_clean)
    monkeypatch.setattr(e_parametric, "run_blender_script", fake_run)
    binary = tmp_path / "blender"
    binary.write_text("")
    return binary, calls


def test_variant_builds_one_candidate(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, tmp_path: Path
) -> None:
    binary, calls = _setup_fake(monkeypatch, tmp_path)
    workdir = tmp_path / "E"
    result = ParametricVariant(blender_bin=binary).run(piece, workdir, candidates=2)

    assert result.variant == "E" and result.piece_id == "p01"
    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert cand.index == 1 and cand.cost_usd == 0.0
    assert cand.glb_path == workdir / "cand_1" / "model.glb" and cand.glb_path.is_file()
    assert cand.meta["kind"] == "table" and cand.meta["n_boxes"] == 5
    assert calls[0]["script"] == e_parametric.BPY_PARAMETRIC_SCRIPT
    assert calls[0]["script"].is_file()
    assert calls[0]["blender_bin"] == binary
    spec = read_spec(Path(calls[0]["args"][calls[0]["args"].index("--spec") + 1]))
    assert spec.kind == "table" and Path(spec.texture).is_file()
    with Image.open(spec.texture) as tex:
        assert tex.size == (80, 50)  # cropped to the object, no white padding
    assert "table" in result.notes


def test_variant_texture_falls_back_to_original(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, tmp_path: Path
) -> None:
    binary, _ = _setup_fake(monkeypatch, tmp_path)

    def failing_clean(src: Path, dst: Path, size: int = 1024) -> Path:
        raise ValueError("sin objeto")

    monkeypatch.setattr(clean, "clean_image", failing_clean)
    result = ParametricVariant(blender_bin=binary).run(piece, tmp_path / "E")
    assert result.candidates[0].meta["texture"] == str(piece.images[0])


def test_variant_blender_failure_raises_with_log(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, tmp_path: Path
) -> None:
    binary, _ = _setup_fake(monkeypatch, tmp_path, returncode=1)
    with pytest.raises(ParametricBuildError, match="boom"):
        ParametricVariant(blender_bin=binary).run(piece, tmp_path / "E")
    assert (tmp_path / "E" / "cand_1" / "parametric_blender.log").is_file()


def _has_white_border(img: Image.Image) -> bool:
    w, h = img.size
    px = img.convert("RGB").load()
    edges = [
        [px[x, 0] for x in range(w)],
        [px[x, h - 1] for x in range(w)],
        [px[0, y] for y in range(h)],
        [px[w - 1, y] for y in range(h)],
    ]
    return any(all(p == (255, 255, 255) for p in edge) for edge in edges)


def test_crop_to_content_removes_white_padding(tmp_path: Path) -> None:
    src = tmp_path / "clean.png"
    img = Image.new("RGB", (200, 200), "white")
    img.paste((90, 60, 30), (30, 50, 170, 150))
    img.putpixel((100, 100), (255, 255, 255))  # white inside the object is kept
    img.save(src)
    assert _has_white_border(Image.open(src))

    out = crop_to_content(src, tmp_path / "cropped.png")
    with Image.open(out) as cropped:
        assert cropped.size == (140, 100)
        assert not _has_white_border(cropped)


def test_crop_to_content_ignores_near_white_noise(tmp_path: Path) -> None:
    src = tmp_path / "clean.png"
    img = Image.new("RGB", (100, 100), (252, 253, 251))  # JPEG-ish off-white background
    img.paste((10, 10, 10), (40, 40, 60, 60))
    img.save(src)
    with Image.open(crop_to_content(src, tmp_path / "c.png")) as cropped:
        assert cropped.size == (20, 20)


def test_crop_to_content_all_white_unchanged(tmp_path: Path) -> None:
    src = tmp_path / "blank.png"
    Image.new("RGB", (30, 20), "white").save(src)
    with Image.open(crop_to_content(src, tmp_path / "c.png")) as out:
        assert out.size == (30, 20)


def test_fill_background_removes_white(tmp_path: Path) -> None:
    src = tmp_path / "t.png"
    img = Image.new("RGB", (60, 40), "white")
    img.paste((120, 80, 40), (0, 0, 60, 10))  # top band (table top)
    img.paste((30, 20, 10), (0, 10, 10, 40))  # left leg
    img.paste((200, 0, 0), (50, 10, 60, 40))  # right leg
    img.save(src)
    out = e_parametric.fill_background(src, erode=0)
    with Image.open(out) as filled:
        px = filled.convert("RGB").load()
        assert all(px[x, y] != (255, 255, 255) for x in range(60) for y in range(40))
        assert px[20, 25] == (30, 20, 10)  # nearest object pixel in the row: left leg
        assert px[40, 25] == (200, 0, 0)  # ... right leg
        assert px[30, 5] == (120, 80, 40)  # object pixels untouched


def test_fill_background_rows_without_object_use_columns(tmp_path: Path) -> None:
    src = tmp_path / "t.png"
    img = Image.new("RGB", (20, 20), "white")
    img.paste((10, 90, 10), (0, 0, 20, 5))
    img.save(src)
    with Image.open(e_parametric.fill_background(src, erode=0)) as filled:
        assert filled.convert("RGB").getpixel((7, 18)) == (10, 90, 10)


def test_fill_background_erodes_halo_and_keeps_blank(tmp_path: Path) -> None:
    src = tmp_path / "t.png"
    img = Image.new("RGB", (30, 30), "white")
    img.paste((235, 235, 235), (5, 5, 25, 25))  # light anti-aliased halo
    img.paste((50, 50, 50), (7, 7, 23, 23))
    img.save(src)
    with Image.open(e_parametric.fill_background(src)) as filled:
        rgb = filled.convert("RGB")
        assert rgb.getpixel((0, 15)) == (50, 50, 50)
        assert rgb.getpixel((6, 15)) == (50, 50, 50)
    blank = tmp_path / "blank.png"
    Image.new("RGB", (8, 8), "white").save(blank)
    with Image.open(e_parametric.fill_background(blank)) as out:
        assert out.getpixel((3, 3)) == (255, 255, 255)


def test_variant_real_blender(piece: Piece, tmp_path: Path) -> None:
    value = os.environ.get("HARNESS_BLENDER_TEST_BIN", "").strip()
    if not value or not Path(value).is_file():
        pytest.skip("Blender real no solicitado (HARNESS_BLENDER_TEST_BIN)")
    binary = Path(value)
    photo = tmp_path / "1.jpg"
    Image.new("RGB", (1200, 900), (140, 100, 60)).save(photo)
    texture = tmp_path / "texture.png"
    shutil.copyfile(photo, texture)
    spec = write_spec(tmp_path / "spec.json", make_spec(piece, "table", texture=texture))
    from harness.core.blender import run_blender_script

    out = tmp_path / "model.glb"
    run = run_blender_script(
        e_parametric.BPY_PARAMETRIC_SCRIPT, ["--spec", str(spec), "--out", str(out)],
        blender_bin=binary,
    )  # fmt: skip
    assert run.ok, run.stderr
    import numpy as np
    import trimesh

    mesh = trimesh.load(out, force="mesh", process=False)
    assert sorted(mesh.extents) == pytest.approx(sorted([1.2, 0.75, 0.6]), rel=1e-3)
    # 5 boxes x 6 quads -> 12 triangles per box, all textured with the same image.
    assert len(mesh.faces) == 5 * 12
    uv = mesh.visual.uv
    assert uv is not None and len(uv) == len(mesh.vertices)
    material = mesh.visual.material
    image = getattr(material, "baseColorTexture", None) or getattr(material, "image", None)
    assert image is not None and image.size == (1200, 900)
    # glTF is +Y up: Blender (x, y, z) == glTF (x, -z, y). Every triangle's UVs must be
    # the planar projection of its own vertices (both triangles of a quad agree).
    z_up = np.column_stack([mesh.vertices[:, 0], -mesh.vertices[:, 2], mesh.vertices[:, 1]])
    mins, maxs = tuple(z_up.min(axis=0)), tuple(z_up.max(axis=0))
    normals = np.column_stack(
        [mesh.face_normals[:, 0], -mesh.face_normals[:, 2], mesh.face_normals[:, 1]]
    )
    for tri, normal in zip(mesh.faces, normals, strict=True):
        for i in tri:
            expected = bpy_parametric.planar_uv(tuple(normal), tuple(z_up[i]), mins, maxs)
            assert tuple(uv[i]) == pytest.approx(expected, abs=1e-4)


def test_variant_not_applicable_on_organic_piece(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # no Blender needed: it declines before checking
    organic = piece.model_copy(update={"rectilinear": False})
    result = ParametricVariant().run(organic, tmp_path / "E")
    assert result.candidates == [] and result.notes == "no aplicable: pieza orgánica"
    from harness.core.variant import is_not_applicable

    assert is_not_applicable(result)


@pytest.mark.parametrize("label", [True, None])
def test_variant_runs_on_rectilinear_or_unknown(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, tmp_path: Path, label: bool | None
) -> None:
    binary, calls = _setup_fake(monkeypatch, tmp_path)
    result = ParametricVariant(blender_bin=binary).run(
        piece.model_copy(update={"rectilinear": label}), tmp_path / "E"
    )
    assert len(result.candidates) == 1 and len(calls) == 1


# ---------------------------------------------------------------- panel_table


PANEL_CASES = [
    {"panel_layout": "sides"},
    {"panel_layout": "sides", "shelf_height_cm": 27, "panel_thickness": 2.5, "panel_inset": 0},
    {"panel_layout": "pairs"},
    {"panel_layout": "pairs", "panel_pair_shape": "L", "panel_fin_length": 30, "panel_inset": 15},
    {"panel_layout": "pairs", "shelf_height_cm": 20, "top_thickness": 6},
]


@pytest.mark.parametrize("params", PANEL_CASES)
@pytest.mark.parametrize("dims", [(135, 38, 79), (35, 50, 35), (45, 45, 45), (200, 3, 90)])
def test_panel_table_bbox_exact(tmp_path: Path, params, dims) -> None:
    w, h, d = dims
    boxes = build_spec(make_piece(tmp_path, w, h, d), "panel_table", params)
    mins, maxs = bounding_box(boxes)
    assert mins == pytest.approx((-w / 2, -d / 2, 0.0))
    assert maxs == pytest.approx((w / 2, d / 2, h))
    assert all(s > 0 for b in boxes for s in b.size_cm)


def test_panel_table_sides_defaults(tmp_path: Path) -> None:
    boxes = {b.name: b for b in build_spec(make_piece(tmp_path, 100, 50, 40), "panel_table")}
    assert set(boxes) == {"top", "panel_l", "panel_r"}  # no shelf unless requested
    assert boxes["top"] == Box("top", (100.0, 40.0, 4.0), (0.0, 0.0, 48.0))
    # inset 8 % of 100 = 8 cm from the top's edge to the panel's outer face, 3 cm thick
    assert boxes["panel_r"].size_cm == (3.0, 40.0, 46.0)
    assert boxes["panel_r"].pos_cm[0] + 1.5 == pytest.approx(50 - 8)
    assert boxes["panel_l"].pos_cm[0] - 1.5 == pytest.approx(-(50 - 8))


def test_panel_table_sides_shelf_p07(tmp_path: Path) -> None:
    params = {"panel_layout": "sides", "shelf_height_cm": 27, "panel_thickness": 2.5}
    params |= {"panel_inset": 0, "top_thickness": 2.5}
    boxes = {b.name: b for b in build_spec(make_piece(tmp_path, 35, 50, 35), "panel_table", params)}
    assert set(boxes) == {"top", "panel_l", "panel_r", "shelf"}
    assert boxes["panel_l"].pos_cm[0] - 1.25 == pytest.approx(-17.5)  # flush with the edge
    shelf = boxes["shelf"]
    assert shelf.size_cm == pytest.approx((30.0, 35.0, 2.5))  # between the panels' inner faces
    assert shelf.pos_cm[2] + shelf.size_cm[2] / 2 == pytest.approx(27.0)  # top face at 27 cm


def test_panel_table_pairs_t_and_l(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 135, 38, 79)
    t = {b.name: b for b in build_spec(piece, "panel_table", {"panel_layout": "pairs"})}
    assert set(t) == {"top", "panel_l", "panel_l_fin", "panel_r", "panel_r_fin"}
    inset = 0.08 * 135
    assert t["panel_r"].size_cm == pytest.approx((3.0, 79 - 2 * inset, 34.0))
    assert t["panel_r"].pos_cm[0] + 1.5 == pytest.approx(67.5 - inset)
    fin = t["panel_r_fin"]
    assert fin.size_cm == pytest.approx((39.5, 3.0, 34.0))  # 50 % of the depth
    assert fin.pos_cm[1] == 0.0  # T: mid-depth
    assert fin.pos_cm[0] + fin.size_cm[0] / 2 == pytest.approx(67.5 - inset - 3.0)  # touches
    params = {"panel_layout": "pairs", "panel_pair_shape": "L", "panel_fin_length": 30}
    lshape = {b.name: b for b in build_spec(piece, "panel_table", params)}
    end, fin = lshape["panel_l"], lshape["panel_l_fin"]
    assert fin.size_cm[0] == 30.0
    # L: the fin's front face is flush with the end panel's front end
    assert fin.pos_cm[1] - 1.5 == pytest.approx(end.pos_cm[1] - end.size_cm[1] / 2)


@pytest.mark.parametrize(
    "params",
    [{"panel_layout": "x"}, {"panel_pair_shape": "U"}, {"legs": 4}],
)
def test_panel_table_rejects_bad_params(piece: Piece, params) -> None:
    with pytest.raises(ValueError, match="panel_table"):
        build_spec(piece, "panel_table", params)


def test_params_rejected_for_other_kinds(piece: Piece) -> None:
    with pytest.raises(ValueError, match="no admite"):
        build_spec(piece, "box", {"panel_layout": "sides"})


def test_panel_table_photo_regions(piece: Piece) -> None:
    spec = make_spec(
        piece,
        "panel_table",
        params={"shelf_height_cm": 30},
        photo_regions={"top_row": 0.25, "side_band": [0.1, 0.4]},
    )
    boxes = {b.name: b for b in spec.boxes}
    assert spec.extra["side_band"] == [0.1, 0.4]
    assert spec.extra["params"] == {"shelf_height_cm": 30}
    assert boxes["top"].uv_v == pytest.approx((0.75, 0.81))
    assert boxes["panel_l"].uv_v[0] == pytest.approx(0.04)
    assert boxes["panel_l"].uv_v[1] == pytest.approx(0.75)
    assert 0.04 < boxes["shelf"].uv_v[0] < boxes["shelf"].uv_v[1] < 0.75
    assert Spec.from_dict(spec.to_dict()) == spec  # uv_v survives the JSON round trip
    plain = make_spec(piece, "table", photo_regions={"top_row": 0.25, "side_band": [0, 1]})
    assert all(b.uv_v is None for b in plain.boxes) and "side_band" not in plain.extra


def test_planar_uv_box_z_and_side_band() -> None:
    mins, maxs = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    box_z = (0.0, 0.5, (0.1, 0.6))
    assert bpy_parametric.planar_uv((0, -1, 0), (0.5, 0, 0.5), mins, maxs, box_z) == (
        pytest.approx(0.5),
        pytest.approx(0.6),
    )
    u, v = bpy_parametric.planar_uv((-1, 0, 0), (0, 0.5, 0.0), mins, maxs, box_z, (0.2, 0.4))
    assert (u, v) == (pytest.approx(0.3), pytest.approx(0.1))
    u, v = bpy_parametric.planar_uv((0, 0, 1), (1.0, 0.0, 1.0), mins, maxs, None, (0.2, 0.4))
    assert (u, v) == (pytest.approx(0.4), pytest.approx(bpy_parametric.BAND_V0))


def test_build_geometry_uses_box_hints() -> None:
    boxes = [
        {"name": "top", "size_cm": [10, 10, 2], "pos_cm": [0, 0, 9], "uv_v": [0.7, 0.8]},
        {"name": "leg", "size_cm": [2, 2, 8], "pos_cm": [0, 0, 4]},
    ]
    _, _, uvs = bpy_parametric.build_geometry(boxes, side_band=(0.2, 0.4))
    top_front = uvs[2]  # box 0, face "front"
    assert sorted({round(v, 6) for _, v in top_front}) == [0.7, 0.8]
    leg_left = uvs[6 + 5]  # box 1 has no hints: no band, straight projection
    assert all(0.0 <= u <= 1.0 for u, _ in leg_left)
    assert {round(v, 6) for _, v in leg_left} == {0.0, 0.8}


def test_photo_regions_detects_top_and_solid_band(tmp_path: Path) -> None:
    img = Image.new("RGB", (100, 100), "white")
    img.paste((120, 80, 40), (0, 0, 100, 20))  # top: full rows 0..19
    img.paste((120, 80, 40), (0, 20, 40, 100))  # solid left panel, columns 0..39
    img.paste((120, 80, 40), (90, 20, 100, 100))  # thin right panel (too narrow a band)
    img.save(tmp_path / "t.png")
    regions = photo_regions(tmp_path / "t.png")
    assert regions["top_row"] == pytest.approx(0.2)
    assert regions["side_band"] == pytest.approx([0.0, 0.4])
    Image.new("RGB", (50, 50), (120, 80, 40)).save(tmp_path / "solid.png")
    assert photo_regions(tmp_path / "solid.png")["top_row"] is None


# ---------------------------------------------------------------- classify panel_table


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Mesa de centro con patas de panel", "panel_table"),
        ("Mesa con paneles laterales de roble", "panel_table"),
        ("Consola con laterales macizos", "panel_table"),
        ("Mesa de centro con estructura en U", "panel_table"),
        ("Mesa auxiliar cuadrada de mármol", "panel_table"),
        ("Mesita auxiliar de travertino", "panel_table"),
        ("Mesa auxiliar de piedra natural", "panel_table"),
        ("Mesita auxiliar de nogal", "table"),  # auxiliar without stone stays a table
        ("Mesa de mármol", "table"),  # stone without auxiliar stays a table
    ],
)
def test_classify_text_panel_table(text: str, kind: str) -> None:
    assert classify_text(text) == kind


def test_classify_panel_from_name(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 35, 50, 35, "Cuadrada 35 x 35", name="Mesa auxiliar en mármol")
    assert classify(piece) == "panel_table"
    assert "panel_table" in KINDS


# ---------------------------------------------------------------- overrides


def test_load_overrides_missing_file(tmp_path: Path) -> None:
    assert load_overrides(tmp_path / "nope.json") == {}


def test_load_overrides_entries(tmp_path: Path) -> None:
    path = tmp_path / "o.json"
    path.write_text(
        '{"_comment": "x", "p03": "box", "p07": {"kind": "panel_table", "shelf_height_cm": 27}}',
        encoding="utf-8",
    )
    assert load_overrides(path) == {
        "p03": {"kind": "box"},
        "p07": {"kind": "panel_table", "shelf_height_cm": 27},
    }
    path.write_text('{"p03": "chair"}', encoding="utf-8")
    with pytest.raises(ValueError, match="desconocido"):
        load_overrides(path)


def test_resolve_kind_sources(piece: Piece, tmp_path: Path) -> None:
    path = tmp_path / "o.json"
    path.write_text('{"p01": {"kind": "panel_table", "panel_layout": "pairs"}}', encoding="utf-8")
    assert ParametricVariant(overrides_path=path).resolve_kind(piece) == (
        "panel_table",
        "override",
        {"panel_layout": "pairs"},
    )
    # constructor overrides win; file params of another kind are dropped
    variant = ParametricVariant(kind_overrides={"p01": "box"}, overrides_path=path)
    assert variant.resolve_kind(piece) == ("box", "override", {})
    no_file = ParametricVariant(overrides_path=tmp_path / "none.json")
    assert no_file.resolve_kind(piece) == ("table", "classify", {})
    with pytest.raises(ValueError, match="desconocido"):
        ParametricVariant(kind_overrides={"p01": "chair"})


def test_variant_records_override_in_meta(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, tmp_path: Path
) -> None:
    binary, calls = _setup_fake(monkeypatch, tmp_path)
    path = tmp_path / "o.json"
    path.write_text(
        '{"p01": {"kind": "panel_table", "panel_layout": "sides", "shelf_height_cm": 30}}',
        encoding="utf-8",
    )
    result = ParametricVariant(blender_bin=binary, overrides_path=path).run(piece, tmp_path / "E")
    meta = result.candidates[0].meta
    assert meta["kind"] == "panel_table" and meta["kind_source"] == "override"
    assert meta["params"] == {"panel_layout": "sides", "shelf_height_cm": 30}
    assert meta["n_boxes"] == 4 and "photo_regions" in meta
    spec = read_spec(Path(calls[0]["args"][calls[0]["args"].index("--spec") + 1]))
    assert spec.kind == "panel_table"
    assert {b.name for b in spec.boxes} == {"top", "panel_l", "panel_r", "shelf"}
    assert "override" in result.notes


# ---------------------------------------------------------------- box_legs


@pytest.mark.parametrize(
    "params",
    [
        None,
        {"leg_height_cm": 10, "leg_inset_cm": 7},
        {"plinth_height_cm": 5, "plinth_inset_cm": 2},
        {"leg_height_cm": 4, "plinth_height_cm": 5},
        {"leg_height_cm": 80, "plinth_height_cm": 80},  # clamped to half the height
    ],
)
@pytest.mark.parametrize("dims", [(110, 106, 35), (52, 50, 36), (200, 3, 90), (20, 20, 20)])
def test_box_legs_bbox_exact(tmp_path: Path, params, dims) -> None:
    w, h, d = dims
    boxes = build_spec(make_piece(tmp_path, w, h, d), "box_legs", params)
    mins, maxs = bounding_box(boxes)
    assert mins == pytest.approx((-w / 2, -d / 2, 0.0))
    assert maxs == pytest.approx((w / 2, d / 2, h))
    assert all(s > 0 for b in boxes for s in b.size_cm)


def test_box_legs_with_legs_p03(tmp_path: Path) -> None:
    boxes = {b.name: b for b in build_spec(make_piece(tmp_path, 110, 106, 35), "box_legs")}
    assert set(boxes) == {"body", "leg_fl", "leg_fr", "leg_bl", "leg_br"}
    assert boxes["body"] == Box("body", (110.0, 35.0, 96.0), (0.0, 0.0, 58.0))
    # defaults: 10 cm high, 5 cm square, 3 cm from the body edge to the outer face
    assert boxes["leg_fl"] == Box("leg_fl", (5.0, 5.0, 10.0), (-49.5, -12.0, 5.0))
    assert boxes["leg_br"].pos_cm == (49.5, 12.0, 5.0)


def test_box_legs_with_plinth_p08(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 52, 50, 36)
    boxes = {b.name: b for b in build_spec(piece, "box_legs", {"plinth_height_cm": 5})}
    assert set(boxes) == {"body", "plinth"}  # no legs without leg_height_cm
    assert boxes["body"] == Box("body", (52.0, 36.0, 45.0), (0.0, 0.0, 27.5))
    assert boxes["plinth"] == Box("plinth", (48.0, 32.0, 5.0), (0.0, 0.0, 2.5))


def test_box_legs_plinth_on_legs(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 52, 50, 36)
    boxes = {
        b.name: b
        for b in build_spec(piece, "box_legs", {"leg_height_cm": 4, "plinth_height_cm": 5})
    }
    assert boxes["plinth"].pos_cm[2] == pytest.approx(6.5)
    assert boxes["body"].pos_cm[2] - boxes["body"].size_cm[2] / 2 == pytest.approx(9.0)
    assert sum(n.startswith("leg") for n in boxes) == 4


@pytest.mark.parametrize("params", [{"panel_layout": "sides"}, {"leg_height_cm": -1}])
def test_box_legs_rejects_bad_params(piece: Piece, params) -> None:
    with pytest.raises(ValueError, match="box_legs"):
        build_spec(piece, "box_legs", params)


@pytest.mark.parametrize(
    ("description", "kind", "params"),
    [
        ("Zapatero de madera maciza con patas", "box_legs", {}),
        ("Mueble de mango sobre zócalo", "box_legs", {"plinth_height_cm": 5.0}),
        ("Mueble con zócalo y patas", "box_legs", {"plinth_height_cm": 5.0, "leg_height_cm": 10.0}),
        ("Mesa de roble con patas", "table", {}),  # a kind keyword wins
        ("Zapatero de madera maciza", "box", {}),  # no keyword: box as before
    ],
)
def test_classify_box_legs(tmp_path: Path, description: str, kind: str, params) -> None:
    piece = make_piece(tmp_path, 110, 106, 35, description)
    assert classify_with_params(piece) == (kind, params)
    assert classify(piece) == kind
    assert "box_legs" in KINDS


def test_resolve_kind_box_legs_from_text_and_file(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 52, 50, 36, "Mueble sobre zócalo")
    no_file = ParametricVariant(overrides_path=tmp_path / "none.json")
    assert no_file.resolve_kind(piece) == ("box_legs", "classify", {"plinth_height_cm": 5.0})
    path = tmp_path / "o.json"
    path.write_text('{"p99": {"kind": "box_legs", "leg_height_cm": 10}}', encoding="utf-8")
    assert ParametricVariant(overrides_path=path).resolve_kind(piece) == (
        "box_legs",
        "override",
        {"leg_height_cm": 10},
    )


def test_repo_overrides_p03_legs_p08_plinth() -> None:
    repo = Path(__file__).resolve().parent.parent / "data" / "parametric_overrides.json"
    overrides = load_overrides(repo)
    assert overrides["p03"]["kind"] == "box_legs"
    assert overrides["p03"]["leg_height_cm"] == 10
    assert "plinth_height_cm" not in overrides["p03"]
    assert overrides["p08"]["kind"] == "box_legs"
    assert overrides["p08"]["plinth_height_cm"] == 5


def test_box_legs_texture_hints(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 52, 50, 36)
    spec = make_spec(
        piece, "box_legs", params={"plinth_height_cm": 5, "side_edge": 0.05, "top_crop": 0.06}
    )
    boxes = {b.name: b for b in spec.boxes}
    assert spec.extra["side_band"] == [0.0, 0.05]
    assert boxes["body"].uv_v == pytest.approx((0.1, 0.94))  # rim rows skipped
    assert boxes["plinth"].uv_v is None
    defaults = make_spec(piece, "box_legs", params={"plinth_height_cm": 5})
    assert defaults.extra["side_band"] == [0.0, BOX_SIDE_EDGE]
    body = next(b for b in defaults.boxes if b.name == "body")
    assert body.uv_v == pytest.approx((0.1, 1.0 - BOX_TOP_CROP))
    assert bounding_box(defaults.boxes) == bounding_box(
        build_spec(piece, "box_legs", {"plinth_height_cm": 5})
    )
    for bad in ({"side_edge": 0}, {"top_crop": 0.5}):
        with pytest.raises(ValueError, match="box_legs"):
            build_spec(piece, "box_legs", bad)


def test_box_legs_top_samples_side_band(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 52, 50, 36)
    spec = make_spec(piece, "box_legs", params={"plinth_height_cm": 5, "side_edge": 0.05})
    raw = spec.to_dict()
    _, _, uvs = bpy_parametric.build_geometry(raw["boxes"], tuple(raw["extra"]["side_band"]))
    body_idx = next(i for i, b in enumerate(raw["boxes"]) if b["name"] == "body")
    faces = dict(
        zip(
            [n for n, _ in bpy_parametric.BOX_FACES],
            uvs[6 * body_idx : 6 * body_idx + 6],
            strict=True,
        )
    )
    for name in ("top", "left", "right"):
        assert all(0.0 <= u <= 0.05 + 1e-9 for u, _ in faces[name]), name
    assert max(v for _, v in faces["front"]) == pytest.approx(1.0 - BOX_TOP_CROP)


def test_base_words_do_not_override_proportions(tmp_path: Path) -> None:
    # p25: coat stand 35 x 176 x 40 "con patas finas" stays a shelf by proportions
    p25 = make_piece(tmp_path, 35, 176, 40, "Perchero de pie de aluminio con patas finas.")
    assert classify_with_params(p25) == ("shelf", {})
    slab = make_piece(tmp_path, 200, 3, 90, "Tablero sobre patas")
    assert classify(slab) == "slab"


# ---------------------------------------------------------------- pedestal

FIXTURE_PEDESTAL = Path(__file__).parent / "fixtures" / "platform" / "travertine_pedestal.png"
SEGMENTS = bpy_parametric.CYLINDER_SEGMENTS
TRIS_PER_CYLINDER = 2 * SEGMENTS + 2 * (SEGMENTS - 2)  # side quads + two fan-split n-gons

PEDESTAL_CASES = [
    None,
    {"top_shape": "oval"},
    {"base_shape": "taper", "foot_plate": True},
    {"base_diameter_ratio": 0.15, "top_thickness_cm": 1.5},
    {"base_diameter_ratio": 0.95, "foot_plate": True, "top_shape": "oval"},
]


def _geometry_bbox_cm(boxes: list[Box]):
    verts, _, _ = bpy_parametric.build_geometry([b.to_dict() for b in boxes])
    mins, maxs = bpy_parametric.bounds(verts)
    return tuple(v * 100 for v in mins), tuple(v * 100 for v in maxs)


@pytest.mark.parametrize("params", PEDESTAL_CASES)
@pytest.mark.parametrize(
    "dims", [(60, 45, 60), (90, 75, 60), (40, 55, 40), (120, 74, 80), (200, 3, 90), (20, 20, 20)]
)
def test_pedestal_bbox_exact(tmp_path: Path, params, dims) -> None:
    """Round (w == d) and oval (w != d) tops: spec bbox AND built mesh bbox == the dims."""
    w, h, d = dims
    boxes = build_spec(make_piece(tmp_path, w, h, d), "pedestal", params)
    expected = ((-w / 2, -d / 2, 0.0), (w / 2, d / 2, h))
    mins, maxs = bounding_box(boxes)
    assert (mins, maxs) == (pytest.approx(expected[0]), pytest.approx(expected[1]))
    gmins, gmaxs = _geometry_bbox_cm(boxes)
    assert gmins == pytest.approx(expected[0], abs=1e-9)
    assert gmaxs == pytest.approx(expected[1], abs=1e-9)
    assert all(b.shape == "cylinder" for b in boxes)
    assert all(s > 0 for b in boxes for s in b.size_cm)


def test_pedestal_defaults_travertine_60x45x60(tmp_path: Path) -> None:
    boxes = {b.name: b for b in build_spec(make_piece(tmp_path, 60, 45, 60), "pedestal")}
    assert set(boxes) == {"top", "base"}
    top, base = boxes["top"], boxes["base"]
    assert top.size_cm == pytest.approx((60.0, 60.0, 1.8))  # 4 % of the height
    assert top.pos_cm == pytest.approx((0.0, 0.0, 44.1))
    assert base.size_cm == pytest.approx((27.0, 27.0, 43.2))  # 0.45 x min(w, d)
    assert base.pos_cm == pytest.approx((0.0, 0.0, 21.6))  # floor → underside of the top
    assert base.taper == 1.0
    # very low piece: the default thickness never drops under 1.5 cm
    low = build_spec(make_piece(tmp_path, 50, 20, 50), "pedestal")
    assert low[0].size_cm[2] == pytest.approx(1.5)


def test_pedestal_oval_taper_foot(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 90, 75, 60)
    params = {"top_shape": "oval", "base_shape": "taper", "foot_plate": True, "top_thickness_cm": 3}
    boxes = {b.name: b for b in build_spec(piece, "pedestal", params)}
    assert boxes["top"].size_cm == pytest.approx((90.0, 60.0, 3.0))  # ellipse 90 x 60
    assert boxes["base"].size_cm[:2] == pytest.approx((27.0, 27.0))  # 0.45 x 60
    assert boxes["base"].taper == pytest.approx(0.9)
    foot = boxes["foot"]
    assert foot.size_cm == pytest.approx((29.7, 29.7, 2.0))  # 1.1 x the column, at the floor
    assert foot.pos_cm[2] == pytest.approx(1.0)
    base_z0 = boxes["base"].pos_cm[2] - boxes["base"].size_cm[2] / 2
    assert base_z0 == pytest.approx(2.0)  # the column stands on the plate
    # widest column: the plate is clamped to the narrow side of the top
    wide = build_spec(piece, "pedestal", {"base_diameter_ratio": 0.95, "foot_plate": True})
    assert next(b for b in wide if b.name == "foot").size_cm[0] == pytest.approx(60.0)
    # taper: the column is narrower at the floor, its top ring keeps the full diameter
    verts, _, _ = bpy_parametric.build_geometry([boxes["base"].to_dict()])
    bottom = [v for v in verts if v[2] == pytest.approx(base_z0 / 100)]
    top_ring = [v for v in verts if v[2] > base_z0 / 100 + 1e-6]
    assert max(v[0] for v in bottom) == pytest.approx(0.27 / 2 * 0.9)
    assert max(v[0] for v in top_ring) == pytest.approx(0.27 / 2)


@pytest.mark.parametrize(
    "params",
    [
        {"legs": 4},
        {"top_shape": "square"},
        {"base_shape": "cone"},
        {"foot_plate": "yes"},
        {"base_diameter_ratio": 0.1},
        {"base_diameter_ratio": 0.96},
        {"top_thickness_cm": 1.0},
        {"top_thickness_cm": float("nan")},
        {"top_thickness_cm": float("inf")},
        {"top_thickness_cm": "grueso"},
        {"top_thickness_cm": None},
        {"top_thickness_cm": True},
        {"base_diameter_ratio": float("nan")},
        {"base_diameter_ratio": "-inf"},
        {"base_diameter_ratio": [0.5]},
    ],
)
def test_pedestal_rejects_bad_params(piece: Piece, params) -> None:
    with pytest.raises(ValueError, match="^pedestal: "):
        build_spec(piece, "pedestal", params)


def test_pedestal_top_thickness_bounds(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 60, 45, 60)
    # explicit: up to half the height, never silently clamped
    boxes = build_spec(piece, "pedestal", {"top_thickness_cm": 22.5})
    assert boxes[0].size_cm[2] == pytest.approx(22.5)
    with pytest.raises(ValueError, match="^pedestal: top_thickness_cm .* mitad"):
        build_spec(piece, "pedestal", {"top_thickness_cm": 22.6})
    # very low pieces: the 1.5 cm default fallback only when it fits (h >= 3)
    assert build_spec(make_piece(tmp_path, 60, 3, 60), "pedestal")[0].size_cm[2] == 1.5
    with pytest.raises(ValueError, match="^pedestal: pieza demasiado baja"):
        build_spec(make_piece(tmp_path, 60, 2.9, 60), "pedestal")


def test_pedestal_round_with_unequal_dims_warns(tmp_path: Path) -> None:
    oval_dims = make_piece(tmp_path, 90, 75, 60)
    spec = make_spec(oval_dims, "pedestal")  # top_shape defaults to "round"
    assert len(spec.warnings) == 1 and "round" in spec.warnings[0]
    assert "90" in spec.warnings[0] and "60" in spec.warnings[0]
    assert next(b for b in spec.boxes if b.name == "top").size_cm[:2] == (90.0, 60.0)
    assert read_spec(write_spec(tmp_path / "s.json", spec)).warnings == spec.warnings
    assert make_spec(oval_dims, "pedestal", params={"top_shape": "oval"}).warnings == []
    assert make_spec(make_piece(tmp_path, 60, 45, 60), "pedestal").warnings == []
    assert make_spec(make_piece(tmp_path, 60, 45, 59.5), "pedestal").warnings == []  # ≤ 2 %
    assert "warnings" not in make_spec(oval_dims, "table").to_dict()  # other kinds: no key


@pytest.mark.parametrize("ratio", [0.15, 0.95])
def test_pedestal_base_ratio_bounds_accepted(tmp_path: Path, ratio: float) -> None:
    boxes = build_spec(make_piece(tmp_path, 60, 45, 40), "pedestal", {"base_diameter_ratio": ratio})
    assert boxes[1].size_cm[0] == pytest.approx(ratio * 40)


def test_pedestal_mesh_counts_and_seamless_wrap(tmp_path: Path) -> None:
    spec = make_spec(make_piece(tmp_path, 60, 45, 60), "pedestal")
    verts, faces, uvs, smooth = bpy_parametric.build_mesh([b.to_dict() for b in spec.boxes])
    # per cylinder: SEGMENTS smooth side quads + 2 flat n-gon caps
    assert len(faces) == 2 * (SEGMENTS + 2)
    assert sum(smooth) == 2 * SEGMENTS
    assert sum(len(f) - 2 for f in faces) == 2 * TRIS_PER_CYLINDER
    assert all(0.0 <= c <= 1.0 for face in uvs for uv in face for c in uv)
    # a side vertex has ONE uv in every quad that uses it: no seam to split around
    seen: dict[int, tuple[float, float]] = {}
    for face, face_uv, is_side in zip(faces, uvs, smooth, strict=True):
        if not is_side:
            continue
        for i, uv in zip(face, face_uv, strict=True):
            assert seen.setdefault(i, uv) == pytest.approx(uv)
        # continuity: u changes by at most one segment's step along every ring edge
        # (bottom edge 0→1 and top edge 3→2), INCLUDING the two mirror lines
        for a, b in ((0, 1), (3, 2)):
            assert abs(face_uv[a][0] - face_uv[b][0]) <= 2 / SEGMENTS + 1e-9
    assert bpy_parametric.wrap_u(0.0, 0.2, 0.6) == pytest.approx(
        bpy_parametric.wrap_u(2 * math.pi, 0.2, 0.6)
    )
    # the mirror lines (where u turns) sit at θ = π/4 and 5π/4 on every cylinder side
    for box, start in zip(spec.boxes, (0, SEGMENTS + 2), strict=True):
        side = list(
            zip(faces[start : start + SEGMENTS], uvs[start : start + SEGMENTS], strict=True)
        )
        ring_u = [face_uv[0][0] for _, face_uv in side]  # u of the bottom vertex i
        cx, cy = box.pos_cm[0] / 100, box.pos_cm[1] / 100
        turns = []
        for i in range(SEGMENTS):
            prev_u, next_u = ring_u[i - 1], ring_u[(i + 1) % SEGMENTS]
            if (ring_u[i] - prev_u) * (next_u - ring_u[i]) < 0:  # slope changes sign
                x, y, _ = verts[side[i][0][0]]
                turns.append(math.atan2(y - cy, x - cx) % (2 * math.pi))
        assert sorted(turns) == pytest.approx([math.pi / 4, 5 * math.pi / 4])
    # the three-quarter view's visible half shows the strip left → right, unmirrored
    phase = bpy_parametric.WRAP_PHASE
    assert phase == pytest.approx(math.pi / 4)
    assert bpy_parametric.wrap_u(phase + math.pi, 0.2, 0.6) == pytest.approx(0.2)
    assert bpy_parametric.wrap_u(phase + 1.5 * math.pi, 0.2, 0.6) == pytest.approx(0.4)


def test_pedestal_photo_hints(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 60, 45, 60)
    regions = {"top_row": 0.1625, "side_band": [0.2627, 0.7282]}  # the travertine photo
    spec = make_spec(piece, "pedestal", params={"foot_plate": True}, photo_regions=regions)
    boxes = {b.name: b for b in spec.boxes}
    split = 1 - 0.1625
    top = boxes["top"]
    assert top.cap_uv[0] == (0.0, 1.0)  # the photographed top surface, whole width ...
    assert top.cap_uv[1] == pytest.approx((split, 1.0))  # ... and rows above the split
    assert top.uv_v == pytest.approx((split - 0.06, split))  # rim: the rows just below it
    assert top.uv_u == PEDESTAL_RIM_STRIP
    centre, half = (0.2627 + 0.7282) / 2, (0.7282 - 0.2627) / 2 * PEDESTAL_COLUMN_STRIP
    for name in ("base", "foot"):
        assert boxes[name].uv_u == pytest.approx((centre - half, centre + half))
    assert boxes["foot"].uv_v[0] == pytest.approx(0.04)  # floor shadow rows skipped
    assert boxes["base"].uv_v[1] == pytest.approx(split - 0.06)  # column ends under the rim
    assert boxes["base"].uv_v[0] == pytest.approx(boxes["foot"].uv_v[1])
    # no regions: default top rows, column band from its straight front projection
    plain = {b.name: b for b in make_spec(piece, "pedestal").boxes}
    assert plain["top"].cap_uv[1] == pytest.approx((1 - PEDESTAL_TOP_ROW, 1.0))
    half = 0.45 * 60 / 120 * PEDESTAL_COLUMN_STRIP
    assert plain["base"].uv_u == pytest.approx((0.5 - half, 0.5 + half))
    # hints never change the geometry
    assert bounding_box(spec.boxes) == bounding_box(
        build_spec(piece, "pedestal", {"foot_plate": True})
    )


def test_pedestal_spec_json_round_trip(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 90, 75, 60)
    spec = make_spec(piece, "pedestal", params={"top_shape": "oval", "base_shape": "taper"})
    assert read_spec(write_spec(tmp_path / "spec.json", spec)) == spec
    raw = spec.to_dict()["boxes"][1]
    assert raw["shape"] == "cylinder" and raw["taper"] == pytest.approx(0.9)
    with pytest.raises(ValueError, match="shape"):
        Box.from_dict({**raw, "shape": "sphere"})
    # plain boxes keep their old JSON (no new keys)
    assert set(Box("b", (1, 1, 1), (0, 0, 0.5)).to_dict()) == {"name", "size_cm", "pos_cm"}


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Mesa auxiliar de travertino con pie central", ("pedestal", {})),
        ("Velador ovalado de mármol", ("pedestal", {"top_shape": "oval"})),
        ("Mesa de centro sobre base cilíndrica", ("pedestal", {})),
        ("Mesa auxiliar de travertino", ("panel_table", {})),  # unchanged without a cue
        ("Mesa de comedor redonda con patas", ("table", {})),
        ("Round coffee table on a pedestal base", ("pedestal", {})),
        # only tables become pedestals: other kinds keep their kind
        ("Estantería con base central", ("shelf", {})),
        ("Aparador con pie central", ("sideboard", {})),
        ("Tablero de mármol con pie central", ("slab", {})),  # "table" ≠ "tablero"
        ("Pedestal de mármol para escultura", ("box", {})),  # no table word
    ],
)
def test_classify_pedestal(tmp_path: Path, description: str, expected) -> None:
    assert classify_with_params(make_piece(tmp_path, 60, 45, 60, description)) == expected
    assert "pedestal" in KINDS


def test_classify_pedestal_cue_in_description_table_in_name(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, 60, 45, 60, "Travertino con pie central", name="Mesa Luna")
    assert classify_with_params(piece) == ("pedestal", {})
    shelf = make_piece(tmp_path, 60, 45, 60, "Estantería con pie central", name="Mesa Luna")
    assert classify(shelf) == "shelf"  # the description's kind wins as before


def test_pedestal_real_blender_travertine(tmp_path: Path) -> None:
    """Opt-in: the travertine side table (60 x 45 x 60 cm) through variant E with the real
    photo cleaning, Blender build and control renders."""
    value = os.environ.get("HARNESS_BLENDER_TEST_BIN", "").strip()
    if not value or not Path(value).is_file():
        pytest.skip("Blender real no solicitado (HARNESS_BLENDER_TEST_BIN)")
    import trimesh

    from harness.eval.render import render_views

    piece = make_piece(tmp_path, 60, 45, 60, "Mesa auxiliar de travertino con pie central")
    piece = piece.model_copy(update={"images": [FIXTURE_PEDESTAL]})
    variant = ParametricVariant(blender_bin=Path(value), overrides_path=None)
    result = variant.run(piece, tmp_path / "E")
    cand = result.candidates[0]
    assert cand.meta["kind"] == "pedestal" and cand.meta["n_boxes"] == 2
    mesh = trimesh.load(cand.glb_path, force="mesh", process=False)
    # glTF is +Y up: (width, height, depth) = (X, Y, Z)
    assert tuple(mesh.extents) == pytest.approx((0.60, 0.45, 0.60), abs=1e-4)
    assert len(mesh.faces) == 2 * TRIS_PER_CYLINDER
    assert mesh.visual.uv is not None
    paths = render_views(cand.glb_path, tmp_path / "renders", size=256, blender_bin=Path(value))
    with Image.open(paths[3]) as img:  # three_quarter: the piece is there, not a blank frame
        assert img.convert("L").getextrema()[0] < 200
