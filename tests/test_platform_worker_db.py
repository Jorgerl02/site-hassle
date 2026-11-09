"""WorkerDB / Storage / FalProvider HTTP contracts (PostgREST, Storage, fal.ai queue)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from platform_worker.db import WorkerDB, WorkerDBError
from platform_worker.providers.fal import HUNYUAN3D_V3, TRELLIS, FalProvider
from platform_worker.storage import Storage

URL = "https://proj.supabase.co"
KEY = "service-key"
AUTH = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
WORKER_ENV_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "PROVIDER",
    "FAL_KEY",
    "FAL_MODEL",
    "TRIPO_API_KEY",
    "BLENDER_BIN",
    "WORKER_ENV_FILE",
)


@pytest.fixture(autouse=True)
def _isolated_worker_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Never read the repo's real ``.env`` nor worker keys from the shell."""
    for key in WORKER_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WORKER_ENV_FILE", str(tmp_path / "no-such-worker.env"))


PIECE = {"id": "p-1", "status": "generating", "attempt": 1, "kind": "cabecero"}


@pytest.fixture
def db() -> WorkerDB:
    return WorkerDB(URL, KEY)


def test_claim_next_returns_the_claimed_row(httpx_mock: HTTPXMock, db: WorkerDB) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{URL}/rest/v1/rpc/claim_next_piece",
        match_headers=AUTH,
        match_json={},
        json=PIECE,
    )
    assert db.claim_next() == PIECE


@pytest.mark.parametrize("body", [None, [], {"id": None, "status": None}])
def test_claim_next_empty_queue(httpx_mock: HTTPXMock, db: WorkerDB, body) -> None:
    httpx_mock.add_response(method="POST", url=f"{URL}/rest/v1/rpc/claim_next_piece", json=body)
    assert db.claim_next() is None


def test_requeue_stale_sends_minutes(httpx_mock: HTTPXMock, db: WorkerDB) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{URL}/rest/v1/rpc/requeue_stale_pieces",
        match_headers=AUTH,
        match_json={"p_minutes": 30},
        json=2,
    )
    assert db.requeue_stale() == 2


def test_provider_spend_today(httpx_mock: HTTPXMock, db: WorkerDB) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{URL}/rest/v1/rpc/provider_spend_today",
        match_headers=AUTH,
        match_json={},
        json=12.5,
    )
    assert db.provider_spend_today() == 12.5


def test_update_piece_patches_by_id(httpx_mock: HTTPXMock, db: WorkerDB) -> None:

    httpx_mock.add_response(
        method="PATCH",
        url=f"{URL}/rest/v1/pieces?id=eq.p-1",
        match_headers={**AUTH, "Prefer": "return=representation"},
        match_json={"status": "review", "error": None},
        json=[{**PIECE, "status": "review"}],
    )
    assert db.update_piece("p-1", status="review", error=None)["status"] == "review"


def test_update_piece_if_is_a_compare_and_swap(httpx_mock: HTTPXMock, db: WorkerDB) -> None:
    url = f"{URL}/rest/v1/pieces?id=eq.p-1&status=eq.generating&attempt=eq.2"
    httpx_mock.add_response(
        method="PATCH",
        url=url,
        match_headers={**AUTH, "Prefer": "return=representation"},
        match_json={"status": "ready"},
        json=[{**PIECE, "status": "ready"}],
    )
    httpx_mock.add_response(method="PATCH", url=url, json=[])  # someone moved it meanwhile
    expected = {"status": "generating", "attempt": 2}
    assert db.update_piece_if("p-1", expected, status="ready") is True
    assert db.update_piece_if("p-1", expected, status="ready") is False


def test_insert_model_returns_the_row(httpx_mock: HTTPXMock, db: WorkerDB) -> None:
    row = {"piece_id": "p-1", "attempt": 1, "candidate": 1, "selected": True}
    httpx_mock.add_response(
        method="POST",
        url=f"{URL}/rest/v1/piece_models",
        match_headers={**AUTH, "Prefer": "return=representation"},
        match_json=row,
        json=[{"id": "m-1", **row}],
    )
    assert db.insert_model(row)["id"] == "m-1"


