"""Post-processing tests.

Real-Blender tests are opt-in: set ``HARNESS_BLENDER_TEST_BIN=/path/to/blender`` (the
autouse fixture in conftest removes ``BLENDER_BIN``); they skip when it is unset.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
import trimesh

from harness.core.blender import BlenderNotAvailable, BlenderRun
from harness.core.models import Piece
from harness.post import blender_post, bpy_post
from harness.post.blender_post import BlenderPostError, build_args, parse_post_meta, postprocess

FIXTURE_META = Path(__file__).parent / "fixtures" / "post" / "post_meta.json"


# ---------------------------------------------------------------- bpy_post pure helpers


def test_script_argv_takes_args_after_double_dash() -> None:
    argv = ["blender", "--background", "--python", "bpy_post.py", "--", "--in", "a.glb"]
    assert bpy_post.script_argv(argv) == ["--in", "a.glb"]
    assert bpy_post.script_argv(["blender"]) == []


def test_bpy_post_parses_build_args(piece: Piece, tmp_path: Path) -> None:
    args = build_args(tmp_path / "in.glb", tmp_path / "out.glb", tmp_path / "m.json", piece)
    ns = bpy_post.parse_args(args)
    assert ns.glb_in == str(tmp_path / "in.glb")
    assert ns.glb_out == str(tmp_path / "out.glb")
    assert ns.meta == str(tmp_path / "m.json")
    assert (ns.width, ns.height, ns.depth) == (120.0, 75.0, 60.0)
    assert ns.max_tris == 150_000
    assert ns.max_tex == 2048
    assert ns.draco is False
    assert "--draco" not in args


def test_build_args_draco_opt_in(piece: Piece, tmp_path: Path) -> None:
    args = build_args(
        tmp_path / "i.glb", tmp_path / "o.glb", tmp_path / "m.json", piece, draco=True
    )
    assert bpy_post.parse_args(args).draco is True


def test_build_args_custom_limits(piece: Piece, tmp_path: Path) -> None:
    args = build_args(
        tmp_path / "i.glb", tmp_path / "o.glb", tmp_path / "m.json", piece,
        max_tris=1000, max_texture_px=512,
    )  # fmt: skip
    assert args[args.index("--max-tris") + 1] == "1000"
    assert args[args.index("--max-tex") + 1] == "512"
    assert all(isinstance(a, str) for a in args)


def test_relative_errors_are_signed() -> None:
    errors = bpy_post.relative_errors(
        {"width": 120.0, "depth": 61.2, "height": 73.5},
        {"width": 120.0, "depth": 60.0, "height": 75.0},
    )
    assert errors["width"] == 0.0
    assert errors["depth"] == pytest.approx(0.02)
    assert errors["height"] == pytest.approx(-0.02)


TARGET = {"width": 120.0, "depth": 60.0, "height": 75.0}


def test_matched_errors_forgive_rotation_about_vertical() -> None:
    # Model rotated 90° about the vertical: width and depth extents swapped.
    measured = {"width": 60.0, "depth": 120.0, "height": 75.0}
    assert bpy_post.matched_errors(measured, TARGET) == pytest.approx(
        {"width": 0.0, "depth": 0.0, "height": 0.0}
    )
    axis = bpy_post.relative_errors(measured, TARGET)
    assert axis["width"] == pytest.approx(-0.5) and axis["depth"] == pytest.approx(1.0)


def test_matched_errors_catch_piece_lying_on_its_side() -> None:
    # Height and width swapped: the vertical extent must still be compared with height_cm.
    measured = {"width": 75.0, "depth": 60.0, "height": 120.0}
    errors = bpy_post.matched_errors(measured, TARGET)
    assert errors["height"] == pytest.approx(0.6)
    assert errors["width"] == pytest.approx(-0.375)
    assert errors["depth"] == pytest.approx(0.0)


def test_uniform_scale_factor_uses_largest_extents() -> None:
    # Rotated raw model: its longest extent is on the named "depth" axis.
    raw = {"width": 30.0, "depth": 60.0, "height": 37.5}
    assert bpy_post.uniform_scale_factor(raw, TARGET) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        bpy_post.uniform_scale_factor({"width": 0.0, "depth": 0.0, "height": 0.0}, TARGET)


@pytest.mark.parametrize(
    ("size", "expected"),
    [((1024, 512), (1024, 512)), ((4096, 4096), (2048, 2048)), ((8192, 2048), (2048, 512))],
)
def test_clamp_size_keeps_aspect(size: tuple[int, int], expected: tuple[int, int]) -> None:
    assert bpy_post.clamp_size(*size, 2048) == expected


# ---------------------------------------------------------------- post_meta parsing


def test_parse_post_meta_fixture(tmp_path: Path) -> None:
    result = parse_post_meta(FIXTURE_META, tmp_path / "out.glb", log="log")
    assert result.errors == {"width": 0.0, "height": -0.024, "depth": 0.02}
    assert result.max_abs_error == pytest.approx(0.024)
    assert result.scale_ok is True
    assert (result.tris_before, result.tris_after) == (412000, 149870)
    assert result.textures[0]["after"] == [2048, 2048]
    assert result.seconds == 12.5
    assert result.scale_factor == 1.2
    assert result.glb_path == tmp_path / "out.glb"
    assert result.raw["blender_version"] == "4.5.3 LTS"
    assert result.errors_axis == {"width": 0.0, "depth": 0.02, "height": -0.024}
    assert result.draco is False


def test_scale_ok_false_over_tolerance(tmp_path: Path) -> None:
    data = json.loads(FIXTURE_META.read_text())
    data["errors"]["height"] = -0.05
    meta = tmp_path / "post_meta.json"
    meta.write_text(json.dumps(data))
    assert parse_post_meta(meta, tmp_path / "o.glb").scale_ok is False


def test_parse_post_meta_missing_file(tmp_path: Path) -> None:
    with pytest.raises(BlenderPostError, match="no escribió"):
        parse_post_meta(tmp_path / "nope.json", tmp_path / "o.glb", log="LOGTEXT")


def test_parse_post_meta_malformed(tmp_path: Path) -> None:
    meta = tmp_path / "post_meta.json"
    meta.write_text(json.dumps({"errors": {"width": 0.0}}))
    with pytest.raises(BlenderPostError, match="inválido"):
        parse_post_meta(meta, tmp_path / "o.glb")


# ---------------------------------------------------------------- postprocess with fake Blender


def _fake_runner(returncode: int = 0, write_outputs: bool = True):
    calls: list[dict] = []

    def fake(script: Path, args: list[str], timeout: int = 600, blender_bin=None) -> BlenderRun:
        calls.append({"script": script, "args": args, "timeout": timeout})
        if write_outputs:
            out = Path(args[args.index("--out") + 1])
            meta = Path(args[args.index("--meta") + 1])
            out.write_bytes(b"glb")
            shutil.copyfile(FIXTURE_META, meta)
        cmd = ["blender", "--background", "--python", str(script), "--", *args]
        return BlenderRun(cmd, returncode, "stdout-text", "stderr-text", 1.0)

    return fake, calls


def test_postprocess_success(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, cube_glb: Path, tmp_path: Path
) -> None:
    fake, calls = _fake_runner()
    monkeypatch.setattr(blender_post, "run_blender_script", fake)
    out = tmp_path / "cand_1" / "model_post.glb"
    result = postprocess(cube_glb, out, piece, timeout=42)

    assert calls[0]["script"] == blender_post.BPY_POST_SCRIPT
    assert calls[0]["script"].is_file()
    assert calls[0]["timeout"] == 42
    assert calls[0]["args"][calls[0]["args"].index("--meta") + 1] == str(
        out.parent / "post_meta.json"
    )
    assert "--draco" not in calls[0]["args"]
    assert result.glb_path == out
    assert result.tris_after == 149870
    assert "stdout-text" in (out.parent / "post_blender.log").read_text()


def test_postprocess_nonzero_exit_raises_with_log(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, cube_glb: Path, tmp_path: Path
) -> None:
    fake, _ = _fake_runner(returncode=1, write_outputs=False)
    monkeypatch.setattr(blender_post, "run_blender_script", fake)
    with pytest.raises(BlenderPostError, match="código 1") as info:
        postprocess(cube_glb, tmp_path / "model_post.glb", piece)
    assert "stderr-text" in str(info.value)
    assert "stderr-text" in info.value.log


def test_postprocess_missing_output_raises(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, cube_glb: Path, tmp_path: Path
) -> None:
    fake, _ = _fake_runner(returncode=0, write_outputs=False)
    monkeypatch.setattr(blender_post, "run_blender_script", fake)
    out = tmp_path / "model_post.glb"
    out.write_bytes(b"stale")  # left over from a previous run: must not be accepted
    (tmp_path / "post_meta.json").write_text(FIXTURE_META.read_text())
    with pytest.raises(BlenderPostError, match="no escribió"):
        postprocess(cube_glb, out, piece)
    assert not out.exists()


def test_postprocess_missing_input(piece: Piece, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        postprocess(tmp_path / "missing.glb", tmp_path / "o.glb", piece)


def test_postprocess_without_blender_raises(
    monkeypatch: pytest.MonkeyPatch, piece: Piece, cube_glb: Path, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here
    with pytest.raises(BlenderNotAvailable):
        postprocess(cube_glb, tmp_path / "o.glb", piece)


# ---------------------------------------------------------------- real Blender (skipped here)


def _blender_bin() -> Path:
    value = os.environ.get("HARNESS_BLENDER_TEST_BIN", "").strip()
    if not value or not Path(value).is_file():
        pytest.skip("Blender real no solicitado (HARNESS_BLENDER_TEST_BIN)")
    return Path(value)


def test_postprocess_real_blender(piece: Piece, tmp_path: Path) -> None:
    binary = _blender_bin()
    src = tmp_path / "in.glb"
    # Wrong scale and rotated about the vertical (glTF X = depth, Z = width) on purpose.
    trimesh.creation.box(extents=(0.3, 0.375, 0.6)).export(src)
    result = postprocess(src, tmp_path / "out.glb", piece, blender_bin=binary)
    assert result.glb_path.is_file()
    assert result.scale_factor == pytest.approx(2.0, rel=1e-4)
    assert result.max_abs_error == pytest.approx(0.0, abs=1e-3)
    assert result.tris_after <= 150_000
    assert result.draco is False
    extents = trimesh.load(result.glb_path, force="mesh").extents  # readable without Draco
    assert sorted(extents) == pytest.approx([0.6, 0.75, 1.2], rel=1e-3)
