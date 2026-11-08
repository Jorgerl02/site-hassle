from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pytest_httpx import HTTPXMock

from harness.clients import meshy
from harness.clients.meshy import GenerationOutcome, MeshyClient, MeshyError
from harness.core import storage
from harness.core.config import Settings
from harness.core.pricing import MESHY_USD_PER_MODEL
from harness.prep import clean
from harness.variants.d_clean_meshy import CleanMeshyVariant

FIX = Path(__file__).parent / "fixtures" / "meshy"
BASE = "https://api.meshy.ai/openapi/v1"
TASK_ID = "018a210d-8ba4-705c-b111-1f1776f7f578"
GLB_URL = json.loads((FIX / "task_succeeded.json").read_text())["model_urls"]["glb"]
GLB_BYTES = b"glTF-fake-binary"


def fixture(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(meshy.time, "sleep", lambda _s: None)


@pytest.fixture
def images(tmp_path: Path) -> list[Path]:
    paths = []
    for i in range(1, 4):
        path = tmp_path / f"{i}.jpg"
        img = Image.new("RGB", (64, 64), (255, 255, 255))
        img.paste((120, 80, 40), (16, 16, 48, 48))
        img.save(path)
        paths.append(path)
    return paths


def client(**kwargs) -> MeshyClient:
    return MeshyClient("test-key", poll_interval_s=0.0, **kwargs)


def mock_cycle(httpx_mock: HTTPXMock, endpoint: str, *, reusable: bool = False) -> None:
    httpx_mock.add_response(
        method="POST", url=f"{BASE}/{endpoint}", json=fixture("create"), is_reusable=reusable
    )
    if not reusable:
        httpx_mock.add_response(
            method="GET", url=f"{BASE}/{endpoint}/{TASK_ID}", json=fixture("task_in_progress")
        )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/{endpoint}/{TASK_ID}",
        json=fixture("task_succeeded"),
        is_reusable=reusable,
    )
    httpx_mock.add_response(method="GET", url=GLB_URL, content=GLB_BYTES, is_reusable=reusable)


def test_single_image_happy_path(httpx_mock: HTTPXMock, images, tmp_path):
    mock_cycle(httpx_mock, "image-to-3d")
    dst = tmp_path / "out" / "model.glb"

    outcome = client().generate(images[:1], dst)

    assert isinstance(outcome, GenerationOutcome)
    assert outcome.glb_path == dst and dst.read_bytes() == GLB_BYTES
    assert outcome.cost_usd == MESHY_USD_PER_MODEL
    assert outcome.seconds >= 0.0
    assert outcome.meta["task_id"] == TASK_ID
    assert outcome.meta["endpoint"] == "image-to-3d"
    assert outcome.meta["multi_image"] is False
    assert outcome.meta["consumed_credits"] == 30
    assert outcome.meta["polls"] == 2
    assert outcome.meta["create_attempts"] == 1
    assert outcome.meta["final_status"]["status"] == "SUCCEEDED"

    create = httpx_mock.get_requests(method="POST")[0]
    assert create.headers["Authorization"] == "Bearer test-key"
    body = json.loads(create.content)
    assert body["image_url"].startswith("data:image/jpeg;base64,")
    assert body["should_texture"] is True and body["target_formats"] == ["glb"]
    assert "seed" not in body
    download = httpx_mock.get_requests(url=GLB_URL)[0]
    assert "Authorization" not in download.headers


def test_multi_image_uses_multi_endpoint(httpx_mock: HTTPXMock, images, tmp_path):
    mock_cycle(httpx_mock, "multi-image-to-3d")
    outcome = client().generate(images, tmp_path / "m.glb", seed=7)

    body = json.loads(httpx_mock.get_requests(method="POST")[0].content)
    assert len(body["image_urls"]) == 3 and "image_url" not in body
    assert outcome.meta["multi_image"] is True
    assert outcome.meta["seed_requested"] == 7 and outcome.meta["seed_supported"] is False


