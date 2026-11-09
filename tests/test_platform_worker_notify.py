"""Optional worker → web notice when a piece reaches ``review`` (``NOTIFY_URL`` + secret)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from platform_worker import pipeline

PIECE_ID = "33333333-3333-3333-3333-333333333333"
URL = "http://localhost:3000/api/internal/notify"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in ("NOTIFY_URL", "WORKER_SHARED_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WORKER_ENV_FILE", str(tmp_path / "no-such-worker.env"))


def test_without_settings_nothing_is_sent(httpx_mock: HTTPXMock) -> None:
    assert pipeline.notify_status(PIECE_ID, "review") is False
    assert pipeline.notify_status(PIECE_ID, "review", settings={"NOTIFY_URL": URL}) is False
    assert httpx_mock.get_requests() == []


def test_posts_piece_and_status_with_the_secret(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, method="POST", json={"ok": True, "sent": False})
    settings = {"NOTIFY_URL": URL, "WORKER_SHARED_SECRET": "s3cret"}
    assert pipeline.notify_status(PIECE_ID, "review", settings=settings) is True
    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["authorization"] == "Bearer s3cret"
    assert json.loads(request.content) == {"pieceId": PIECE_ID, "status": "review"}


def test_reads_the_environment(httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFY_URL", URL)
    monkeypatch.setenv("WORKER_SHARED_SECRET", "from-env")
    httpx_mock.add_response(url=URL, method="POST", json={"ok": True})
    assert pipeline.notify_status(PIECE_ID, "review") is True
    assert httpx_mock.get_request().headers["authorization"] == "Bearer from-env"


@pytest.mark.parametrize("failure", ["status", "network"])
def test_a_failed_notice_never_raises(httpx_mock: HTTPXMock, failure: str) -> None:
    if failure == "status":
        httpx_mock.add_response(url=URL, method="POST", status_code=401)
    else:
        httpx_mock.add_exception(httpx.ConnectError("refused"))
    settings = {"NOTIFY_URL": URL, "WORKER_SHARED_SECRET": "s3cret"}
    assert pipeline.notify_status(PIECE_ID, "review", settings=settings) is False
