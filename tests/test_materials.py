"""Tests for the real PBR material library (``materials`` + ``bpy_materials`` + fetch script).

Real-Blender tests are opt-in: set ``HARNESS_BLENDER_TEST_BIN=/path/to/blender``; they also
need the fetched maps (``uv run python scripts/fetch_materials.py``) and skip without them.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from harness.core.blender import BlenderRun
from harness.post import bpy_materials, materials
from harness.post.bpy_materials import (
    box_uv,
    repeats_per_unit,
    split_vertex_fraction,
    triangle_uv_stats,
    uv_usable,
)
from harness.post.materials import (
    Material,
    MaterialError,
    apply_material,
    build_args,
    detect_material,
    load_manifest,
    masked_mean_color,
    normalise_text,
    remap_mean,
    tone_match,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE_PEDESTAL = Path(__file__).parent / "fixtures" / "platform" / "travertine_pedestal.png"
RENDER_OUT = REPO / "outputs" / "renders" / "M_travertine_pedestal_three_quarter.png"


def _load_fetch_script():
    spec = importlib.util.spec_from_file_location(
        "fetch_materials", REPO / "scripts" / "fetch_materials.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- manifest


def test_manifest_has_the_eight_cc0_materials() -> None:
    manifest = load_manifest()
    assert set(manifest) == {
        "travertine", "white_marble", "oak", "walnut", "white_plaster", "boucle", "linen",
        "leather",
    }  # fmt: skip
    assert manifest["travertine"].asset == "Travertine009"
    for material in manifest.values():
        assert material.license == "CC0"
        assert material.url == f"https://ambientcg.com/get?file={material.asset}_1K-JPG.zip"
        assert material.tile_cm > 0 and 0 <= material.roughness <= 1
        assert material.label_en and material.label_es
    # every detectable id exists in the manifest
    assert {mid for mid, _ in materials.MATERIAL_STEMS} == set(manifest)


def test_travertine_is_matte_without_normal_relief() -> None:
    trav = load_manifest()["travertine"]
    assert trav.matte and trav.roughness == 1.0 and trav.metallic == 0.0
    assert trav.normal_strength == 0.0 and trav.vertical_grain


# --------------------------------------------------------------------------- detection


@pytest.mark.parametrize(
    ("name", "notes", "expected"),
    [
        ("Mesa auxiliar de travertino", "", "travertine"),
        ("Side table", "Honed TRAVERTINE top", "travertine"),
        ("Mesa de mármol travertino", "", "travertine"),  # travertine wins over marble
        ("Mesa de MÁRMOL blanco", "", "white_marble"),
        ("Marble coffee table", "", "white_marble"),
        ("Aparador de roble macizo", "", "oak"),
        ("Oak sideboard", "", "oak"),
        ("Cómoda de nogal", "", "walnut"),
        ("Walnut desk", "", "walnut"),
        ("Aparador lacado en blanco", "", "white_plaster"),
        ("Lacquered cabinet", "", "white_plaster"),
        ("Lámpara de yeso", "", "white_plaster"),
        ("Butaca bouclé", "", "boucle"),
        ("Butaca BOUCLE", "", "boucle"),
        ("Puff de lana", "", "boucle"),
        ("Wool armchair", "", "boucle"),
        ("Sofá de lino con patas de roble", "", "linen"),  # first material in the name
        ("Linen sofa", "", "linen"),
        ("Sillón de piel", "", "leather"),
        ("Taburete de cuero", "", "leather"),
        ("Leather lounge chair", "", "leather"),
        ("Mesa Luna", "acabado en nogal", "walnut"),  # from the notes
        ("Mesa Luna", "", None),
        ("Linóleo gris", "", None),  # "lino" is a whole word, not a prefix
        ("Robledal", "", None),
        ("Pielago", "", None),
    ],
)
def test_detect_material(name: str, notes: str, expected: str | None) -> None:
    assert detect_material(name, notes) == expected


def test_detect_material_name_beats_notes() -> None:
    assert detect_material("Sillón de piel", "patas de roble") == "leather"
    assert detect_material("", "") is None


def test_normalise_text_strips_accents() -> None:
    assert normalise_text("Bouclé MÁRMOL Nögal") == "boucle marmol nogal"


# --------------------------------------------------------------------------- colour


def _synthetic_scan(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.array([223.0, 203.0, 172.0])  # Travertine009's own mean
    grad = np.linspace(-40, 40, 256)[None, :, None]
    noise = rng.normal(0, 18, (256, 256, 3))
    return np.clip(base + grad + noise, 0, 255).astype(np.uint8)


@pytest.mark.parametrize(
    "target", [(199, 182, 163), (185, 166, 144), (240, 236, 228), (60, 42, 30), (128, 128, 128)]
)
def test_tone_match_hits_target_mean(target: tuple[int, int, int]) -> None:
    out = tone_match(_synthetic_scan(), target)
    assert out.dtype == np.uint8 and out.shape == (256, 256, 3)
    mean = out.reshape(-1, 3).mean(axis=0)
    assert np.all(np.abs(mean - np.array(target)) <= 3), mean


def test_tone_match_keeps_texture_contrast() -> None:
    scan = _synthetic_scan()
    out = tone_match(scan, (199, 182, 163))
    lum_in = scan.astype(float) @ materials.REC709
    lum_out = out.astype(float) @ materials.REC709
    assert lum_out.std() > 0.6 * lum_in.std()  # grain kept, not flattened to a solid colour


def test_tone_match_desaturates_mildly() -> None:
    pixel = np.array([[[200, 100, 50]]], dtype=np.uint8)
    out = tone_match(pixel, (200, 100, 50), iterations=0).astype(float)
    lum = float(np.array([200, 100, 50]) @ materials.REC709)
    expected = lum + 0.95 * (np.array([200, 100, 50]) - lum)
    assert np.allclose(out[0, 0], np.round(expected), atol=0.5)


def test_masked_mean_color_trims_shadow_and_highlight() -> None:
    img = np.full((100, 100, 3), 255, dtype=np.uint8)  # white background
    img[10:90, 10:90] = (200, 180, 160)  # object
    img[80:90, 10:90] = (20, 20, 20)  # cast shadow inside the mask (12,5 % of it)
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:90, 10:90] = True
    assert masked_mean_color(img, mask) == (200, 180, 160)
    with pytest.raises(ValueError, match="vacía"):
        masked_mean_color(img, np.zeros_like(mask))


def test_photo_mean_color_uses_clean_mask(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from harness.prep import clean

    img = np.full((60, 60, 3), 250, dtype=np.uint8)
    img[20:40, 20:40] = (120, 90, 60)
    photo = tmp_path / "p.png"
    Image.fromarray(img).save(photo)

    def fake_remove(image: Image.Image) -> Image.Image:
        rgba = image.convert("RGBA")
        alpha = np.zeros((60, 60), dtype=np.uint8)
        alpha[20:40, 20:40] = 255
        rgba.putalpha(Image.fromarray(alpha))
        return rgba

    monkeypatch.setattr(clean, "_remove_background", fake_remove)
    assert materials.photo_mean_color(photo) == (120, 90, 60)


def test_remap_mean() -> None:
    rng = np.random.default_rng(1)
    rough = rng.integers(60, 200, (64, 64)).astype(np.uint8)
    out = remap_mean(rough, 0.3)
    assert abs(out.mean() - 0.3 * 255) < 2
    assert remap_mean(np.zeros((4, 4), dtype=np.uint8), 0.5).mean() == pytest.approx(128, abs=1)


# --------------------------------------------------------------------------- tiling / UVs


def test_repeats_per_unit_real_size() -> None:
    # 1 unit wide model that is really 120 cm, 60 cm tile → 2 repeats per unit
    assert repeats_per_unit((1.0, 0.5, 0.3), (120, 50, 30), 60) == pytest.approx(2.0)
    # already in metres: 60 x 45 x 60 cm pedestal, 40 cm tile → 2,5 repeats per metre
    assert repeats_per_unit((0.6, 0.6, 0.45), (60, 45, 60), 40) == pytest.approx(2.5)
    # orientation-independent: largest side matched with largest dimension
    assert repeats_per_unit((0.3, 0.5, 1.0), (120, 50, 30), 60) == pytest.approx(2.0)
    # no real size: units are metres
    assert repeats_per_unit((2.0, 1.0, 1.0), None, 50) == pytest.approx(2.0)


def test_repeats_per_unit_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        repeats_per_unit((1, 1, 1), None, 0)
    with pytest.raises(ValueError):
        repeats_per_unit((0, 0, 0), (10, 10, 10), 10)


def test_box_uv_axes_and_scale() -> None:
    pts = np.array([[0.2, 0.4, 0.6]] * 6)
    normals = np.array([[0, 0, 1], [0, 0, -1], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0]])
    uv = box_uv(pts, normals, 2.0)
    assert uv[0] == pytest.approx([0.4, 0.8])  # top: (x, y)
    assert uv[1] == pytest.approx([0.4, -0.8])  # bottom: y flipped (not mirrored)
    assert uv[2] == pytest.approx([0.8, 1.2])  # +X: (y, z)
    assert uv[3] == pytest.approx([-0.8, 1.2])  # -X: y flipped
    assert uv[4] == pytest.approx([-0.4, 1.2])  # +Y (back): x flipped
    assert uv[5] == pytest.approx([0.4, 1.2])  # -Y (front): (x, z)


def test_box_uv_vertical_grain_swaps_only_side_faces() -> None:
    pts = np.array([[0.2, 0.4, 0.6]] * 3)
    normals = np.array([[0, 0, 1], [1, 0, 0], [0, -1, 0]])
    uv = box_uv(pts, normals, 1.0, vertical_grain=True)
    assert uv[0] == pytest.approx([0.2, 0.4])  # top unchanged
    assert uv[1] == pytest.approx([0.6, 0.4])  # (y, z) → (z, y)
    assert uv[2] == pytest.approx([0.6, 0.2])  # (x, z) → (z, x)


def test_box_uv_physical_repeat() -> None:
    """A 1,2 m wide front face with a 60 cm tile spans exactly 2 repeats."""
    pts = np.array([[-0.6, 0, 0], [0.6, 0, 0]])
    normals = np.array([[0, -1, 0], [0, -1, 0]])
    uv = box_uv(pts, normals, repeats_per_unit((1.2, 0.6, 0.75), (120, 75, 60), 60))
    assert uv[1, 0] - uv[0, 0] == pytest.approx(2.0)


def _grid(nx: int = 4, ny: int = 4):
    """Triangles of a unit square grid in the XY plane."""
    tris = []
    for i in range(nx):
        for j in range(ny):
            a = (i / nx, j / ny, 0.0)
            b = ((i + 1) / nx, j / ny, 0.0)
            c = ((i + 1) / nx, (j + 1) / ny, 0.0)
            d = (i / nx, (j + 1) / ny, 0.0)
            tris += [(a, b, c), (a, c, d)]
    return np.array(tris)


def test_triangle_uv_stats_planar_unwrap_is_usable() -> None:
    xyz = _grid()
    stats = triangle_uv_stats(xyz, xyz[:, :, :2] * 3.0)
    assert stats["density"] == pytest.approx(3.0)
    assert stats["density_cv"] == pytest.approx(0.0, abs=1e-9)
    assert stats["anisotropy"] == pytest.approx(1.0)
    assert uv_usable(stats, 0.0)


def test_triangle_uv_stats_detects_stretch_and_atlas() -> None:
    xyz = _grid()
    stretched = xyz[:, :, :2] * np.array([2.0, 1.0])
    stats = triangle_uv_stats(xyz, stretched)
    assert stats["anisotropy"] == pytest.approx(2.0)
    assert not uv_usable(stats, 0.0)
    # uneven density: half the triangles at 4× scale
    uneven = xyz[:, :, :2].copy()
    uneven[: len(uneven) // 2] *= 4.0
    assert triangle_uv_stats(xyz, uneven)["density_cv"] > 0.5
    # good stats but many chart borders → not usable
    assert not uv_usable(triangle_uv_stats(xyz, xyz[:, :, :2]), 0.4)


def test_triangle_uv_stats_degenerate() -> None:
    xyz = np.zeros((2, 3, 3))
    stats = triangle_uv_stats(xyz, np.zeros((2, 3, 2)))
    assert stats["triangles"] == 0 and not uv_usable(stats, 0.0)


def test_split_vertex_fraction() -> None:
    loop_vertex = np.array([0, 1, 2, 0, 2, 3])
    same = np.array([[0, 0], [1, 0], [1, 1], [0, 0], [1, 1], [0, 1]], dtype=float)
    assert split_vertex_fraction(loop_vertex, same) == 0.0
    seam = same.copy()
    seam[3] = [0.5, 0.5]  # vertex 0 gets two UVs
    assert split_vertex_fraction(loop_vertex, seam) == pytest.approx(0.25)


# --------------------------------------------------------------------------- arguments


def _material(**overrides) -> Material:
    base = load_manifest()["travertine"]
    return Material(**{**base.__dict__, **overrides})


def test_build_args_matte_round_trip(tmp_path: Path) -> None:
    mat = _material()
    args = build_args(
        tmp_path / "in.glb", tmp_path / "out.glb", tmp_path / "m.json", mat,
        color=tmp_path / "c.jpg", normal=tmp_path / "n.jpg", roughness_map=tmp_path / "r.jpg",
        matte=True, real_size_cm=(60, 45, 60),
    )  # fmt: skip
    ns = bpy_materials.parse_args(bpy_materials.script_argv(["blender", "--", *args]))
    assert ns.material_id == "travertine" and ns.color == str(tmp_path / "c.jpg")
    assert (ns.roughness, ns.metallic) == (1.0, 0.0)
    assert ns.roughness_map is None  # matte drops the map
    assert ns.normal is None and ns.normal_strength == 0.0  # travertine: no relief
    assert ns.tile_cm == 40 and ns.real_size == [60, 45, 60]
    assert ns.vertical_grain and ns.uv_mode == "auto"


def test_build_args_polished_keeps_roughness_map(tmp_path: Path) -> None:
    marble = load_manifest()["white_marble"]
    args = build_args(
        tmp_path / "in.glb", tmp_path / "out.glb", tmp_path / "m.json", marble,
        color=tmp_path / "c.jpg", normal=None, roughness_map=tmp_path / "r.jpg",
        matte=False, real_size_cm=None, uv_mode="box",
    )  # fmt: skip
    ns = bpy_materials.parse_args(args)
    assert ns.roughness_map == str(tmp_path / "r.jpg") and ns.roughness == pytest.approx(0.3)
    assert ns.real_size is None and ns.uv_mode == "box" and not ns.vertical_grain
    leather = load_manifest()["leather"]
    args = build_args(
        tmp_path / "a", tmp_path / "b", tmp_path / "m", leather, color=tmp_path / "c",
        normal=tmp_path / "n.jpg", roughness_map=None, matte=False, real_size_cm=None,
    )  # fmt: skip
    ns = bpy_materials.parse_args(args)
    assert ns.normal == str(tmp_path / "n.jpg") and ns.normal_strength == pytest.approx(0.6)


@pytest.mark.parametrize(
    "bad",
    [["--tile-cm", "0"], ["--roughness", "2"], ["--real-size", "1", "0", "1"],
     ["--normal-strength", "-1"], ["--uv-mode", "planar"]],
)  # fmt: skip
def test_bpy_parse_args_rejects_bad_values(bad: list[str]) -> None:
    base = ["--in", "a", "--out", "b", "--meta", "m", "--material-id", "x", "--color", "c",
            "--tile-cm", "40"]  # fmt: skip
    with pytest.raises(SystemExit):
        bpy_materials.parse_args(base + bad)


# --------------------------------------------------------------------------- apply (mocked)


@pytest.fixture
def maps_dir(tmp_path: Path) -> Path:
    root = tmp_path / "materials"
    rng = np.random.default_rng(2)
    for mid in load_manifest():
        folder = root / mid
        folder.mkdir(parents=True)
        Image.fromarray(_synthetic_scan()).save(folder / "Color.jpg", quality=95)
        Image.fromarray(rng.integers(0, 255, (64, 64, 3)).astype(np.uint8)).save(
            folder / "NormalGL.jpg"
        )
        Image.fromarray(rng.integers(80, 220, (64, 64)).astype(np.uint8)).save(
            folder / "Roughness.jpg"
        )
    return root


def _fake_materials_blender(seen: dict):
    def fake(script: Path, args: list[str], timeout: int = 600, blender_bin=None) -> BlenderRun:
        assert script == materials.BPY_MATERIALS_SCRIPT
        ns = bpy_materials.parse_args(args)
        seen["ns"] = ns
        with Image.open(ns.color) as img:
            seen["color_mean"] = np.asarray(img.convert("RGB")).reshape(-1, 3).mean(axis=0)
        if ns.roughness_map:
            with Image.open(ns.roughness_map) as img:
                seen["rough_mean"] = np.asarray(img.convert("L")).mean()
        Path(ns.glb_out).write_bytes(b"glTF")
        Path(ns.meta).write_text(
            json.dumps({"glb_bytes": 4, "uv": [{"used": "box"}], "repeats_per_unit": 2.5}),
            encoding="utf-8",
        )
        return BlenderRun(["blender", *args], 0, "ok", "", 0.2)

    return fake


def test_apply_material_tone_matches_and_cleans_up(
    tmp_path: Path, maps_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}
    monkeypatch.setattr(materials, "run_blender_script", _fake_materials_blender(seen))
    glb_in = tmp_path / "in.glb"
    glb_in.write_bytes(b"glTF")
    out = tmp_path / "out" / "model_post.glb"
    meta = apply_material(
        glb_in, out, material_id="travertine", target_rgb=(199, 182, 163),
        real_size_cm=(60, 45, 60), materials_dir=maps_dir,
    )  # fmt: skip
    # the JPEG handed to Blender carries the photo's mean (JPEG rounding included)
    assert np.all(np.abs(seen["color_mean"] - np.array([199, 182, 163])) <= 3)
    assert meta["color_mean"] == pytest.approx([199, 182, 163], abs=1)
    assert meta["target_rgb"] == [199, 182, 163]
    assert meta["material"]["asset"] == "Travertine009" and meta["matte"] is True
    assert meta["uv"][0]["used"] == "box"
    assert not (out.parent / materials.TMP_DIRNAME).exists()
    saved = json.loads(out.with_name("model_post_materials.json").read_text(encoding="utf-8"))
    assert saved["material"]["id"] == "travertine"


def test_apply_material_polished_remaps_roughness(
    tmp_path: Path, maps_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}
    monkeypatch.setattr(materials, "run_blender_script", _fake_materials_blender(seen))
    glb_in = tmp_path / "in.glb"
    glb_in.write_bytes(b"glTF")
    meta = apply_material(
        glb_in, tmp_path / "out.glb", material_id="white_marble", materials_dir=maps_dir
    )
    assert abs(seen["rough_mean"] - 0.3 * 255) < 4
    assert meta["matte"] is False and meta["target_rgb"] is None
    # without a target the scan keeps its own colour (the original Color.jpg is passed)
    assert seen["ns"].color == str(maps_dir / "white_marble" / "Color.jpg")
    # matte=False lifts the matte look of a matte material: its Roughness map is kept
    meta = apply_material(
        glb_in, tmp_path / "out2.glb", material_id="oak", matte=False, materials_dir=maps_dir
    )
    assert meta["matte"] is False and seen["ns"].roughness_map is not None
    assert seen["rough_mean"] > 240  # oak's manifest roughness is 1 (clamped at white)


def test_apply_material_errors(tmp_path: Path, maps_dir: Path, monkeypatch) -> None:
    glb_in = tmp_path / "in.glb"
    glb_in.write_bytes(b"glTF")
    with pytest.raises(MaterialError, match="desconocido"):
        apply_material(glb_in, tmp_path / "o.glb", material_id="granite", materials_dir=maps_dir)
    with pytest.raises(MaterialError, match="fetch_materials"):
        apply_material(
            glb_in, tmp_path / "o.glb", material_id="oak", materials_dir=tmp_path / "empty"
        )
    with pytest.raises(FileNotFoundError):
        apply_material(tmp_path / "nope.glb", tmp_path / "o.glb", material_id="oak")

    def failing(script: Path, args: list[str], timeout: int = 600, blender_bin=None):
        return BlenderRun(["blender"], 1, "", "Traceback: kaput", 0.1)

    monkeypatch.setattr(materials, "run_blender_script", failing)
    with pytest.raises(MaterialError, match="kaput"):
        apply_material(glb_in, tmp_path / "o.glb", material_id="oak", materials_dir=maps_dir)
    assert not (tmp_path / materials.TMP_DIRNAME).exists()


# --------------------------------------------------------------------------- fetch script


def _zip_for(asset: str, maps=("Color", "NormalGL", "Roughness")) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in maps:
            jpg = io.BytesIO()
            Image.new("RGB", (8, 8), (200, 180, 160)).save(jpg, format="JPEG")
            zf.writestr(f"{asset}_1K-JPG_{name}.jpg", jpg.getvalue())
        zf.writestr(f"{asset}_1K-JPG.blend", b"not extracted")
        zf.writestr("../evil.jpg", b"never written")
    return buf.getvalue()


def test_fetch_extracts_verifies_and_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    fetch = _load_fetch_script()
    trav = load_manifest()["travertine"]
    calls: list[str] = []

    def fake_download(url: str) -> bytes:
        calls.append(url)
        return _zip_for(trav.asset)

    monkeypatch.setattr(fetch, "download", fake_download)
    assert fetch.fetch(trav, tmp_path) == "descargado"
    folder = tmp_path / "travertine"
    assert sorted(p.name for p in folder.iterdir()) == [
        "Color.jpg", "NormalGL.jpg", "Roughness.jpg", "source.json",
    ]  # fmt: skip
    source = json.loads((folder / "source.json").read_text(encoding="utf-8"))
    assert source["license"] == "CC0" and len(source["maps"]["Color"]["sha256"]) == 64
    assert not (tmp_path / "evil.jpg").exists()
    assert fetch.fetch(trav, tmp_path) == "ya estaba" and len(calls) == 1
    (folder / "NormalGL.jpg").write_bytes(b"broken")  # corrupt map → downloaded again
    assert fetch.fetch(trav, tmp_path) == "descargado" and len(calls) == 2
    assert fetch.fetch(trav, tmp_path, force=True) == "descargado" and len(calls) == 3


def test_fetch_rejects_incomplete_zip(tmp_path: Path, monkeypatch) -> None:
    fetch = _load_fetch_script()
    oak = load_manifest()["oak"]
    monkeypatch.setattr(fetch, "download", lambda url: _zip_for(oak.asset, ("Color",)))
    with pytest.raises(ValueError, match="NormalGL"):
        fetch.fetch(oak, tmp_path)
    assert fetch.main(["--dest", str(tmp_path), "--only", "oak"]) == 1


# --------------------------------------------------------------------------- real Blender


def _blender_bin() -> Path:
    value = os.environ.get("HARNESS_BLENDER_TEST_BIN", "").strip()
    if not value or not Path(value).is_file():
        pytest.skip("Blender real no solicitado (HARNESS_BLENDER_TEST_BIN)")
    if not load_manifest()["travertine"].map_path("Color").is_file():
        pytest.skip("Mapas sin descargar: uv run python scripts/fetch_materials.py")
    return Path(value)


def _build_pedestal(tmp_path: Path, binary: Path) -> Path:
    from harness.core.blender import run_blender_script
    from harness.core.models import Piece
    from harness.post import parametric_spec

    piece = Piece(
        id="p99", name="Mesa auxiliar", store="Tienda", source_url="https://example.com",
        category="macizo_mate", images=[FIXTURE_PEDESTAL], width_cm=60, height_cm=45,
        depth_cm=60, description="Mesa auxiliar de travertino con pie central",
    )  # fmt: skip
    spec = parametric_spec.make_spec(piece, "pedestal", texture=FIXTURE_PEDESTAL)
    spec_path = parametric_spec.write_spec(tmp_path / "spec.json", spec)
    glb = tmp_path / "pedestal.glb"
    run = run_blender_script(
        Path(parametric_spec.__file__).with_name("bpy_parametric.py"),
        ["--spec", str(spec_path), "--out", str(glb)],
        blender_bin=binary,
    )
    assert run.ok and glb.is_file(), run.stderr[-2000:]
    return glb


def test_apply_travertine_pedestal_real_blender(tmp_path: Path) -> None:
    """Opt-in: the travertine pedestal (60 × 45 × 60 cm) re-skinned with Travertine009,
    tone-matched to the fixture photo; three-quarter render saved for a visual check
    against ``tests/fixtures/platform/travertine_pedestal.png``."""
    import trimesh

    from harness.eval.render import render_views

    binary = _blender_bin()
    glb = _build_pedestal(tmp_path, binary)
    target = materials.photo_mean_color(FIXTURE_PEDESTAL)
    assert 170 < target[0] < 230 and target[0] > target[1] > target[2]  # warm cream
    out = tmp_path / "cand_1" / "model_post.glb"
    meta = apply_material(
        glb, out, material_id="travertine", target_rgb=target, real_size_cm=(60, 45, 60),
        blender_bin=binary,
    )  # fmt: skip
    assert meta["tris"] == 504 and meta["meshes"] == 1
    assert meta["repeats_per_unit"] == pytest.approx(2.5, rel=1e-4)
    assert [u["used"] for u in meta["uv"]] == ["box"]  # photo-region UVs are not physical
    assert np.allclose(meta["color_mean"], target, atol=1)

    mesh = trimesh.load(out, force="mesh", process=False)
    assert tuple(mesh.extents) == pytest.approx((0.60, 0.45, 0.60), abs=1e-4)
    uv = mesh.visual.uv
    assert uv is not None
    # the 60 cm round top (glTF +Y up) spans 1,5 repeats of the 40 cm tile in each direction
    top_faces = mesh.faces[mesh.face_normals[:, 1] > 0.99]
    top_uv = uv[np.unique(top_faces)]
    assert np.ptp(top_uv, axis=0) == pytest.approx([1.5, 1.5], abs=0.01)
    # vertical grain: on the column U runs along the height (0,45 m − top → ≤ 1,125 repeats)
    side_faces = mesh.faces[np.abs(mesh.face_normals[:, 1]) < 0.1]
    side_v = mesh.vertices[np.unique(side_faces)]
    side_u = uv[np.unique(side_faces), 0]
    assert np.corrcoef(side_v[:, 1], side_u)[0, 1] > 0.99
    material = mesh.visual.material
    assert material.roughnessFactor in (None, 1.0)  # glTF default 1 is omitted
    assert material.metallicFactor in (None, 0.0)
    assert material.normalTexture is None

    paths = render_views(out, tmp_path / "renders", size=1024, blender_bin=binary)
    three_quarter = paths[3]
    RENDER_OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(three_quarter, RENDER_OUT)
    with Image.open(three_quarter) as img:
        rgb = np.asarray(img.convert("RGB")).astype(float)
    piece_px = rgb[rgb.min(axis=2) < 245]
    mean = piece_px.mean(axis=0)
    assert mean[0] > mean[1] > mean[2]  # warm, not grey
    assert np.all(np.abs(mean - np.array(target)) < 35), (mean, target)

    # end to end: the re-skinned piece through the Pietra-proven delivery
    from harness.core.models import Piece
    from harness.post.deliver import deliver
    from test_deliver import assert_usdz_arkit_ok, assert_web_glb  # tests/ is on sys.path

    piece = Piece(
        id="p99", name="Mesa auxiliar", store="Tienda", source_url="https://example.com",
        category="macizo_mate", images=[FIXTURE_PEDESTAL], width_cm=60, height_cm=45,
        depth_cm=60,
    )  # fmt: skip
    result = deliver(out.parent, piece, blender_bin=binary)
    assert result.optimize_error is None
    assert_web_glb(result.glb_path)
    assert_web_glb(result.preview_glb_path)
    delivered = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert_usdz_arkit_ok(delivered["usdz_arkit"])
    assert_usdz_arkit_ok(delivered["preview"]["usdz_arkit"])
    # tiled UVs (outside [0, 1]) survive quantization
    web = trimesh.load(result.glb_path, force="mesh", process=False)
    assert np.ptp(web.visual.uv, axis=0).max() > 1.2