def test_multi_image_caps_at_four(httpx_mock: HTTPXMock, images, tmp_path):
    mock_cycle(httpx_mock, "multi-image-to-3d")
    many = images + images  # 6 images
    outcome = client().generate(many, tmp_path / "m.glb")

    body = json.loads(httpx_mock.get_requests(method="POST")[0].content)
    assert len(body["image_urls"]) == 4
    assert len(outcome.meta["images_dropped"]) == 2


def test_task_failure_raises_with_payload(httpx_mock: HTTPXMock, images, tmp_path):
    httpx_mock.add_response(method="POST", url=f"{BASE}/image-to-3d", json=fixture("create"))
    httpx_mock.add_response(
        method="GET", url=f"{BASE}/image-to-3d/{TASK_ID}", json=fixture("task_failed")
    )
    with pytest.raises(MeshyError, match="too complex") as exc:
        client().generate(images[:1], tmp_path / "x.glb")
    assert exc.value.payload["status"] == "FAILED"
    assert not (tmp_path / "x.glb").exists()


def test_timeout_raises_with_last_status(httpx_mock: HTTPXMock, images, tmp_path):
    httpx_mock.add_response(method="POST", url=f"{BASE}/image-to-3d", json=fixture("create"))
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/image-to-3d/{TASK_ID}",
        json=fixture("task_in_progress"),
        is_reusable=True,
    )
    with pytest.raises(MeshyError, match="Timeout") as exc:
        client(timeout_s=0.0).generate(images[:1], tmp_path / "x.glb")
    assert exc.value.payload["status"] == "IN_PROGRESS"


def test_create_post_5xx_is_not_retried(httpx_mock: HTTPXMock, images, tmp_path):
    httpx_mock.add_response(
        method="POST", url=f"{BASE}/image-to-3d", status_code=502, json={"message": "bad gw"}
    )
    with pytest.raises(MeshyError, match="502") as exc:
        client().generate(images[:1], tmp_path / "x.glb")
    assert exc.value.payload == {"message": "bad gw"}
    assert len(httpx_mock.get_requests(method="POST")) == 1


def test_create_post_read_timeout_is_not_retried(httpx_mock: HTTPXMock, images, tmp_path):
    httpx_mock.add_exception(httpx.ReadTimeout("lost"), method="POST", url=f"{BASE}/image-to-3d")
    with pytest.raises(MeshyError, match="no idempotente"):
        client().generate(images[:1], tmp_path / "x.glb")
    assert len(httpx_mock.get_requests(method="POST")) == 1


def test_create_post_429_is_retried(httpx_mock: HTTPXMock, images, tmp_path):
    httpx_mock.add_response(method="POST", url=f"{BASE}/image-to-3d", status_code=429)
    mock_cycle(httpx_mock, "image-to-3d")
    outcome = client().generate(images[:1], tmp_path / "r.glb")
    assert outcome.meta["create_attempts"] == 2
    assert len(httpx_mock.get_requests(method="POST")) == 2


def test_create_post_connect_error_is_retried(httpx_mock: HTTPXMock, images, tmp_path):
    httpx_mock.add_exception(
        httpx.ConnectError("refused"), method="POST", url=f"{BASE}/image-to-3d"
    )
    httpx_mock.add_exception(
        httpx.ConnectTimeout("slow dns"), method="POST", url=f"{BASE}/image-to-3d"
    )
    mock_cycle(httpx_mock, "image-to-3d")
    outcome = client().generate(images[:1], tmp_path / "r.glb")
    assert outcome.meta["create_attempts"] == 3
    assert len(httpx_mock.get_requests(method="POST")) == 3


def test_create_post_429_gives_up_after_three_retries(httpx_mock: HTTPXMock, images, tmp_path):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/image-to-3d",
        status_code=429,
        json={"message": "NoMorePendingTasks"},
        is_reusable=True,
    )
    with pytest.raises(MeshyError, match="429") as exc:
        client().generate(images[:1], tmp_path / "x.glb")
    assert exc.value.payload == {"message": "NoMorePendingTasks"}
    assert len(httpx_mock.get_requests(method="POST")) == 4


