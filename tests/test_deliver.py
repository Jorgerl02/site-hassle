"""Tests for the web delivery (``bpy_deliver`` + ``deliver``).

Real-Blender tests are opt-in: set ``HARNESS_BLENDER_TEST_BIN=/path/to/blender`` (the
autouse fixture in conftest removes ``BLENDER_BIN``); they skip when it is unset.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import zipfile
from pathlib import Path

import pytest
import trimesh

from harness.core.blender import BlenderRun
from harness.core.models import Piece
from harness.post import bpy_deliver, deliver
from harness.post.deliver import (
    MODEL_VIEWER_SRC,
    BlenderDeliverError,
    build_args,
    format_dimensions,
    parse_deliver_meta,
    render_viewer,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deliver"
REPO = Path(__file__).resolve().parents[1]
REAL_CANDS = {
    "p05": REPO / "runs/mcp-higgsfield/p05/MG_TRELLIS2/cand_1",
    "p15": REPO / "runs/mcp-higgsfield/p15/MG_TRELLIS2/cand_1",
}


# --------------------------------------------------------------------------- bpy_deliver


def test_bpy_parse_args_defaults() -> None:
    ns = bpy_deliver.parse_args(
        ["--in", "a.glb", "--out-glb", "b.glb", "--out-usdz", "c.usdz", "--meta", "m.json"]
    )
    assert (ns.max_tris, ns.max_tex, ns.jpeg_quality) == (60_000, 2048, 85)
    assert ns.tmp_dir is None


@pytest.mark.parametrize("bad", [["--max-tris", "0"], ["--max-tex", "0"], ["--jpeg-quality", "0"]])
def test_bpy_parse_args_rejects_bad_limits(bad: list[str]) -> None:
    base = ["--in", "a", "--out-glb", "b", "--out-usdz", "c", "--meta", "m"]
    with pytest.raises(SystemExit):
        bpy_deliver.parse_args(base + bad)


@pytest.mark.parametrize(
    ("max_tex", "expected"),
    [(2048, ("2048", 2048)), (1024, ("1024", 1024)), (1500, ("CUSTOM", 1500))],
)
def test_usdz_downscale(max_tex: int, expected: tuple[str, int]) -> None:
    assert bpy_deliver.usdz_downscale(max_tex) == expected


# --------------------------------------------------------------------------- arguments


def test_build_args_round_trips_through_bpy_parser(tmp_path: Path) -> None:
    args = build_args(
        tmp_path / "in.glb", tmp_path / "web.glb", tmp_path / "m.usdz", tmp_path / "meta.json",
        max_tris=30_000, max_tex=1024, tmp_dir=tmp_path / "tmp",
    )  # fmt: skip
    ns = bpy_deliver.parse_args(bpy_deliver.script_argv(["blender", "--", *args]))
    assert ns.glb_in == str(tmp_path / "in.glb")
    assert ns.out_glb == str(tmp_path / "web.glb")
    assert ns.out_usdz == str(tmp_path / "m.usdz")
    assert ns.meta == str(tmp_path / "meta.json")
    assert (ns.max_tris, ns.max_tex, ns.jpeg_quality) == (30_000, 1024, 85)
    assert ns.tmp_dir == str(tmp_path / "tmp")


def test_build_args_without_tmp_dir(tmp_path: Path) -> None:
    args = build_args(tmp_path / "a", tmp_path / "b", tmp_path / "c", tmp_path / "d")
    assert "--tmp-dir" not in args
    assert args[args.index("--max-tris") + 1] == "60000"


# --------------------------------------------------------------------------- meta parsing


def test_parse_deliver_meta_fixture() -> None:
    data = parse_deliver_meta(FIXTURES / "deliver_meta.json")
    assert data["glb_bytes"] == 1_175_588
    assert data["tris_after"] == 58_799
    assert [t["format"] for t in data["textures"]] == ["JPEG", "JPEG"]


def test_parse_deliver_meta_missing_and_invalid(tmp_path: Path) -> None:
    with pytest.raises(BlenderDeliverError, match="no escribió"):
        parse_deliver_meta(tmp_path / "nope.json", log="LOG")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"glb_bytes": 1}), encoding="utf-8")
    with pytest.raises(BlenderDeliverError, match="inválido"):
        parse_deliver_meta(bad)


# --------------------------------------------------------------------------- viewer


def test_render_viewer_paths_and_attributes(piece: Piece) -> None:
    page = render_viewer(piece)
    tag = re.search(r"<model-viewer\b[^>]*>", page, re.S).group(0)
    assert 'src="model_web.glb"' in tag
    assert 'ios-src="model.usdz"' in tag
    assert 'ar-modes="webxr scene-viewer quick-look"' in tag
    assert re.search(r"\sar\s", tag) and "camera-controls" in tag
    assert 'ar-scale="fixed"' in tag
    assert f'<script type="module" src="{MODEL_VIEWER_SRC}"></script>' in page
    assert re.search(r"@google/model-viewer@\d+\.\d+\.\d+/", MODEL_VIEWER_SRC)
    assert "Mesa de roble" in page
    assert "Ancho 120 × alto 75 × fondo 60 cm" in page
    assert not re.search(r"\$\{?[A-Za-z_]", page)  # every placeholder substituted


def test_render_viewer_without_usdz_and_escaping(piece: Piece) -> None:
    hostile = piece.model_copy(update={"name": 'Mesa "A" <b>'})
    page = render_viewer(hostile, usdz_name=None)
    assert "ios-src" not in page
    assert "<b>" not in page and "&lt;b&gt;" in page and "&quot;A&quot;" in page


def test_format_dimensions_decimal_comma(piece: Piece) -> None:
    thin = piece.model_copy(update={"width_cm": 12.5, "height_cm": 20, "depth_cm": 1.8})
    assert format_dimensions(thin) == "Ancho 12,5 × alto 20 × fondo 1,8 cm"


# --------------------------------------------------------------------------- deliver (mocked)


def _fake_blender(glb_sizes: list[int], calls: list[list[str]], usdz_error: str | None = None):
    """Stand-in for ``run_blender_script`` that writes outputs of the given sizes."""

    def fake(script: Path, args: list[str], timeout: int = 600, blender_bin=None) -> BlenderRun:
        assert script == deliver.BPY_DELIVER_SCRIPT
        ns = bpy_deliver.parse_args(args)
        calls.append(args)
        size = glb_sizes[len(calls) - 1]
        Path(ns.out_glb).write_bytes(b"\0" * size)
        if usdz_error is None:
            Path(ns.out_usdz).write_bytes(b"\0" * 100)
        Path(ns.tmp_dir).mkdir(parents=True, exist_ok=True)
        meta = {
            "glb_bytes": size,
            "usdz_bytes": None if usdz_error else 100,
            "usdz_error": usdz_error,
            "tris_before": 100_000,
            "tris_after": min(ns.max_tris, 100_000),
            "max_tris": ns.max_tris,
            "max_tex": ns.max_tex,
            "textures": [{"name": "Image_0", "after": [ns.max_tex, ns.max_tex]}],
            "seconds": 1.5,
        }
        Path(ns.meta).write_text(json.dumps(meta), encoding="utf-8")
        return BlenderRun(["blender", *args], 0, "ok", "", 1.5)

    return fake


@pytest.fixture
def cand_dir(tmp_path: Path) -> Path:
    cand = tmp_path / "cand_1"
    cand.mkdir()
    (cand / "model_post.glb").write_bytes(b"glb")
    return cand


def test_deliver_within_limit_single_attempt(
    cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(deliver, "run_blender_script", _fake_blender([1_000_000], calls))
    result = deliver.deliver(cand_dir, piece)
    assert len(calls) == 1
    assert calls[0][calls[0].index("--in") + 1] == str(cand_dir / "model_post.glb")
    assert result.within_limit and not result.retried
    assert (result.max_tris, result.max_tex) == (60_000, 2048)
    assert result.glb_path == cand_dir / "model_web.glb"
    assert result.usdz_path == cand_dir / "model.usdz" and result.usdz_bytes == 100
    assert 'ios-src="model.usdz"' in result.viewer_path.read_text(encoding="utf-8")
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["within_limit"] is True and meta["piece_id"] == "p01"
    assert len(meta["attempts"]) == 1
    assert not (cand_dir / deliver.TMP_DIRNAME).exists()
    assert (cand_dir / deliver.DELIVER_LOG_FILENAME).is_file()


def test_deliver_retries_once_when_too_big(
    cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(deliver, "run_blender_script", _fake_blender([6_000, 3_000], calls))
    out = tmp_path / "outputs" / "p01"
    result = deliver.deliver(cand_dir, piece, size_limit_bytes=5_000, out_dir=out)
    assert len(calls) == 2
    second = bpy_deliver.parse_args(calls[1])
    assert (second.max_tris, second.max_tex) == (30_000, 1024)
    assert result.retried and result.within_limit
    assert result.glb_bytes == 3_000 and (result.max_tris, result.max_tex) == (30_000, 1024)
    assert result.glb_path.parent == out and result.viewer_path.parent == out
    assert [a["glb_bytes"] for a in result.attempts] == [6_000, 3_000]


def test_deliver_still_too_big_after_retry_does_not_raise(
    cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(deliver, "run_blender_script", _fake_blender([9_000, 8_000, 1], calls))
    result = deliver.deliver(cand_dir, piece, size_limit_bytes=5_000)
    assert len(calls) == 2  # exactly one retry
    assert not result.within_limit
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["within_limit"] is False and len(meta["attempts"]) == 2


def test_deliver_without_usdz_omits_ios_src(
    cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    fake = _fake_blender([1_000], calls, usdz_error="RuntimeError: boom")
    monkeypatch.setattr(deliver, "run_blender_script", fake)
    result = deliver.deliver(cand_dir, piece)
    assert result.usdz_path is None and result.usdz_error == "RuntimeError: boom"
    assert "ios-src" not in result.viewer_path.read_text(encoding="utf-8")


def test_deliver_blender_failure_raises_with_log(
    cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(script: Path, args: list[str], timeout: int = 600, blender_bin=None) -> BlenderRun:
        return BlenderRun(["blender"], 1, "", "Traceback: kaput", 0.1)

    monkeypatch.setattr(deliver, "run_blender_script", failing)
    with pytest.raises(BlenderDeliverError, match="kaput"):
        deliver.deliver(cand_dir, piece)


def test_deliver_missing_input(tmp_path: Path, piece: Piece) -> None:
    with pytest.raises(FileNotFoundError, match="model_post.glb"):
        deliver.deliver(tmp_path, piece)


# --------------------------------------------------------------------------- real Blender


def _blender_bin() -> Path:
    value = os.environ.get("HARNESS_BLENDER_TEST_BIN", "").strip()
    if not value or not Path(value).is_file():
        pytest.skip("Blender real no solicitado (HARNESS_BLENDER_TEST_BIN)")
    return Path(value)


def test_deliver_real_blender_synthetic_box(tmp_path: Path, piece: Piece) -> None:
    binary = _blender_bin()
    cand = tmp_path / "cand_1"
    cand.mkdir()
    trimesh.creation.box(extents=(1.2, 0.75, 0.6)).export(cand / "model_post.glb")
    result = deliver.deliver(cand, piece, blender_bin=binary)
    assert result.glb_path.is_file() and result.within_limit
    assert result.usdz_path is not None and result.usdz_path.is_file()
    assert result.tris_after == 12
    assert result.glb_bytes == result.glb_path.stat().st_size


@pytest.mark.parametrize("piece_id", sorted(REAL_CANDS))
def test_deliver_real_blender_real_model(tmp_path: Path, piece: Piece, piece_id: str) -> None:
    binary = _blender_bin()
    src = REAL_CANDS[piece_id] / "model_post.glb"
    if not src.is_file():
        pytest.skip(f"No existe {src}")
    cand = tmp_path / "cand_1"
    cand.mkdir()
    shutil.copy(src, cand / "model_post.glb")
    result = deliver.deliver(cand, piece, blender_bin=binary)
    assert result.glb_bytes < 5_000_000
    assert result.tris_after <= 60_000
    assert result.usdz_path is not None and result.usdz_path.is_file()
    assert all(t["format"] in {"JPEG", "PNG"} for t in result.textures)
    # Check the real bytes, not the script's own labels.
    with zipfile.ZipFile(result.usdz_path) as usdz:
        textures = [n for n in usdz.namelist() if n.startswith("textures/")]
        assert textures
        for name in textures:
            assert _image_magic(usdz.read(name)[:8]) in {"JPEG", "PNG"}, name
    gltf, binary_chunk = _read_glb(result.glb_path)
    assert gltf["images"]
    for image in gltf["images"]:
        view = gltf["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        magic = _image_magic(binary_chunk[start : start + 8])
        assert magic in {"JPEG", "PNG"}
        assert image["mimeType"] == f"image/{magic.lower()}"
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["tris_within_limit"] is True
    assert result.meta_path.read_text(encoding="utf-8").endswith("\n")


def _image_magic(head: bytes) -> str:
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head.startswith(b"\x89PNG"):
        return "PNG"
    return repr(head)


def _read_glb(path: Path) -> tuple[dict, bytes]:
    """(JSON chunk, BIN chunk) of a GLB container."""
    data = path.read_bytes()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20 : 20 + json_len])
    bin_start = 20 + json_len
    bin_len = struct.unpack_from("<I", data, bin_start)[0]
    return gltf, data[bin_start + 8 : bin_start + 8 + bin_len]