def test_list_photos_ordered_by_position(httpx_mock: HTTPXMock, db: WorkerDB) -> None:
    rows = [{"piece_id": "p-1", "storage_path": "u/p-1/1.jpg", "position": 1}]
    httpx_mock.add_response(
        method="GET",
        url=f"{URL}/rest/v1/piece_photos?piece_id=eq.p-1&select=*&order=position.asc",
        match_headers=AUTH,
        json=rows,
    )
    assert db.list_photos("p-1") == rows


def test_postgrest_error_is_reported_in_spanish(httpx_mock: HTTPXMock, db: WorkerDB) -> None:
    httpx_mock.add_response(
        method="POST", url=f"{URL}/rest/v1/rpc/claim_next_piece", status_code=404, text="nope"
    )
    with pytest.raises(WorkerDBError, match="Supabase respondió 404"):
        db.claim_next()


def test_storage_upload_upserts_with_content_type(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    src = tmp_path / "model_web.glb"
    src.write_bytes(b"glTF")
    httpx_mock.add_response(
        method="POST",
        url=f"{URL}/storage/v1/object/models/p-1/1/model_web.glb",
        match_headers={**AUTH, "x-upsert": "true", "Content-Type": "model/gltf-binary"},
        match_content=b"glTF",
        json={"Key": "models/p-1/1/model_web.glb"},
    )
    assert Storage(URL, KEY).upload("models", "p-1/1/model_web.glb", src) == "p-1/1/model_web.glb"


def test_storage_download_writes_file(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{URL}/storage/v1/object/photos/u/p-1/1.jpg",
        match_headers=AUTH,
        content=b"jpeg-bytes",
    )
    dst = Storage(URL, KEY).download("photos", "u/p-1/1.jpg", tmp_path / "x" / "1.jpg")
    assert dst.read_bytes() == b"jpeg-bytes"


@pytest.mark.parametrize(
    ("model", "endpoint", "output", "image_key"),
    [
        ("trellis", TRELLIS, {"model_mesh": {"url": "https://cdn.fal/m.glb"}}, "image_url"),
        (
            "hunyuan3d",
            HUNYUAN3D_V3,
            {"model_glb": {"url": "https://cdn.fal/m.glb"}},
            "input_image_url",
        ),
    ],
)
def test_fal_queue_flow(
    httpx_mock: HTTPXMock, tmp_path: Path, model, endpoint, output, image_key
) -> None:
    image = tmp_path / "1.png"
    image.write_bytes(b"\x89PNG")
    fal_auth = {"Authorization": "Key fal-key"}
    status_url = f"https://queue.fal.run/{endpoint}/requests/r1/status"
    response_url = f"https://queue.fal.run/{endpoint}/requests/r1"

    def check_submit(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        assert body[image_key].startswith("data:image/png;base64,")
        return httpx.Response(
            200,
            json={"request_id": "r1", "status_url": status_url, "response_url": response_url},
        )

    httpx_mock.add_callback(
        check_submit, method="POST", url=f"https://queue.fal.run/{endpoint}", match_headers=fal_auth
    )
    httpx_mock.add_response(method="GET", url=status_url, json={"status": "IN_QUEUE"})
    httpx_mock.add_response(method="GET", url=status_url, json={"status": "COMPLETED"})
    httpx_mock.add_response(method="GET", url=response_url, match_headers=fal_auth, json=output)
    httpx_mock.add_response(method="GET", url="https://cdn.fal/m.glb", content=b"glTF-bytes")

    provider = FalProvider("fal-key", model=model, sleep=lambda _s: None)
    outcome = provider.generate([image], tmp_path / "out" / "model.glb", seed=1)
    assert outcome.glb_path.read_bytes() == b"glTF-bytes"
    assert outcome.cost_usd > 0
    assert outcome.meta["status_history"] == ["IN_QUEUE", "COMPLETED"]
