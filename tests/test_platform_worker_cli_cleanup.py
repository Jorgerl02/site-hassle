"""Workdir cleanup of the platform worker CLI (tmp dirs, no network)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from platform_worker import cli


def _fake_process(status: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(db, storage, row, *, provider, workdir, blender_bin):  # noqa: ANN001
        (
            cli.piece_workdir(workdir, str(row["id"]), int(row.get("attempt") or 1)) / "f.glb"
        ).write_text("x")
        return status

    monkeypatch.setattr(cli, "process_piece", fake)


def _ctx(**extra: Any) -> dict[str, Any]:
    return {"db": None, "storage": None, "provider": None, "blender_bin": None, **extra}


@pytest.mark.parametrize("status", ["ready", "review", "superseded"])
def test_workdir_deleted_on_final_status(
    status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_process(status, monkeypatch)
    cli._process(_ctx(), {"id": "p1", "attempt": 2}, tmp_path)
    assert not (tmp_path / "p1" / "2").exists()
    assert not (tmp_path / "p1").exists()


@pytest.mark.parametrize("status", ["failed", "needs_photos"])
def test_workdir_kept_on_failure(
    status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_process(status, monkeypatch)
    cli._process(_ctx(), {"id": "p1", "attempt": 1}, tmp_path)
    assert (tmp_path / "p1" / "1" / "f.glb").exists()


def test_keep_workdirs_disables_deletion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_process("review", monkeypatch)
    cli._process(_ctx(keep_workdirs=True), {"id": "p1", "attempt": 1}, tmp_path)
    assert (tmp_path / "p1" / "1" / "f.glb").exists()


def test_cleanup_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_process("review", monkeypatch)

    def boom(*a: Any, **k: Any) -> None:
        raise OSError("nope")

    monkeypatch.setattr(cli.shutil, "rmtree", boom)
    assert cli._process(_ctx(), {"id": "p1", "attempt": 1}, tmp_path) == "review"


def test_sweep_deletes_only_old_workdirs(tmp_path: Path) -> None:
    old = tmp_path / "p1" / "1"
    new = tmp_path / "p2" / "1"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "a").write_text("x")
    past = time.time() - 4 * 86400
    os.utime(old, (past, past))
    cli._sweep_old_workdirs(tmp_path)
    assert not old.exists()
    assert not (tmp_path / "p1").exists()
    assert new.exists()


def test_sweep_missing_root_is_silent(tmp_path: Path) -> None:
    cli._sweep_old_workdirs(tmp_path / "nope")
