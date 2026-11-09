from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image
from pytest_httpx import HTTPXMock

from harness.clients.tripo import DEFAULT_BASE_URL, ENV_VARS, TripoClient, TripoSettings
from platform_worker.providers import Provider
from platform_worker.providers.tripo import TripoProvider

TASK_ID = "1ec04ced-4b87-44f6-a296-beee80777941"
GLB_URL = "https://tripo-data.example.com/out/model_pbr.glb"
FIXTURES = Path(__file__).parent / "fixtures" / "tripo"


@pytest.fixture(autouse=True)
def _no_tripo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_provider_uses_pietra_defaults() -> None:
    provider = TripoProvider("tsk_test")
    assert isinstance(provider, Provider)
    assert provider.settings == TripoSettings()


def test_provider_reads_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRIPO_FACE_LIMIT", "30000")
    assert TripoProvider("tsk_test").settings.face_limit == 30000


def test_provider_env_mapping_and_explicit_settings() -> None:
    from_env = TripoProvider("tsk_test", env={"TRIPO_TEXTURE_QUALITY": "standard"})
    assert from_env.settings.texture_quality == "standard"
    explicit = TripoSettings(face_limit=50000)
    assert (
        TripoProvider("tsk_test", settings=explicit, env={"TRIPO_FACE_LIMIT": "1"}).settings
        is explicit
    )


def test_provider_sends_first_photo_with_settings(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(method="POST", url=f"{DEFAULT_BASE_URL}/files", json=fixture("upload"))
    httpx_mock.add_response(
        method="POST",
        url=f"{DEFAULT_BASE_URL}/generation/image-to-model",
        json=fixture("create_task"),
    )
    httpx_mock.add_response(
        method="GET", url=f"{DEFAULT_BASE_URL}/tasks/{TASK_ID}", json=fixture("task_success")
    )
    httpx_mock.add_response(method="GET", url=GLB_URL, content=b"glTF-fake")
    photos = []
    for k in range(3):
        photos.append(tmp_path / f"{k}.jpg")
        Image.new("RGB", (16, 16), (k * 50, 0, 0)).save(photos[-1])
    client = TripoClient("tsk_test", settings=TripoSettings(face_limit=50000), sleep=lambda s: None)

    outcome = TripoProvider("tsk_test", client=client).generate(
        photos, tmp_path / "out.glb", seed=5
    )

    assert len(httpx_mock.get_requests(url=f"{DEFAULT_BASE_URL}/files")) == 1
    [create] = httpx_mock.get_requests(url=f"{DEFAULT_BASE_URL}/generation/image-to-model")
    body = json.loads(create.content)
    assert body["input"] == fixture("upload")["data"]["file_token"]
    assert body["face_limit"] == 50000 and body["geometry_quality"] == "detailed"
    assert body["model_seed"] == 5
    assert outcome.cost_usd == pytest.approx(0.60)
    assert outcome.meta["images"] == [str(photos[0])]
    assert (tmp_path / "out.glb").read_bytes() == b"glTF-fake"
