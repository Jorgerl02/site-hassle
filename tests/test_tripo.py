from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pytest_httpx import HTTPXMock

from harness.clients.tripo import DEFAULT_BASE_URL, TripoClient, TripoError
from harness.core import pricing, storage
from harness.core.config import Settings
from harness.core.models import Piece
from harness.core.variant import Variant
from harness.prep import clean
from harness.variants.a_tripo_direct import TripoDirectVariant
from harness.variants.b_clean_tripo import CleanTripoVariant

FIXTURES = Path(__file__).parent / "fixtures" / "tripo"
TASK_ID = "1ec04ced-4b87-44f6-a296-beee80777941"
UPLOAD_URL = f"{DEFAULT_BASE_URL}/upload/sts"
TASK_URL = f"{DEFAULT_BASE_URL}/task"
POLL_URL = f"{DEFAULT_BASE_URL}/task/{TASK_ID}"
GLB_URL = "https://tripo-data.example.com/out/pbr_model.glb"
GLB_BYTES = b"glTF\x02\x00\x00\x00fake-glb"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def make_client(clock: FakeClock | None = None, **kwargs) -> TripoClient:
    clock = clock or FakeClock()
    kwargs.setdefault("poll_interval_s", 5.0)
    return TripoClient("tsk_test", sleep=clock.sleep, clock=clock, **kwargs)


def write_photo(path: Path, color: tuple[int, int, int] = (150, 90, 40)) -> Path:
    Image.new("RGB", (64, 48), color).save(path)
    return path


def task_requests(httpx_mock: HTTPXMock) -> list[dict]:
    return [json.loads(r.content) for r in httpx_mock.get_requests(method="POST", url=TASK_URL)]


def mock_success_cycle(httpx_mock: HTTPXMock, *, reusable: bool = False) -> None:
    httpx_mock.add_response(
        method="POST", url=UPLOAD_URL, json=fixture("upload"), is_reusable=reusable
    )
    httpx_mock.add_response(
        method="POST", url=TASK_URL, json=fixture("create_task"), is_reusable=reusable
    )
    if not reusable:
        httpx_mock.add_response(method="GET", url=POLL_URL, json=fixture("task_queued"))
        httpx_mock.add_response(method="GET", url=POLL_URL, json=fixture("task_running"))
    httpx_mock.add_response(
        method="GET", url=POLL_URL, json=fixture("task_success"), is_reusable=reusable
    )
    httpx_mock.add_response(method="GET", url=GLB_URL, content=GLB_BYTES, is_reusable=reusable)


# -- client ---------------------------------------------------------------------------


