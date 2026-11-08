"""Bounding-box validation of input photos and the user-facing photo requirements."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from harness.prep import clean
from harness.prep.requirements import PHOTO_REQUIREMENTS, explain

GREY = (128, 128, 128)
METAL = (40, 40, 40)


def _fake_rembg(image: Image.Image) -> Image.Image:
    """Deterministic stand-in for rembg: every non-grey pixel belongs to the object."""
    rgb = np.asarray(image.convert("RGB"))
    alpha = np.where((rgb == 128).all(axis=-1), 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


@pytest.fixture(autouse=True)
def no_rembg(monkeypatch) -> None:
    monkeypatch.setattr(clean, "_remove_background", _fake_rembg)


def _mask_stats(path: Path) -> tuple[float, float, float]:
    """Return (pixel fraction, bbox width / long side, bbox height / long side)."""
    with Image.open(path) as img:
        mask = clean._object_mask(_fake_rembg(img))
    left, top, right, bottom = mask.getbbox()
    long_side = max(mask.size)
    fraction = mask.histogram()[255] / (mask.width * mask.height)
    return fraction, (right - left) / long_side, (bottom - top) / long_side


def _coat_rack(path: Path) -> Path:
    """Thin silhouette: pole, hooks and a tripod base on a 1000×1500 grey canvas."""
    img = Image.new("RGB", (1000, 1500), GREY)
    draw = ImageDraw.Draw(img)
    draw.rectangle((490, 200, 515, 1250), fill=METAL)  # pole, 70 % of the long side
    draw.line((502, 230, 330, 330), fill=METAL, width=14)  # hooks
    draw.line((502, 230, 675, 330), fill=METAL, width=14)
    draw.line((502, 1180, 250, 1250), fill=METAL, width=16)  # tripod base
    draw.line((502, 1180, 755, 1250), fill=METAL, width=16)
    img.save(path)
    return path


def _square_object(path: Path, size: tuple[int, int], box: tuple[int, int, int, int]) -> Path:
    img = Image.new("RGB", size, GREY)
    img.paste((200, 30, 30), box)
    img.save(path)
    return path


def test_thin_silhouette_passes(tmp_path: Path) -> None:
    rack = _coat_rack(tmp_path / "perchero.png")
    fraction, box_w, box_h = _mask_stats(rack)
    assert fraction < 0.05  # the old 10 % area rule would have rejected it
    assert box_h == pytest.approx(0.70, abs=0.01)
    assert clean.validate_input(rack) == []


def test_tiny_object_fails(tmp_path: Path) -> None:
    # 150×150 px box on a 1500 px long side: 10 % of the long side in both axes
    tiny = _square_object(tmp_path / "tiny.png", (1000, 1500), (400, 600, 550, 750))
    problems = clean.validate_input(tiny)
    assert len(problems) == 1
    assert problems[0].startswith("Objeto demasiado pequeño")
    assert "10 % × 10 %" in problems[0]
    assert "≥ 25 %)" in problems[0]


def test_tiny_object_with_stray_pixel_fails(tmp_path: Path) -> None:
    # A rembg speck in the opposite corner must not inflate the box
    path = _square_object(tmp_path / "speck.png", (1000, 1500), (50, 50, 200, 200))
    with Image.open(path) as img:
        img = img.copy()
    img.putpixel((990, 1490), METAL)
    img.save(path)
    problems = clean.validate_input(path)
    assert len(problems) == 1
    assert problems[0].startswith("Objeto demasiado pequeño")


def test_elongated_piece_passes(tmp_path: Path) -> None:
    # Well-framed headboard (like p12): 60 % wide but only 20 % tall
    headboard = _square_object(tmp_path / "cabecero.png", (1500, 1000), (300, 400, 1200, 700))
    assert clean.validate_input(headboard) == []


def test_small_elongated_object_fails(tmp_path: Path) -> None:
    # 20 % × 5 %: elongated but small along its longer axis too
    stick = _square_object(tmp_path / "stick.png", (1000, 1500), (400, 700, 475, 1000))
    assert clean.validate_input(stick)[0].startswith("Objeto demasiado pequeño")


def test_no_object_detected(tmp_path: Path) -> None:
    empty = tmp_path / "empty.png"
    Image.new("RGB", (1200, 1200), GREY).save(empty)
    problems = clean.validate_input(empty)
    assert problems == ["Objeto no detectado: la eliminación de fondo no encuentra ninguna pieza"]


def test_low_resolution_fails(tmp_path: Path) -> None:
    low = _square_object(tmp_path / "low.png", (600, 800), (100, 100, 500, 700))
    problems = clean.validate_input(low)
    assert len(problems) == 1
    assert problems[0] == "Resolución insuficiente: lado mayor 800 px (< 1.000 px)"


def test_core_small_object_still_rejected(tmp_path: Path) -> None:
    # Mirrors the tiny-object case of tests/test_core.py::test_validate_input
    tiny = _square_object(tmp_path / "t.png", (1200, 1000), (0, 0, 100, 100))
    assert "Objeto" in clean.validate_input(tiny)[0]


def test_requirements_list() -> None:
    text = " ".join(PHOTO_REQUIREMENTS).lower()
    for needle in ("frontal", "tres cuartos", "fondo", "recortes", "1.000 px", "centímetros"):
        assert needle in text


def test_explain_with_issues(tmp_path: Path) -> None:
    tiny = _square_object(tmp_path / "tiny.png", (1000, 1500), (400, 600, 550, 750))
    message = explain(clean.validate_input(tiny))
    assert message.startswith("La foto no se puede usar todavía:")
    assert "Objeto demasiado pequeño" in message
    assert "Requisitos de la foto:" in message
    assert all(req in message for req in PHOTO_REQUIREMENTS)


def test_explain_without_issues() -> None:
    assert explain([]) == "La foto cumple los requisitos."


def test_spanish_number_formatting() -> None:
    assert clean.format_int(1000) == "1.000"
    assert clean.format_int(800) == "800"
    assert clean.format_pct(0.25) == "25 %"
    assert any("25 %" in req for req in PHOTO_REQUIREMENTS)
