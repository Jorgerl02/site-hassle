from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import anthropic
import httpx2
import numpy as np
import pytest
import trimesh
from PIL import Image
from typer.testing import CliRunner

from conftest import piece_row, write_csv
from harness.cli import app
from harness.clients.vlm import VLMClient, VLMError, token_cost_usd
from harness.core import storage
from harness.core.blender import BlenderNotAvailable, run_blender_script
from harness.core.config import Settings
from harness.core.models import CSV_COLUMNS, GeometryMetrics, Scores, load_pieces
from harness.core.registry import get_variant
from harness.core.variant import FakeVariant, Variant
from harness.prep import clean

# --- models / CSV ---------------------------------------------------------------------------


def test_load_valid_csv(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path / "s.csv",
        [
            piece_row(),
            piece_row(id="p02", category="tapizado", rectilinear="", images="/abs/a.jpg"),
        ],
    )
    pieces = load_pieces(csv_path, root=tmp_path)
    assert [p.id for p in pieces] == ["p01", "p02"]
    assert pieces[0].images == [
        tmp_path / "data/images/p01/1.jpg",
        tmp_path / "data/images/p01/2.jpg",
    ]
    assert pieces[0].rectilinear is True and pieces[1].rectilinear is None
    assert pieces[1].images == [Path("/abs/a.jpg")]
    assert pieces[0].width_cm == 120.0


def test_header_only_csv_is_empty(tmp_path: Path) -> None:
    assert load_pieces(write_csv(tmp_path / "s.csv", [])) == []


def test_repo_sample_csv_has_expected_header() -> None:
    header = Path("data/sample.csv").read_text(encoding="utf-8").splitlines()[0]
    assert tuple(header.split(",")) == CSV_COLUMNS


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"category": "plastico"}, "línea 2"),
        ({"width_cm": "-3"}, "línea 2"),
        ({"rectilinear": "quizá"}, "rectilinear"),
        ({"images": ""}, "línea 2"),
    ],
)
def test_invalid_row_rejected(tmp_path: Path, override: dict[str, str], match: str) -> None:
    csv_path = write_csv(tmp_path / "s.csv", [piece_row(**override)])
    with pytest.raises(ValueError, match=match):
        load_pieces(csv_path)


def test_duplicate_ids_and_too_many_rows_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicado"):
        load_pieces(write_csv(tmp_path / "d.csv", [piece_row(), piece_row()]))
    rows = [piece_row(id=f"p{i:02d}") for i in range(31)]
    with pytest.raises(ValueError, match="máximo"):
        load_pieces(write_csv(tmp_path / "big.csv", rows))


def test_scores_and_geometry_models() -> None:
    with pytest.raises(ValueError):
        Scores(parecido=6, geometria=4, materiales=4, escala=4, apt=True)
    metrics = GeometryMetrics(
        width_cm=120,
        height_cm=75,
        depth_cm=60,
        err_width=0.01,
        err_height=0.04,
        err_depth=0.0,
        watertight=True,
        n_components=1,
        n_faces=12,
    )
    assert metrics.max_error == 0.04 and not metrics.scale_ok


# --- storage --------------------------------------------------------------------------------


def test_storage_layout(tmp_path: Path) -> None:
    workdir = storage.variant_dir("r1", "p01", "A", root=tmp_path)
    assert workdir == tmp_path / "r1/p01/A" and workdir.is_dir()
    cand = storage.candidate_dir(workdir, 1)
    assert cand == workdir / "cand_1" and cand.is_dir()
    assert storage.model_path(cand) == cand / "model.glb"
    assert storage.model_post_path(cand) == cand / "model_post.glb"
    assert storage.renders_dir(cand).is_dir()
    assert storage.scores_path("r1", root=tmp_path) == tmp_path / "r1/eval/scores.jsonl"
    assert storage.blind_sheet_path("r1", root=tmp_path).name == "blind_sheet.csv"
    assert storage.blind_key_path("r1", root=tmp_path).name == "blind_key.csv"
    assert storage.report_path("r1", root=tmp_path).name == "report.md"


def test_meta_roundtrip(tmp_path: Path) -> None:
    assert storage.read_meta(tmp_path) == {}
    storage.write_meta(tmp_path / "x", {"glb": Path("a/b.glb"), "cost_usd": 0.25})
    assert storage.read_meta(tmp_path / "x") == {"glb": "a/b.glb", "cost_usd": 0.25}