def test_generate_single_image_full_cycle(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    mock_success_cycle(httpx_mock)
    photo = write_photo(tmp_path / "1.jpg")
    dst = tmp_path / "out" / "model.glb"

    outcome = make_client().generate([photo], dst, seed=7)

    assert outcome.glb_path == dst
    assert dst.read_bytes() == GLB_BYTES
    [request] = task_requests(httpx_mock)
    assert request["type"] == "image_to_model"
    assert request["file"] == {
        "type": "jpg",
        "file_token": fixture("upload")["data"]["image_token"],
    }
    assert request["model_seed"] == 7 and request["texture_seed"] == 7
    assert request["pbr"] is True and request["texture"] is True
    assert outcome.meta["task_id"] == TASK_ID
    assert [h["status"] for h in outcome.meta["status_history"]] == ["queued", "running", "success"]
    assert outcome.meta["model_url_field"] == "pbr_model"
    assert outcome.meta["create_attempts"] == 1

    upload = httpx_mock.get_request(method="POST", url=UPLOAD_URL)
    assert upload.headers["Authorization"] == "Bearer tsk_test"
    assert b'name="file"' in upload.content
    download = httpx_mock.get_request(method="GET", url=GLB_URL)
    assert "Authorization" not in download.headers


def test_generate_populates_cost_and_seconds(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    mock_success_cycle(httpx_mock)
    clock = FakeClock()
    outcome = make_client(clock).generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert outcome.cost_usd == pricing.TRIPO_USD_PER_MODEL
    assert outcome.seconds == pytest.approx(10.0)  # two polls x 5 s
    assert outcome.meta["consumed_credit"] == 30
    assert outcome.meta["consumed_credit_usd"] == pytest.approx(0.30)
    assert outcome.meta["timings"]["total_s"] == pytest.approx(10.0)
    assert outcome.meta["seed"] is None
    assert "model_seed" not in outcome.meta["request"]


def test_generate_multiview_pads_to_four_slots(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        method="POST", url=UPLOAD_URL, json={"code": 0, "data": {"image_token": "tok-front"}}
    )
    httpx_mock.add_response(
        method="POST", url=UPLOAD_URL, json={"code": 0, "data": {"image_token": "tok-left"}}
    )
    httpx_mock.add_response(method="POST", url=TASK_URL, json=fixture("create_task"))
    httpx_mock.add_response(method="GET", url=POLL_URL, json=fixture("task_success"))
    httpx_mock.add_response(method="GET", url=GLB_URL, content=GLB_BYTES)
    photos = [write_photo(tmp_path / "a.png"), write_photo(tmp_path / "b.jpg")]

    outcome = make_client().generate(photos, tmp_path / "m.glb", seed=3)

    [request] = task_requests(httpx_mock)
    assert request["type"] == "multiview_to_model"
    assert request["files"] == [
        {"type": "png", "file_token": "tok-front"},
        {"type": "jpg", "file_token": "tok-left"},
        {},
        {},
    ]
    assert "file" not in request
    assert outcome.meta["task_type"] == "multiview_to_model"
    assert (tmp_path / "m.glb").read_bytes() == GLB_BYTES


def test_task_failure_raises_with_payload(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(method="POST", url=UPLOAD_URL, json=fixture("upload"))
    httpx_mock.add_response(method="POST", url=TASK_URL, json=fixture("create_task"))
    httpx_mock.add_response(method="GET", url=POLL_URL, json=fixture("task_running"))
    httpx_mock.add_response(method="GET", url=POLL_URL, json=fixture("task_failed"))
    dst = tmp_path / "m.glb"

    with pytest.raises(TripoError, match="failed") as info:
        make_client().generate([write_photo(tmp_path / "1.jpg")], dst)

    assert info.value.payload["status"] == "failed"
    assert info.value.payload["error_msg"] == "generation failed"
    assert not dst.exists()


def test_timeout_raises_with_last_status(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(method="POST", url=UPLOAD_URL, json=fixture("upload"))
    httpx_mock.add_response(method="POST", url=TASK_URL, json=fixture("create_task"))
    httpx_mock.add_response(
        method="GET", url=POLL_URL, json=fixture("task_running"), is_reusable=True
    )
    client = make_client(timeout_s=30.0, poll_interval_s=10.0)

    with pytest.raises(TripoError, match="Tiempo agotado") as info:
        client.generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert info.value.payload["status"] == "running"
    assert (
        len(httpx_mock.get_requests(method="GET", url=POLL_URL)) == 4
    )  # t = 0, 10, 20, 30 (deadline)


def test_transient_http_errors_are_retried(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(method="POST", url=UPLOAD_URL, status_code=503)
    httpx_mock.add_response(
        method="POST", url=UPLOAD_URL, status_code=429, json={"code": 2000, "message": "rate limit"}
    )
    mock_success_cycle(httpx_mock)
    clock = FakeClock()

    outcome = make_client(clock, backoff_s=1.0).generate(
        [write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb"
    )

    assert outcome.glb_path.exists()
    assert len(httpx_mock.get_requests(method="POST", url=UPLOAD_URL)) == 3
    assert clock.now == pytest.approx(1.0 + 2.0 + 10.0)  # backoff 1 + 2, then polls


def test_retries_are_bounded(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(method="POST", url=UPLOAD_URL, status_code=500, is_reusable=True)

    with pytest.raises(TripoError, match="500"):
        make_client().generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert len(httpx_mock.get_requests(method="POST", url=UPLOAD_URL)) == 4  # 1 + 3 retries


def test_non_transient_api_error_is_not_retried(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        method="POST",
        url=UPLOAD_URL,
        status_code=400,
        json={"code": 2004, "message": "unsupported file type"},
    )

    with pytest.raises(TripoError, match="2004") as info:
        make_client().generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert info.value.payload["code"] == 2004


def mock_upload_only(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=UPLOAD_URL, json=fixture("upload"))


def mock_poll_and_download(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="GET", url=POLL_URL, json=fixture("task_success"))
    httpx_mock.add_response(method="GET", url=GLB_URL, content=GLB_BYTES)


def test_create_task_5xx_is_not_retried(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    mock_upload_only(httpx_mock)
    httpx_mock.add_response(method="POST", url=TASK_URL, status_code=503)

    with pytest.raises(TripoError, match="503"):
        make_client().generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert len(httpx_mock.get_requests(method="POST", url=TASK_URL)) == 1


def test_create_task_read_timeout_is_not_retried(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    mock_upload_only(httpx_mock)
    httpx_mock.add_exception(httpx.ReadTimeout("lost response"), method="POST", url=TASK_URL)

    with pytest.raises(TripoError, match="ReadTimeout"):
        make_client().generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert len(httpx_mock.get_requests(method="POST", url=TASK_URL)) == 1


def test_create_task_429_is_retried(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    mock_upload_only(httpx_mock)
    httpx_mock.add_response(
        method="POST", url=TASK_URL, status_code=429, json={"code": 2000, "message": "limit"}
    )
    httpx_mock.add_response(method="POST", url=TASK_URL, json=fixture("create_task"))
    mock_poll_and_download(httpx_mock)

    outcome = make_client().generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert len(httpx_mock.get_requests(method="POST", url=TASK_URL)) == 2
    assert outcome.meta["create_attempts"] == 2


def test_create_task_connect_error_is_retried(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    mock_upload_only(httpx_mock)
    httpx_mock.add_exception(httpx.ConnectError("refused"), method="POST", url=TASK_URL)
    httpx_mock.add_response(method="POST", url=TASK_URL, json=fixture("create_task"))
    mock_poll_and_download(httpx_mock)

    outcome = make_client().generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert outcome.meta["create_attempts"] == 2
    assert outcome.glb_path.read_bytes() == GLB_BYTES


def test_poll_5xx_is_still_retried(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    mock_upload_only(httpx_mock)
    httpx_mock.add_response(method="POST", url=TASK_URL, json=fixture("create_task"))
    httpx_mock.add_response(method="GET", url=POLL_URL, status_code=502)
    mock_poll_and_download(httpx_mock)

    outcome = make_client().generate([write_photo(tmp_path / "1.jpg")], tmp_path / "m.glb")

    assert len(httpx_mock.get_requests(method="GET", url=POLL_URL)) == 2
    assert outcome.meta["create_attempts"] == 1
    assert outcome.glb_path.exists()


def test_generate_requires_images(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        make_client().generate([], tmp_path / "m.glb")


# -- variants ----------------------------------------------------------------------------


def make_piece(tmp_path: Path, n_images: int) -> Piece:
    images = [write_photo(tmp_path / f"{k}.jpg", (40 * k, 80, 120)) for k in range(1, n_images + 1)]
    return Piece(
        id="p01",
        name="Mesa",
        store="Tienda",
        source_url="https://example.com/mesa",
        category="macizo_mate",
        images=images,
        width_cm=120,
        height_cm=75,
        depth_cm=60,
    )


def test_variants_satisfy_protocol() -> None:
    client = make_client()
    assert isinstance(TripoDirectVariant(client), Variant)
    assert isinstance(CleanTripoVariant(client), Variant)
    assert TripoDirectVariant(client).name == "A"
    assert CleanTripoVariant(client).name == "B"


def test_variant_without_key_fails_at_run(tmp_path: Path) -> None:
    variant = TripoDirectVariant(settings=Settings())  # construction never needs the key
    with pytest.raises(RuntimeError, match="TRIPO_API_KEY"):
        variant.run(make_piece(tmp_path, 1), tmp_path / "work")


def test_variant_a_candidates_distinct_seeds(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    mock_success_cycle(httpx_mock, reusable=True)
    piece = make_piece(tmp_path, 3)
    workdir = tmp_path / "work"

    result = TripoDirectVariant(make_client(), base_seed=100).run(piece, workdir, candidates=3)

    assert result.variant == "A" and result.piece_id == "p01"
    assert [c.index for c in result.candidates] == [1, 2, 3]
    requests = task_requests(httpx_mock)
    assert [r["model_seed"] for r in requests] == [101, 102, 103]
    assert all(r["type"] == "image_to_model" for r in requests)
    assert len(httpx_mock.get_requests(method="POST", url=UPLOAD_URL)) == 3  # first photo only
    for cand in result.candidates:
        assert cand.glb_path == storage.model_path(workdir / f"cand_{cand.index}")
        assert cand.glb_path.read_bytes() == GLB_BYTES
        assert cand.cost_usd == pricing.TRIPO_USD_PER_MODEL
        meta = storage.read_meta(workdir / f"cand_{cand.index}")
        assert meta["seed"] == 100 + cand.index
        assert meta["task_id"] == TASK_ID
        assert meta["images"] == [str(piece.images[0])]
        assert meta["request"]["model_seed"] == 100 + cand.index
        assert "timings" in meta and meta["cost_usd"] == pricing.TRIPO_USD_PER_MODEL


def test_variant_a_keeps_successful_candidates_on_partial_failure(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    mock_success_cycle(httpx_mock)  # candidate 1 succeeds
    httpx_mock.add_response(method="POST", url=UPLOAD_URL, json=fixture("upload"))
    httpx_mock.add_response(method="POST", url=TASK_URL, json=fixture("create_task"))
    httpx_mock.add_response(method="GET", url=POLL_URL, json=fixture("task_failed"))
    workdir = tmp_path / "work"

    result = TripoDirectVariant(make_client()).run(make_piece(tmp_path, 1), workdir, candidates=2)

    assert [c.index for c in result.candidates] == [1]
    assert "cand_2" in result.notes
    assert storage.read_meta(workdir / "cand_2")["error_payload"]["status"] == "failed"


@pytest.fixture
def fake_rembg(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    calls: list[tuple[int, int]] = []

    def fake(image: Image.Image) -> Image.Image:
        calls.append(image.size)
        rgba = Image.new("RGBA", image.size, (0, 0, 0, 0))
        w, h = image.size
        rgba.paste((200, 100, 50, 255), (w // 4, h // 4, 3 * w // 4, 3 * h // 4))
        return rgba

    monkeypatch.setattr(clean, "_remove_background", fake)
    return calls


def test_variant_b_cleans_and_uses_multiview(
    httpx_mock: HTTPXMock, tmp_path: Path, fake_rembg: list
) -> None:
    mock_success_cycle(httpx_mock, reusable=True)
    piece = make_piece(tmp_path, 2)
    workdir = tmp_path / "work"

    result = CleanTripoVariant(make_client(), base_seed=0).run(piece, workdir, candidates=2)

    assert len(fake_rembg) == 2  # every photo cleaned once, shared by candidates
    cleaned = sorted((workdir / "clean").glob("*.png"))
    assert len(cleaned) == 2
    with Image.open(cleaned[0]) as img:
        assert img.size == (1024, 1024)
    requests = task_requests(httpx_mock)
    assert [r["type"] for r in requests] == ["multiview_to_model"] * 2
    assert [r["model_seed"] for r in requests] == [1, 2]
    assert all(sum(1 for f in r["files"] if f) == 2 for r in requests)
    uploads = httpx_mock.get_requests(method="POST", url=UPLOAD_URL)
    assert len(uploads) == 4 and all(b"image/png" in u.content for u in uploads)
    for cand in result.candidates:
        assert cand.glb_path.read_bytes() == GLB_BYTES
        meta = storage.read_meta(workdir / f"cand_{cand.index}")
        assert meta["variant"] == "B"
        assert meta["clean_images"] == [str(p) for p in cleaned]
        assert meta["task_type"] == "multiview_to_model"


def test_variant_b_single_photo_uses_image_to_model(
    httpx_mock: HTTPXMock, tmp_path: Path, fake_rembg: list
) -> None:
    mock_success_cycle(httpx_mock)

    result = CleanTripoVariant(make_client()).run(
        make_piece(tmp_path, 1), tmp_path / "w", candidates=1
    )

    assert len(fake_rembg) == 1
    [request] = task_requests(httpx_mock)
    assert request["type"] == "image_to_model"
    assert request["file"]["type"] == "png"
    assert len(result.candidates) == 1
