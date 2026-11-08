"""Parametric spec and variant E tests.

The real-Blender test is opt-in: set ``HARNESS_BLENDER_TEST_BIN=/path/to/blender`` (the
autouse fixture in conftest removes ``BLENDER_BIN``); it skips when unset.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from PIL import Image

from harness.core.blender import BlenderNotAvailable, BlenderRun
from harness.core.models import Piece
from harness.post import bpy_parametric
from harness.post.parametric_spec import (
    Box,
    Spec,
    bounding_box,
    build_spec,
    classify,
    classify_text,
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


@pytest.mark.parametrize("kind", ["table", "shelf", "sideboard", "slab", "box"])
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
    assert len(verts) == 5 * 8 and len(faces) == 5 * 6
    mins, maxs = bpy_parametric.bounds(verts)
    assert mins == pytest.approx((-0.6, -0.3, 0.0))
    assert maxs == pytest.approx((0.6, 0.3, 0.75))
    assert all(0.0 <= c <= 1.0 for face in uvs for uv in face for c in uv)
    # Top box front face (index 2) spans the full width and the top 4 cm of the photo.
    front = uvs[2]
    assert sorted(u for u, _ in front) == pytest.approx([0.0, 0.0, 1.0, 1.0])
    assert sorted(v for _, v in front) == pytest.approx([71 / 75, 71 / 75, 1.0, 1.0])


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
    import trimesh

    extents = trimesh.load(out, force="mesh").extents
    assert sorted(extents) == pytest.approx(sorted([1.2, 0.75, 0.6]), rel=1e-3)
