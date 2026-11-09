"""intake.check (excluded categories, photo requirements) and the row → Piece mapping."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from harness.prep import clean
from harness.variants.f_router import rule_classify
from platform_worker import intake

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


def _fake_rembg(image: Image.Image) -> Image.Image:
    """Deterministic stand-in for rembg: non-grey pixels are the object."""
    rgb = np.asarray(image.convert("RGB"))
    alpha = np.where((rgb == 128).all(axis=-1), 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


@pytest.fixture(autouse=True)
def no_rembg(monkeypatch) -> None:
    monkeypatch.setattr(clean, "_remove_background", _fake_rembg)


def photo(path: Path, size=(1600, 1200), box=(200, 300, 1400, 900)) -> Path:
    img = Image.new("RGB", size, (128, 128, 128))
    img.paste((150, 110, 80), box)
    img.save(path)
    return path


def row(**overrides) -> dict:
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Cabecero tapizado",
        "kind": "cabecero",
        "width_cm": 165,
        "height_cm": 60,
        "depth_cm": 3,
        "rectilinear": None,
        "notes": "",
        "attempt": 1,
    }
    base.update(overrides)
    return base


def test_lamp_is_excluded(tmp_path: Path) -> None:
    problems = intake.check(row(kind="lampara", name="Lámpara"), [photo(tmp_path / "1.jpg")])
    assert problems and "lámparas" in problems[0]


def test_chrome_note_is_excluded(tmp_path: Path) -> None:
    problems = intake.check(row(notes="Patas de Cromo"), [photo(tmp_path / "1.jpg")])
    assert problems == [intake.EXCLUDED_STEMS["crom"]]


@pytest.mark.parametrize(
    "notes",
    [
        "Mesa de metal",
        "Estructura metálica",
        "Patas cromadas",
        "Acero inoxidable",
        "Base de inox",
        "Tapa de vidrio",
        "Puertas acristaladas",
        "Sobre de cristal",
    ],
)
def test_other_excluded_materials(tmp_path: Path, notes: str) -> None:
    assert intake.check(row(notes=notes), [photo(tmp_path / "1.jpg")])


def test_words_inside_other_words_are_not_excluded(tmp_path: Path) -> None:
    assert intake.excluded_reasons(row(notes="Tapizado policromo")) == []


def test_headboard_3cm_is_ok_and_rectilinear(tmp_path: Path) -> None:
    photos = [photo(tmp_path / "1.jpg")]
    r = row()
    assert intake.check(r, photos) == []
    piece = intake.build_piece(r, photos)
    assert piece.rectilinear is True
    assert (piece.width_cm, piece.height_cm, piece.depth_cm) == (165, 60, 3)
    decision = rule_classify(piece)
    assert decision.route == "E" and decision.thin
    assert intake.parametric_kind_override(r) == "box"


def test_no_photos(tmp_path: Path) -> None:
    assert intake.check(row(), []) == ["La pieza no tiene ninguna foto"]


def test_pdf_is_not_an_image(tmp_path: Path) -> None:
    pdf = tmp_path / "1.jpg"
    pdf.write_bytes(b"%PDF-1.7\n...")
    problems = intake.check(row(), [pdf])
    assert problems == [
        "Foto 1: El archivo no es una imagen que podamos leer (usa JPG, PNG o WEBP)"
    ]


def test_photo_over_20mb(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(intake, "MAX_PHOTO_BYTES", 10)
    problems = intake.check(row(), [photo(tmp_path / "1.jpg")])
    assert problems[0].startswith("Foto 1: La foto pesa") and "máximo 20 MB" in problems[0]


def test_low_resolution_photo_uses_harness_validator(tmp_path: Path) -> None:
    small = photo(tmp_path / "1.jpg", size=(800, 600), box=(100, 100, 700, 500))
    problems = intake.check(row(), [small])
    assert problems[0].startswith("Foto 1: Resolución insuficiente")
    message = intake.explain(problems)
    assert message.startswith("Las fotos no se pueden usar todavía:")
    assert "Requisitos de la foto:" in message


@pytest.mark.parametrize(
    ("kind", "rectilinear", "expected"),
    [
        ("sofa", None, False),
        ("jarron", None, False),
        ("otro", None, False),
        ("mesa", None, True),
        ("mesa", False, False),
        ("sillon", True, True),
    ],
)
def test_rectilinear_resolution(kind: str, rectilinear, expected: bool) -> None:
    assert intake.is_rectilinear(row(kind=kind, rectilinear=rectilinear)) is expected


def test_table_notes_reach_the_parametric_classifier(tmp_path: Path) -> None:
    piece = intake.build_piece(
        row(kind="mesita", name="Auxiliar", notes="Auxiliar de travertino"), [tmp_path / "1.jpg"]
    )
    from harness.post.parametric_spec import classify

    assert classify(piece) == "panel_table"
    assert intake.parametric_kind_override(row(kind="mesita")) is None


# ---------------------------------------------------------------- support answer (W1)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"kind": "mesa", "support": "patas"}, "table"),
        ({"kind": "cabecero", "support": "paneles"}, "panel_table"),
        ({"kind": "aparador", "support": "caja", "notes": ""}, "box"),
        ({"kind": "aparador", "support": "caja", "notes": "Sobre un zócalo"}, "box_legs"),
        ({"kind": "aparador", "support": "caja", "notes": "Cuatro patas"}, "box_legs"),
        ({"kind": "cabecero", "support": "no_se"}, "box"),
        ({"kind": "cabecero", "support": None}, "box"),
        ({"kind": "mesa", "support": "no_se"}, None),
        ({"kind": "aparador"}, None),
    ],
)
def test_parametric_kind_override_from_support(row, expected) -> None:
    assert intake.parametric_kind_override(row) == expected
