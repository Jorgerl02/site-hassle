"""Configurable scale tolerance: ``.env`` → Settings → geometry, post and judge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.core import config
from harness.core.config import Settings, resolve_scale_tolerance
from harness.core.models import SCALE_TOLERANCE, GeometryMetrics
from harness.eval.judge import escala_from_error, escala_thresholds, judge_candidate
from harness.post.blender_post import parse_post_meta


@pytest.fixture(autouse=True)
def _no_tolerance_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCALE_TOLERANCE", raising=False)


def _env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, line: str) -> None:
    env = tmp_path / ".env"
    env.write_text(line + "\n", encoding="utf-8")
    monkeypatch.setattr(config, "DEFAULT_ENV_FILE", env)


def _metrics(err: float) -> GeometryMetrics:
    return GeometryMetrics(
        width_cm=100, height_cm=75, depth_cm=60,
        err_width=0.0, err_height=err, err_depth=0.0,
        watertight=True, n_components=1, n_faces=12,
    )  # fmt: skip


def _post_meta(tmp_path: Path, height_err: float) -> Path:
    meta = tmp_path / "post_meta.json"
    meta.write_text(
        json.dumps(
            {
                "errors": {"width": 0.0, "height": height_err, "depth": 0.0},
                "tris_before": 10,
                "tris_after": 10,
            }
        )
    )
    return meta


# ---------- Settings ----------


def test_default_tolerance_is_three_percent() -> None:
    assert SCALE_TOLERANCE == 0.03
    assert Settings.load().scale_tolerance == 0.03
    assert Settings().scale_tolerance == 0.03


def test_tolerance_read_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(tmp_path, monkeypatch, "SCALE_TOLERANCE=0.05")
    assert Settings.load().scale_tolerance == 0.05
    assert resolve_scale_tolerance() == 0.05


def test_environment_wins_over_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(tmp_path, monkeypatch, "SCALE_TOLERANCE=0.05")
    monkeypatch.setenv("SCALE_TOLERANCE", "0,04")  # decimal comma accepted
    assert Settings.load().scale_tolerance == 0.04


@pytest.mark.parametrize("raw", ["abc", "0", "5", "-0.01"])
def test_invalid_tolerance_is_rejected(
    raw: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _env(tmp_path, monkeypatch, f"SCALE_TOLERANCE={raw}")
    with pytest.raises(ValueError, match="SCALE_TOLERANCE"):
        Settings.load()


def test_explicit_tolerance_wins_over_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _env(tmp_path, monkeypatch, "SCALE_TOLERANCE=0.05")
    assert resolve_scale_tolerance(0.02) == 0.02
    with pytest.raises(ValueError):
        resolve_scale_tolerance(1.5)


# ---------- GeometryMetrics ----------


def test_geometry_scale_ok_with_explicit_tolerance() -> None:
    m = _metrics(-0.04)
    assert not m.scale_ok  # default 3 %
    assert m.is_scale_ok(0.05)
    assert not m.is_scale_ok(0.03)
    assert not _metrics(0.05).is_scale_ok(0.05)  # strict: < tolerance


def test_geometry_scale_ok_follows_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(tmp_path, monkeypatch, "SCALE_TOLERANCE=0.05")
    m = _metrics(0.04)
    assert m.scale_ok
    assert "scale_ok" not in m.model_dump()  # still a property, not a stored field


# ---------- PostResult ----------


def test_post_scale_ok_with_tolerance(tmp_path: Path) -> None:
    meta = _post_meta(tmp_path, -0.04)
    result = parse_post_meta(meta, tmp_path / "o.glb")
    assert not result.scale_ok
    assert result.is_scale_ok(0.05)
    assert parse_post_meta(meta, tmp_path / "o.glb", tolerance=0.05).scale_ok


def test_post_scale_ok_follows_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(tmp_path, monkeypatch, "SCALE_TOLERANCE=0.05")
    assert parse_post_meta(_post_meta(tmp_path, -0.04), tmp_path / "o.glb").scale_ok


# ---------- judge ----------


def test_default_thresholds_match_history() -> None:
    assert escala_thresholds() == (0.03, 0.1)


@pytest.mark.parametrize(
    ("err", "expected"),
    [(0.0, 5), (0.0499, 5), (0.05, 3), (0.1666, 3), (0.1667, 1), (0.5, 1)],
)
def test_escala_thresholds_scale_with_tolerance(err: float, expected: int) -> None:
    assert escala_from_error(err, tolerance=0.05) == expected


def test_escala_follows_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env(tmp_path, monkeypatch, "SCALE_TOLERANCE=0.05")
    assert escala_from_error(0.04) == 5


class _StubVLM:
    def ask_json(self, prompt: str, images: list[Path], schema_hint: str) -> dict:
        return {"parecido": 5, "geometria": 5, "materiales": 5, "comentario": "ok"}


def test_judge_apt_depends_on_tolerance() -> None:
    kwargs = {"blind_id": "c1", "photos": [], "renders": [], "geometry": _metrics(0.04)}
    strict = judge_candidate(_StubVLM(), **kwargs)
    loose = judge_candidate(_StubVLM(), **kwargs, tolerance=0.05)
    assert (strict["escala"], strict["apt"]) == (3, False)
    assert (loose["escala"], loose["apt"]) == (5, True)