# --- variants / registry --------------------------------------------------------------------


def test_fake_variant_copies_fixture(tmp_path: Path, piece, cube_glb: Path) -> None:
    variant = FakeVariant(source_glb=cube_glb)
    assert isinstance(variant, Variant)
    result = variant.run(piece, tmp_path, candidates=2)
    assert result.variant == "FAKE" and result.piece_id == "p01"
    assert [c.index for c in result.candidates] == [1, 2]
    for cand in result.candidates:
        assert cand.glb_path == tmp_path / f"cand_{cand.index}" / "model.glb"
        assert cand.glb_path.read_bytes() == cube_glb.read_bytes()


def test_fake_variant_default_box_matches_piece(tmp_path: Path, piece) -> None:
    result = get_variant("fake").run(piece, tmp_path, candidates=1)
    mesh = trimesh.load(result.candidates[0].glb_path, force="mesh")
    assert mesh.extents == pytest.approx([1.20, 0.75, 0.60])


def test_unknown_variant() -> None:
    with pytest.raises(KeyError, match="FAKE"):
        get_variant("Z")


# --- config / blender -----------------------------------------------------------------------


def test_settings_env_file_and_environment(tmp_path: Path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("TRIPO_API_KEY=from-file\nBLENDER_BIN=\nMESHY_API_KEY=file\n")
    monkeypatch.setenv("MESHY_API_KEY", "from-env")
    settings = Settings.load(env)
    assert settings.tripo_api_key == "from-file"
    assert settings.meshy_api_key == "from-env"
    assert settings.blender_bin is None and settings.anthropic_api_key is None


def test_blender_not_available(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(BlenderNotAvailable):
        run_blender_script(tmp_path / "s.py", [])
    with pytest.raises(BlenderNotAvailable):
        run_blender_script(tmp_path / "s.py", [], blender_bin=tmp_path / "missing")


def test_blender_command_line(tmp_path: Path, monkeypatch) -> None:
    fake = tmp_path / "blender"
    fake.write_text('#!/bin/sh\necho "$@"\necho oops >&2\nexit 3\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("BLENDER_BIN", str(fake))
    run = run_blender_script(Path("job.py"), ["--in", Path("a.glb")], timeout=10)
    assert run.stdout.strip() == "--background --python job.py -- --in a.glb"
    assert run.stderr.strip() == "oops" and run.returncode == 3 and not run.ok


# --- prep/clean -----------------------------------------------------------------------------


def _fake_rembg(image: Image.Image) -> Image.Image:
    """Deterministic stand-in for rembg: non-grey pixels are the object."""
    rgb = np.asarray(image.convert("RGB"))
    alpha = np.where((rgb == 128).all(axis=-1), 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


@pytest.fixture
def no_rembg(monkeypatch) -> None:
    monkeypatch.setattr(clean, "_remove_background", _fake_rembg)


def _synthetic(path: Path, size: tuple[int, int], box: tuple[int, int, int, int]) -> Path:
    img = Image.new("RGB", size, (128, 128, 128))
    img.paste((200, 30, 30), box)
    img.save(path)
    return path


def test_clean_image_crops_pads_and_whitens(tmp_path: Path, no_rembg) -> None:
    src = _synthetic(tmp_path / "in.png", (1200, 900), (100, 200, 500, 400))  # 400×200 object
    out = clean.clean_image(src, tmp_path / "out" / "clean.png", size=512)
    img = Image.open(out).convert("RGB")
    assert img.size == (512, 512)
    assert img.getpixel((2, 2)) == (255, 255, 255)
    assert img.getpixel((256, 256)) == (200, 30, 30)
    # 400 px object + 2×32 px margin = 464 px → spans 400/464 of the width
    row = [img.getpixel((x, 256)) for x in range(512)]
    red = [x for x, px in enumerate(row) if px[0] > 150 and px[1] < 100]
    assert len(red) == pytest.approx(512 * 400 / 464, abs=4)


def test_validate_input(tmp_path: Path, no_rembg) -> None:
    good = _synthetic(tmp_path / "g.png", (1200, 1000), (200, 200, 900, 800))
    assert clean.validate_input(good) == []
    small = _synthetic(tmp_path / "s.png", (600, 400), (100, 100, 500, 300))
    problems = clean.validate_input(small)
    assert len(problems) == 1 and "Resolución" in problems[0]
    tiny_object = _synthetic(tmp_path / "t.png", (1200, 1000), (0, 0, 100, 100))
    assert "Objeto" in clean.validate_input(tiny_object)[0]


# --- clients/vlm ----------------------------------------------------------------------------


def _message(text: str, stop_reason: str = "end_turn") -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1000, "output_tokens": 200},
    }


def _vlm(responses: list[httpx2.Response], seen: list[dict]) -> VLMClient:
    queue = list(responses)

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(
            {
                "url": str(request.url),
                "headers": request.headers,
                "body": json.loads(request.content),
            }
        )
        return queue.pop(0)

    client = anthropic.Anthropic(
        api_key="test",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return VLMClient(client=client, sleep=lambda _: None)


def test_vlm_parses_json_and_records_cost(tmp_path: Path) -> None:
    img = tmp_path / "a.png"
    Image.new("RGB", (8, 8)).save(img)
    seen: list[dict] = []
    vlm = _vlm([httpx2.Response(200, json=_message('```json\n{"rectilinear": true}\n```'))], seen)

    assert vlm.ask_json("¿Rectilínea?", [img], '{"rectilinear": bool}') == {"rectilinear": True}

    body = seen[0]["body"]
    assert seen[0]["url"].startswith("https://api.anthropic.com/v1/messages")
    assert body["model"] == "claude-sonnet-5-5"
    blocks = body["messages"][0]["content"]
    assert blocks[0]["type"] == "image" and blocks[0]["source"]["media_type"] == "image/png"
    assert '{"rectilinear": bool}' in blocks[1]["text"]
    assert vlm.total_cost_usd == pytest.approx(token_cost_usd(1000, 200)) and len(vlm.calls) == 1


def test_vlm_retries_on_server_error_and_bad_json() -> None:
    seen: list[dict] = []
    vlm = _vlm(
        [
            httpx2.Response(
                529, json={"type": "error", "error": {"type": "overloaded_error", "message": "x"}}
            ),
            httpx2.Response(200, json=_message("no es json")),
            httpx2.Response(200, json=_message('{"ok": 1}')),
        ],
        seen,
    )
    assert vlm.ask_json("p", [], "{}") == {"ok": 1}
    assert len(seen) == 3 and len(vlm.calls) == 2


def test_vlm_gives_up_and_does_not_retry_client_errors() -> None:
    vlm = _vlm([httpx2.Response(200, json=_message("nada"))] * 3, [])
    with pytest.raises(VLMError):
        vlm.ask_json("p", [], "{}")
    bad = _vlm(
        [
            httpx2.Response(
                400,
                json={"type": "error", "error": {"type": "invalid_request_error", "message": "x"}},
            )
        ],
        [],
    )
    with pytest.raises(anthropic.BadRequestError):
        bad.ask_json("p", [], "{}")


# --- cli ------------------------------------------------------------------------------------


def test_cli_run_with_fake_variant(tmp_path: Path) -> None:
    csv_path = write_csv(tmp_path / "s.csv", [piece_row(), piece_row(id="p02")])
    runs = tmp_path / "runs"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--variants",
            "FAKE",
            "--pieces",
            "p02",
            "--candidates",
            "2",
            "--run-id",
            "t1",
            "--sample",
            str(csv_path),
            "--runs-root",
            str(runs),
        ],
    )
    assert result.exit_code == 0, result.output
    run_meta = storage.read_meta(runs / "t1")
    assert run_meta["pieces"] == ["p02"] and run_meta["variants"] == ["FAKE"]
    assert run_meta["errors"] == [] and len(run_meta["results"][0]["candidates"]) == 2
    cand_meta = storage.read_meta(runs / "t1/p02/FAKE/cand_2")
    assert cand_meta["piece_id"] == "p02" and cand_meta["index"] == 2
    assert os.path.exists(cand_meta["glb_path"])


def test_cli_eval_without_eval_module(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "harness.eval", None)  # simulate Task 6 not merged yet
    result = CliRunner().invoke(app, ["eval", "--run-id", "t1"])
    assert result.exit_code == 1 and "harness.eval" in result.output