def test_idempotent_gets_retry_transient_errors(httpx_mock: HTTPXMock, images, tmp_path):
    poll_url = f"{BASE}/image-to-3d/{TASK_ID}"
    httpx_mock.add_response(method="POST", url=f"{BASE}/image-to-3d", json=fixture("create"))
    httpx_mock.add_response(method="GET", url=poll_url, status_code=502)
    httpx_mock.add_exception(httpx.ReadTimeout("slow"), method="GET", url=poll_url)
    httpx_mock.add_response(method="GET", url=poll_url, status_code=408)
    httpx_mock.add_response(method="GET", url=poll_url, json=fixture("task_succeeded"))
    httpx_mock.add_exception(httpx.ReadTimeout("slow"), method="GET", url=GLB_URL)
    httpx_mock.add_response(method="GET", url=GLB_URL, status_code=503)
    httpx_mock.add_response(method="GET", url=GLB_URL, content=GLB_BYTES)

    outcome = client().generate(images[:1], tmp_path / "r.glb")
    assert outcome.glb_path.read_bytes() == GLB_BYTES
    assert outcome.meta["create_attempts"] == 1
    assert len(httpx_mock.get_requests(method="GET", url=poll_url)) == 4


def test_client_error_is_not_retried(httpx_mock: HTTPXMock, images, tmp_path):
    httpx_mock.add_response(
        method="POST", url=f"{BASE}/image-to-3d", status_code=400, json={"message": "bad"}
    )
    with pytest.raises(MeshyError, match="400"):
        client().generate(images[:1], tmp_path / "x.glb")
    assert len(httpx_mock.get_requests(method="POST")) == 1


def test_variant_d_cleans_and_produces_candidates(
    httpx_mock: HTTPXMock, monkeypatch, images, piece, tmp_path
):
    calls: list[tuple[int, int]] = []

    def fake_remove(img: Image.Image) -> Image.Image:
        calls.append(img.size)
        rgba = img.convert("RGBA")
        alpha = Image.new("L", img.size, 0)
        alpha.paste(255, (16, 16, 48, 48))
        rgba.putalpha(alpha)
        return rgba

    monkeypatch.setattr(clean, "_remove_background", fake_remove)
    mock_cycle(httpx_mock, "multi-image-to-3d", reusable=True)
    piece = piece.model_copy(update={"images": images[:2]})
    workdir = storage.variant_dir("run1", piece.id, "D", root=tmp_path / "runs")

    variant = CleanMeshyVariant(client=client())
    result = variant.run(piece, workdir, candidates=3)

    assert variant.name == "D"
    assert len(calls) == 2  # every photo cleaned once
    assert result.variant == "D" and result.piece_id == piece.id
    assert [c.index for c in result.candidates] == [1, 2, 3]
    assert len(httpx_mock.get_requests(method="POST")) == 3
    for cand in result.candidates:
        assert cand.glb_path == workdir / f"cand_{cand.index}" / "model.glb"
        assert cand.glb_path.read_bytes() == GLB_BYTES
        assert cand.cost_usd == MESHY_USD_PER_MODEL
        meta = storage.read_meta(cand.glb_path.parent)
        assert meta["variant"] == "D" and meta["index"] == cand.index
        assert meta["task_id"] == TASK_ID and meta["seed_supported"] is False
        assert len(meta["clean_images"]) == 2
    body = json.loads(httpx_mock.get_requests(method="POST")[0].content)
    assert all(u.startswith("data:image/png;base64,") for u in body["image_urls"])
    assert "semilla" in result.notes


def test_variant_d_without_key_fails_at_run(piece, tmp_path):
    variant = CleanMeshyVariant(settings=Settings())
    with pytest.raises(RuntimeError, match="MESHY_API_KEY"):
        _ = variant.client
