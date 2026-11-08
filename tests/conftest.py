from __future__ import annotations

import csv
from pathlib import Path

import pytest

from harness.core import config
from harness.core.models import CSV_COLUMNS, Piece

FIXTURES = Path(__file__).parent / "fixtures"
ENV_KEYS = (
    "TRIPO_API_KEY",
    "MESHY_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "BLENDER_BIN",
    "SCALE_TOLERANCE",
)


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tests never see real keys or a real Blender, not even from the repo's .env."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "DEFAULT_ENV_FILE", tmp_path / "no-such.env")


@pytest.fixture
def cube_glb() -> Path:
    return FIXTURES / "cube.glb"


@pytest.fixture
def piece(tmp_path: Path) -> Piece:
    return Piece(
        id="p01",
        name="Mesa de roble",
        store="Tienda",
        source_url="https://example.com/mesa",
        category="macizo_mate",
        images=[tmp_path / "1.jpg"],
        width_cm=120,
        height_cm=75,
        depth_cm=60,
        description="Mesa rectangular de roble macizo",
        rectilinear=True,
    )


def piece_row(**overrides: str) -> dict[str, str]:
    row = {
        "id": "p01",
        "name": "Mesa de roble",
        "store": "Tienda",
        "source_url": "https://example.com/mesa",
        "category": "macizo_mate",
        "images": "data/images/p01/1.jpg;data/images/p01/2.jpg",
        "width_cm": "120",
        "height_cm": "75",
        "depth_cm": "60",
        "description": "Mesa rectangular",
        "rectilinear": "true",
    }
    row.update(overrides)
    return row


def write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path
