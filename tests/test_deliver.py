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
import subprocess
import time
import zipfile
from pathlib import Path

import pytest
import trimesh

from harness.core.blender import BlenderRun
from harness.core.models import Piece
from harness.post import bpy_deliver, deliver
from harness.post.deliver import (
    GLTF_TRANSFORM_PACKAGE,
    MODEL_VIEWER_SRC,
    BlenderDeliverError,
    build_args,
    build_optimize_args,
    format_dimensions,
    glb_extensions,
    optimize_glb,
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
    assert ns.preview_glb is None and ns.preview_usdz is None
    assert (ns.preview_max_tris, ns.preview_max_tex) == (15_000, 512)


def test_bpy_parse_args_preview_outputs_go_together() -> None:
    base = ["--in", "a", "--out-glb", "b", "--out-usdz", "c", "--meta", "m"]
    with pytest.raises(SystemExit):
        bpy_deliver.parse_args(base + ["--preview-glb", "p.glb"])
    with pytest.raises(SystemExit):
        bpy_deliver.parse_args(
            base + ["--preview-glb", "p", "--preview-usdz", "u", "--preview-max-tris", "0"]
        )


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
    assert "--tmp-dir" not in args and "--preview-glb" not in args
    assert args[args.index("--max-tris") + 1] == "60000"


def test_build_args_preview_round_trip(tmp_path: Path) -> None:
    args = build_args(
        tmp_path / "in.glb", tmp_path / "raw.glb", tmp_path / "m.usdz", tmp_path / "meta.json",
        preview_glb=tmp_path / "p.glb", preview_usdz=tmp_path / "p.usdz",
        preview_max_tris=10_000, preview_max_tex=256,
    )  # fmt: skip
    ns = bpy_deliver.parse_args(args)
    assert ns.preview_glb == str(tmp_path / "p.glb")
    assert ns.preview_usdz == str(tmp_path / "p.usdz")
    assert (ns.preview_max_tris, ns.preview_max_tex) == (10_000, 256)


# --------------------------------------------------------------------------- gltf-transform


def test_build_optimize_args_pietra_flags(tmp_path: Path) -> None:
    runner = ["/usr/bin/npx", "--no-install", GLTF_TRANSFORM_PACKAGE]
    cmd = build_optimize_args(
        tmp_path / "raw.glb", tmp_path / "web.glb", texture_size=2048, runner=runner
    )
    assert cmd[:4] == [*runner, "optimize"]
    assert GLTF_TRANSFORM_PACKAGE == "@gltf-transform/cli@4.5.1"
    assert cmd[4:6] == [str(tmp_path / "raw.glb"), str(tmp_path / "web.glb")]
    flags = dict(zip(cmd[6::2], cmd[7::2], strict=True))
    assert flags == {
        "--compress": "quantize",  # KHR_mesh_quantization: not meshopt, not Draco
        "--texture-compress": "webp",
        "--texture-size": "2048",
        "--simplify": "false",  # Blender's decimation owns the triangle budget
    }
    assert "draco" not in " ".join(cmd) and "meshopt" not in " ".join(cmd)
    assert "--yes" not in cmd  # never downloads at delivery time
    local = build_optimize_args(tmp_path / "a", tmp_path / "b", texture_size=512)
    assert local[:2] == [str(deliver.LOCAL_GLTF_TRANSFORM), "optimize"]


def test_tools_gltf_package_is_pinned() -> None:
    package = json.loads((deliver.GLTF_TOOLS_DIR / "package.json").read_text(encoding="utf-8"))
    assert package["dependencies"] == {"@gltf-transform/cli": "4.5.1"}
    lock = json.loads((deliver.GLTF_TOOLS_DIR / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"]["node_modules/@gltf-transform/cli"]["version"] == "4.5.1"
    assert GLTF_TRANSFORM_PACKAGE.endswith("@" + package["dependencies"]["@gltf-transform/cli"])


def test_gltf_transform_command_prefers_local_install(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "node_modules" / ".bin" / "gltf-transform"
    monkeypatch.setattr(deliver, "LOCAL_GLTF_TRANSFORM", local)
    monkeypatch.setattr(deliver.shutil, "which", lambda name: "/usr/bin/npx")
    assert deliver.gltf_transform_command() == [
        "/usr/bin/npx", "--no-install", GLTF_TRANSFORM_PACKAGE,
    ]  # fmt: skip
    local.parent.mkdir(parents=True)
    local.write_text("#!/bin/sh\n")
    assert deliver.gltf_transform_command() == [str(local)]
    local.unlink()
    monkeypatch.setattr(deliver.shutil, "which", lambda name: None)
    assert deliver.gltf_transform_command() is None


def test_optimize_glb_runs_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(deliver, "LOCAL_GLTF_TRANSFORM", tmp_path / "missing")
    monkeypatch.setattr(deliver.shutil, "which", lambda name: "/opt/node/bin/npx")

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        assert kwargs["timeout"] == 42 and kwargs["check"] is False
        Path(cmd[cmd.index("optimize") + 2]).write_bytes(b"optimized")
        return subprocess.CompletedProcess(cmd, 0, "done", "")

    monkeypatch.setattr(deliver.subprocess, "run", fake_run)
    src, dst = tmp_path / "raw.glb", tmp_path / "web.glb"
    src.write_bytes(b"raw")
    error, log = optimize_glb(src, dst, texture_size=512, timeout=42)
    assert error is None and dst.read_bytes() == b"optimized"
    assert calls[0][:3] == ["/opt/node/bin/npx", "--no-install", GLTF_TRANSFORM_PACKAGE]
    assert calls[0][calls[0].index("--texture-size") + 1] == "512"
    assert "[exit 0]" in log


def test_optimize_glb_falls_back_to_plain_glb(tmp_path: Path, monkeypatch) -> None:
    src, dst = tmp_path / "raw.glb", tmp_path / "web.glb"
    src.write_bytes(b"raw")
    monkeypatch.setattr(deliver, "LOCAL_GLTF_TRANSFORM", tmp_path / "missing")
    monkeypatch.setattr(deliver.shutil, "which", lambda name: None)
    error, _ = optimize_glb(src, dst, texture_size=2048)
    assert "npm ci" in error and dst.read_bytes() == b"raw"

    monkeypatch.setattr(deliver.shutil, "which", lambda name: "/usr/bin/npx")
    monkeypatch.setattr(
        deliver.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "boom"),
    )  # fmt: skip
    error, log = optimize_glb(src, dst, texture_size=2048)
    assert "código 1" in error and "boom" in log and dst.read_bytes() == b"raw"

    def timeout(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(deliver.subprocess, "run", timeout)
    error, _ = optimize_glb(src, dst, texture_size=2048)
    assert "TimeoutExpired" in error and dst.read_bytes() == b"raw"


def test_glb_extensions(tmp_path: Path) -> None:
    glb = tmp_path / "a.glb"
    _write_glb(glb, {"asset": {"version": "2.0"},
                     "extensionsUsed": ["KHR_mesh_quantization", "EXT_texture_webp"]})  # fmt: skip
    assert glb_extensions(glb) == ["EXT_texture_webp", "KHR_mesh_quantization"]
    other = tmp_path / "b.glb"
    other.write_bytes(b"not a glb at all, really")
    assert glb_extensions(other) == []


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


def _write_glb(path: Path, gltf: dict) -> None:
    body = json.dumps(gltf).encode()
    body += b" " * (-len(body) % 4)
    path.write_bytes(
        b"glTF" + struct.pack("<II", 2, 20 + len(body)) + struct.pack("<I", len(body)) + b"JSON"
        + body
    )  # fmt: skip


@pytest.fixture
def fake_npx(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """gltf-transform stand-in: copies the plain GLB to the output (same size) and records
    the command."""
    calls: list[list[str]] = []
    monkeypatch.setattr(deliver, "LOCAL_GLTF_TRANSFORM", Path("/nonexistent/gltf-transform"))
    monkeypatch.setattr(deliver.shutil, "which", lambda name: "/usr/bin/npx")

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        at = cmd.index("optimize")
        shutil.copyfile(cmd[at + 1], cmd[at + 2])
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(deliver.subprocess, "run", fake_run)
    return calls


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
        preview = None
        if ns.preview_glb:
            Path(ns.preview_glb).write_bytes(b"\0" * 300)
            Path(ns.preview_usdz).write_bytes(b"\0" * 200)
            preview = {
                "glb_bytes": 300,
                "usdz_bytes": 200,
                "usdz_error": None,
                "usdz_arkit": {"errors": [], "failed_checks": [], "scale_issues": []},
                "tris_after": min(ns.preview_max_tris, 100_000),
                "max_tris": ns.preview_max_tris,
                "max_tex": ns.preview_max_tex,
                "textures": [],
            }
        meta = {
            "preview": preview,
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
    fake_npx: list[list[str]], cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
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
    fake_npx: list[list[str]],
    cand_dir: Path,
    piece: Piece,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
    fake_npx: list[list[str]], cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(deliver, "run_blender_script", _fake_blender([9_000, 8_000, 1], calls))
    result = deliver.deliver(cand_dir, piece, size_limit_bytes=5_000)
    assert len(calls) == 2  # exactly one retry
    assert not result.within_limit
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["within_limit"] is False and len(meta["attempts"]) == 2


def test_deliver_without_usdz_omits_ios_src(
    fake_npx: list[list[str]], cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    fake = _fake_blender([1_000], calls, usdz_error="RuntimeError: boom")
    monkeypatch.setattr(deliver, "run_blender_script", fake)
    result = deliver.deliver(cand_dir, piece)
    assert result.usdz_path is None and result.usdz_error == "RuntimeError: boom"
    assert "ios-src" not in result.viewer_path.read_text(encoding="utf-8")


def test_deliver_preview_outputs_and_meta(
    fake_npx: list[list[str]], cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(deliver, "run_blender_script", _fake_blender([1_000], calls))
    result = deliver.deliver(cand_dir, piece)
    ns = bpy_deliver.parse_args(calls[0])
    assert ns.out_glb == str(cand_dir / deliver.TMP_DIRNAME / "model_raw.glb")
    assert ns.preview_usdz == str(cand_dir / "preview" / "model_preview.usdz")
    assert (ns.preview_max_tris, ns.preview_max_tex) == (15_000, 512)
    # gltf-transform: web GLB at 2048 px, preview at 512 px
    sizes = [c[c.index("--texture-size") + 1] for c in fake_npx]
    assert sizes == ["2048", "512"]
    assert result.preview_glb_path == cand_dir / "preview" / "model_preview.glb"
    assert result.preview_usdz_path == cand_dir / "preview" / "model_preview.usdz"
    assert (result.preview_glb_bytes, result.preview_usdz_bytes) == (300, 200)
    assert result.preview_tris_after == 15_000 and result.warnings == []
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["compress"] == "quantize" and meta["texture_format"] == "webp"
    assert meta["preview"]["compress"] == "quantize"
    assert meta["preview"]["texture_format"] == "webp"
    assert meta["files"] == {
        "glb": "model_web.glb", "usdz": "model.usdz", "viewer": "viewer.html",
        "preview_glb": "preview/model_preview.glb", "preview_usdz": "preview/model_preview.usdz",
    }  # fmt: skip
    assert meta["sizes"] == {"glb": 1_000, "usdz": 100, "preview_glb": 300, "preview_usdz": 200}
    assert not {"draco", "draco_level", "jpeg_quality"} & set(meta)
    assert meta["warnings"] == [] and meta["strict"] is False and meta["deadline_s"] == 900


def test_deliver_without_preview(
    fake_npx: list[list[str]], cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(deliver, "run_blender_script", _fake_blender([1_000], calls))
    result = deliver.deliver(cand_dir, piece, preview=False)
    assert "--preview-glb" not in calls[0] and len(fake_npx) == 1
    assert result.preview_glb_path is None and result.preview_usdz_path is None
    assert not (cand_dir / "preview").exists()


def _failing_npx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deliver, "LOCAL_GLTF_TRANSFORM", Path("/nonexistent/gltf-transform"))
    monkeypatch.setattr(deliver.shutil, "which", lambda name: "/usr/bin/npx")
    monkeypatch.setattr(
        deliver.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "sharp missing"),
    )  # fmt: skip


def test_deliver_optimize_failure_warns_and_ships_plain_glb(
    cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    _failing_npx(monkeypatch)
    monkeypatch.setattr(deliver, "run_blender_script", _fake_blender([1_000], []))
    result = deliver.deliver(cand_dir, piece)
    assert result.optimize_error and result.glb_path.stat().st_size == 1_000
    assert len(result.warnings) == 2  # web GLB and preview GLB
    assert all("sin optimizar" in w for w in result.warnings)
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["warnings"] == result.warnings
    assert meta["compress"] is None and meta["preview"]["compress"] is None


def test_deliver_strict_raises_on_optimize_failure(
    cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    _failing_npx(monkeypatch)
    monkeypatch.setattr(deliver, "run_blender_script", _fake_blender([1_000], []))
    with pytest.raises(deliver.OptimizeError, match="sharp missing"):
        deliver.deliver(cand_dir, piece, strict=True)
    assert not (cand_dir / deliver.TMP_DIRNAME).exists()


def test_deliver_deadline_stops_before_retry(
    fake_npx: list[list[str]], cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    slow = _fake_blender([9_000, 1_000], calls)

    def slow_blender(script, args, timeout=600, blender_bin=None):
        assert timeout <= 0.3  # the per-run timeout is capped by what is left
        run = slow(script, args, timeout, blender_bin)
        time.sleep(0.35)
        return run

    monkeypatch.setattr(deliver, "run_blender_script", slow_blender)
    with pytest.raises(deliver.DeliverDeadlineExceeded, match="0.3 s"):
        deliver.deliver(cand_dir, piece, size_limit_bytes=5_000, deadline_s=0.3)
    assert len(calls) == 1  # the retry never started
    assert not (cand_dir / deliver.TMP_DIRNAME).exists()


def test_deliver_deadline_cuts_blender(
    cand_dir: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    def hanging(script, args, timeout=600, blender_bin=None):
        raise subprocess.TimeoutExpired(["blender"], timeout)

    monkeypatch.setattr(deliver, "run_blender_script", hanging)
    with pytest.raises(deliver.DeliverDeadlineExceeded, match="Blender"):
        deliver.deliver(cand_dir, piece, deadline_s=30)
    # the per-run timeout (shorter than the deadline) keeps its own exception
    with pytest.raises(subprocess.TimeoutExpired):
        deliver.deliver(cand_dir, piece, timeout=5, deadline_s=900)
    with pytest.raises(ValueError, match="deadline_s"):
        deliver.deliver(cand_dir, piece, deadline_s=0)


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
    assert result.optimize_error is None
    assert "KHR_mesh_quantization" in glb_extensions(result.glb_path)
    assert result.preview_glb_path == cand / "preview" / "model_preview.glb"
    assert result.preview_usdz_path == cand / "preview" / "model_preview.usdz"
    assert result.preview_tris_after == 12


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
    assert result.optimize_error is None
    assert_web_glb(result.glb_path)
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["tris_within_limit"] is True
    assert result.meta_path.read_text(encoding="utf-8").endswith("\n")
    assert_usdz_arkit_ok(meta["usdz_arkit"])
    # preview: ≤ 15k triangles, 512 px, quantize + WebP GLB and a Quick Look-valid USDZ
    assert result.preview_tris_after is not None and result.preview_tris_after <= 15_000
    assert_web_glb(result.preview_glb_path)
    assert result.preview_glb_bytes < result.glb_bytes
    assert all(max(t["after"]) <= 512 for t in meta["preview"]["textures"])
    assert_usdz_arkit_ok(meta["preview"]["usdz_arkit"])
    with zipfile.ZipFile(result.preview_usdz_path) as usdz:
        names = [n for n in usdz.namelist() if n.startswith("textures/")]
        assert names
        assert all(_image_magic(usdz.read(n)[:12]) in {"JPEG", "PNG"} for n in names)
    assert meta["files"]["preview_usdz"] == "preview/model_preview.usdz"
    assert meta["sizes"]["preview_usdz"] == result.preview_usdz_path.stat().st_size


def assert_web_glb(path: Path) -> None:
    """Pietra-proven web GLB: KHR_mesh_quantization + EXT_texture_webp, no Draco/meshopt,
    every embedded image really WebP."""
    gltf, binary_chunk = _read_glb(path)
    used = set(gltf.get("extensionsUsed", []))
    assert {"KHR_mesh_quantization", "EXT_texture_webp"} <= used, used
    assert not used & {"KHR_draco_mesh_compression", "EXT_meshopt_compression"}, used
    assert gltf["images"]
    for image in gltf["images"]:
        view = gltf["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        assert _image_magic(binary_chunk[start : start + 12]) == "WEBP"
        assert image["mimeType"] == "image/webp"


def assert_usdz_arkit_ok(report: dict | None) -> None:
    """``UsdUtils.ComplianceChecker(arkit=True)`` run inside Blender by bpy_deliver."""
    assert report is not None, "pxr no disponible en Blender"
    assert report["errors"] == [] and report["failed_checks"] == [], report
    assert report["scale_issues"] == [], report


def _image_magic(head: bytes) -> str:
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head.startswith(b"\x89PNG"):
        return "PNG"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WEBP"
    return repr(head)


def _read_glb(path: Path) -> tuple[dict, bytes]:
    """(JSON chunk, BIN chunk) of a GLB container."""
    data = path.read_bytes()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20 : 20 + json_len])
    bin_start = 20 + json_len
    bin_len = struct.unpack_from("<I", data, bin_start)[0]
    return gltf, data[bin_start + 8 : bin_start + 8 + bin_len]
