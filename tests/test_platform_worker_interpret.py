"""Automatic photo interpretation (``platform_worker.interpret``).

Synthetic silhouettes are drawn with PIL and fed to the silhouette functions directly (no
rembg). The real-photo evaluation (30 pilot photos + the owner's travertine pedestal) is
opt-in: ``HARNESS_INTERPRET_EVAL=1 uv run pytest tests/test_platform_worker_interpret.py``.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from platform_worker.interpret import (
    Interpretation,
    NoObject,
    SilhouetteInterpreter,
    bottom_support,
    check_dimensions,
    combine,
    merge_answers,
    prepare_mask,
    silhouette_features,
    text_hint,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "platform"

real_eval = pytest.mark.skipif(
    os.environ.get("HARNESS_INTERPRET_EVAL") != "1",
    reason="real-photo evaluation (rembg): set HARNESS_INTERPRET_EVAL=1",
)


# --------------------------------------------------------------------------- synthetic masks


def _canvas(w: int = 600, h: int = 500) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("L", (w, h), 0)
    return img, ImageDraw.Draw(img)


def _arr(img: Image.Image) -> np.ndarray:
    return np.asarray(img) > 0


def table_on_legs() -> np.ndarray:
    img, d = _canvas()
    d.rectangle((50, 100, 549, 139), fill=255)  # top
    for x in (70, 180, 400, 510):  # four legs seen from the front
        d.rectangle((x, 140, x + 19, 449), fill=255)
    return _arr(img)


def side_panel_table() -> np.ndarray:
    img, d = _canvas()
    d.rectangle((50, 100, 549, 139), fill=255)
    d.rectangle((60, 140, 159, 449), fill=255)  # left slab, seen at an angle
    d.rectangle((470, 140, 539, 449), fill=255)  # right slab
    return _arr(img)


def box() -> np.ndarray:
    img, d = _canvas()
    d.rectangle((100, 50, 499, 449), fill=255)
    return _arr(img)


def plinth_box() -> np.ndarray:
    img, d = _canvas()
    d.rectangle((100, 50, 499, 409), fill=255)  # body
    d.rectangle((130, 410, 469, 449), fill=255)  # recessed plinth (85 % of the width)
    return _arr(img)


def blob_sofa() -> np.ndarray:
    img, d = _canvas()
    d.ellipse((60, 60, 540, 330), fill=255)  # rounded back
    d.ellipse((40, 200, 560, 440), fill=255)  # rounded seat
    return _arr(img)


def headboard() -> np.ndarray:
    img, d = _canvas()
    d.rectangle((50, 150, 549, 349), fill=255)
    return _arr(img)


def pedestal_table() -> np.ndarray:
    """Round top seen slightly from above (an ellipse) on one centred cylinder."""
    img, d = _canvas(600, 600)
    d.rectangle((230, 150, 369, 520), fill=255)  # column
    d.ellipse((230, 490, 369, 550), fill=255)  # its elliptical base
    d.ellipse((50, 60, 549, 220), fill=255)  # top
    return _arr(img)


# --------------------------------------------------------------------------- silhouette


@pytest.mark.parametrize(
    ("make", "support"),
    [
        (table_on_legs, "patas"),
        (side_panel_table, "paneles"),
        (box, "caja"),
        (plinth_box, "caja"),
        (pedestal_table, "pie_central"),
    ],
)
def test_bottom_support(make, support):
    reading = bottom_support(prepare_mask(make()))
    assert reading.support == support, reading.reason
    assert reading.confidence >= 0.6


def test_pedestal_reports_base_ratio():
    reading = bottom_support(prepare_mask(pedestal_table()))
    assert reading.base_ratio == pytest.approx(140 / 500, abs=0.03)


@pytest.mark.parametrize("make", [table_on_legs, side_panel_table, box, plinth_box, headboard])
def test_boxy_silhouettes_are_rectilinear_with_a_rect_top(make):
    features = silhouette_features(prepare_mask(make()))
    assert features.top_shape == "rect"
    assert features.rectilinear_evidence() > 2


@pytest.mark.parametrize("make", [blob_sofa, pedestal_table])
def test_rounded_silhouettes_are_organic_with_a_round_top(make):
    features = silhouette_features(prepare_mask(make()))
    assert features.top_shape == "round"
    assert features.rectilinear_evidence() < -2


def test_prepare_mask_crops_and_resizes():
    mask = prepare_mask(box())
    assert max(mask.shape) == 256
    assert mask.all()  # cropped to the object
    with pytest.raises(ValueError):
        prepare_mask(np.zeros((10, 10), dtype=bool))


# --------------------------------------------------------------------------- interpreter


def _interpret(make, dims=(120, 75, 60), name="", notes="") -> Interpretation:
    interpreter = SilhouetteInterpreter(masker=lambda _path: make())
    w, h, d = dims
    return interpreter.interpret(
        [Path("photo.jpg")], width_cm=w, height_cm=h, depth_cm=d, name=name, notes=notes
    )


def test_interpreter_table_on_legs():
    result = _interpret(table_on_legs)
    assert (result.rectilinear, result.support, result.kind) == (True, "patas", None)
    assert result.confidence >= 0.8
    assert any("legs" in r for r in result.reasons)


def test_interpreter_blob_sofa_is_organic_and_text_names_it():
    result = _interpret(blob_sofa, dims=(200, 85, 90), name="Sofá tres plazas")
    assert result.rectilinear is False
    assert result.kind == "sofa"
    assert result.top_shape == "round"


def test_interpreter_thin_headboard_is_a_box():
    result = _interpret(headboard, dims=(160, 120, 5))
    assert (result.rectilinear, result.support, result.kind) == (True, "caja", "cabecero")
    tall = _interpret(headboard, dims=(60, 200, 3))
    assert tall.kind == "panel"


def coat_rack() -> np.ndarray:
    """A pole with hooks on top: one centred column, but no solid top."""
    img, d = _canvas(300, 600)
    d.rectangle((140, 60, 159, 560), fill=255)
    for x in (60, 110, 170, 220):  # hooks
        d.rectangle((x, 60, x + 19, 99), fill=255)
    d.rectangle((90, 540, 209, 559), fill=255)  # small foot
    return _arr(img)


def test_interpreter_pedestal_is_buildable_despite_its_round_top():
    result = _interpret(pedestal_table, dims=(60, 50, 60), name="Mesa redonda de pie central")
    assert result.rectilinear is True  # E's parametric pedestal builds it
    assert result.support == "pie_central"
    assert result.top_shape == "round"
    assert 0.2 < (result.base_ratio or 0) < 0.4
    assert result.support_confidence >= 0.85
    assert any("pedestal" in r for r in result.reasons)


def test_a_column_without_a_solid_top_is_not_a_pedestal():
    assert bottom_support(prepare_mask(coat_rack())).support != "pie_central"


@pytest.mark.parametrize(
    "error", [OSError("no photo"), RuntimeError("onnxruntime failed"), MemoryError("bomb")]
)
def test_a_failing_masker_degrades_to_text_and_dimensions(error):
    def broken(_path: Path) -> np.ndarray:
        raise error

    interpreter = SilhouetteInterpreter(masker=broken)
    result = interpreter.interpret(
        [Path("x.jpg")], width_cm=100, height_cm=80, depth_cm=40, name="Aparador de roble"
    )
    assert (result.rectilinear, result.kind, result.support) == (True, "aparador", None)
    assert result.reasons[0].startswith("photo: could not be analysed")
    assert type(error).__name__ in result.reasons[0]
    nothing = interpreter.interpret([Path("x.jpg")], width_cm=100, height_cm=80, depth_cm=40)
    assert (nothing.rectilinear, nothing.confidence) == (None, 0.0)


def _object_in_frame(frame: int, side: int) -> np.ndarray:
    mask = np.zeros((frame, frame), dtype=bool)
    mask[:side, :side] = True
    return mask


@pytest.mark.parametrize(
    ("mask", "why"),
    [
        (np.ones((1, 1), dtype=bool), "fills 100%"),
        (np.ones((3, 3), dtype=bool), "fills 100%"),
        (np.ones((10, 30), dtype=bool), "fills 100%"),
        (np.full((500, 400), 255, dtype=np.uint8), "fills 100%"),  # all-white photo
        (np.zeros((200, 200), dtype=bool), "no object"),
        (_object_in_frame(1000, 50), "covers only"),  # 0.25 % of the frame
        (_object_in_frame(100, 15), "only 15×15 px"),  # 2 % of the frame but tiny
    ],
)
def test_degenerate_masks_are_no_object(mask, why):
    with pytest.raises(NoObject):
        prepare_mask(mask)
    result = SilhouetteInterpreter(masker=lambda _p: mask).interpret(
        [Path("x.jpg")], width_cm=100, height_cm=80, depth_cm=40
    )
    assert (result.rectilinear, result.confidence, result.support) == (None, 0.0, None)
    assert result.reasons[0].startswith("photo: no object") and why in result.reasons[0]
    assert check_dimensions(mask, 100, 80, 40) == []


def test_text_outweighs_a_weak_silhouette_but_not_a_round_one():
    features = silhouette_features(prepare_mask(blob_sofa()))
    hint = text_hint("Cabecero tapizado")
    result = combine(
        features=features, support=None, hint=hint, thin=False, width_cm=100, height_cm=80
    )
    assert result.rectilinear is False  # round caps beat a single text hint
    assert result.kind == "cabecero"


# --------------------------------------------------------------------------- text hints


@pytest.mark.parametrize(
    ("name", "notes", "kind", "sign"),
    [
        ("Sofá cama 3 plazas", "", "sofa", -1),
        ("SILLÓN orejero", "", "sillon", -1),
        ("Butacas de terciopelo", "", "sillon", -1),
        ("Lounge armchair", "", "sillon", -1),
        ("Jarrón de cerámica", "", "jarron", -1),
        ("Floor lamp", "", "lampara", -1),
        ("Lámpara de pie", "", "lampara", -1),
        ("Cabecero tapizado", "", "cabecero", 1),
        ("Oak headboard", "", "cabecero", 1),
        ("Zapatero de mango", "", "aparador", 1),
        ("Cómoda", "", "aparador", 1),
        ("Estantería de pino", "", "estanteria", 1),
        ("Bookcase", "", "estanteria", 1),
        ("Mesa de noche", "", "mesita", 1),
        ("Mesita", "", "mesita", 1),
        ("Oak side table", "", "mesita", 1),
        ("Mesa de comedor", "", "mesa", 1),
        ("Mesa redonda", "", "mesa", 0),
        ("Round coffee table", "", "mesa", 0),
        ("Mesa redonda de pie central", "", "mesa", 0),
        ("Mesa de cantos redondeados", "", "mesa", 1),  # rounded corners: still a box
        ("Table with rounded corners", "", "mesa", 1),
        ("", "Mueble: banco de entrada", "otro", 1),
        ("Mi pieza", "es una silla", "silla", -1),
    ],
)
def test_text_hint(name, notes, kind, sign):
    hint = text_hint(name, notes)
    assert hint is not None
    assert hint.kind == kind
    assert np.sign(hint.evidence) == sign


def test_text_hint_prefers_the_name_and_ignores_unknown_words():
    hint = text_hint("Aparador nórdico", "va junto a la mesa")
    assert hint is not None and hint.kind == "aparador"
    assert text_hint("Pieza bonita", "de madera") is None


# --------------------------------------------------------------------------- consistency


def test_check_dimensions_flags_the_owners_pedestal_case():
    warnings = check_dimensions(pedestal_table(), 60, 30, 25)
    assert len(warnings) == 2
    assert warnings[0].startswith("From the photo, the height looks closer to ~")
    assert "than 30 cm" in warnings[0]
    assert warnings[1] == (
        "If the top is round, width and depth are usually similar — is the depth really "
        "25 cm? (Ignore this if it is oval.)"
    )


def test_check_dimensions_names_the_implied_height():
    # Silhouette aspect 1.1, entered 60 × 30 × 25: from the slightly-from-above bound,
    # height ≈ 60 / 1.1 − 0.35 · 25 ≈ 45.8 → "~45 cm" (owner's example).
    seen = Interpretation(True, None, None, 0.9, photo_aspect=1.1)
    assert check_dimensions(seen, 60, 30, 25) == [
        "From the photo, the height looks closer to ~45 cm than 30 cm. "
        "Please check the height (and the width, 60 cm)."
    ]
    flat = Interpretation(True, None, None, 0.9, photo_aspect=4.0)  # wider than entered
    assert "closer to ~15 cm than 45 cm" in check_dimensions(flat, 60, 45, 10)[0]


@pytest.mark.parametrize("dims", [(0, 30, 25), (60, 0, 25), (60, 30, 0), (-1, 30, 25)])
def test_check_dimensions_ignores_non_positive_dimensions(dims):
    assert check_dimensions(pedestal_table(), *dims) == []


def test_check_dimensions_accepts_consistent_dimensions():
    assert check_dimensions(pedestal_table(), 60, 55, 60) == []
    assert check_dimensions(box(), 80, 80, 40) == []  # a box seen from the front


def test_check_dimensions_from_an_interpretation():
    round_table = Interpretation(False, None, "mesa", 0.9, top_shape="round", photo_aspect=1.0)
    assert check_dimensions(round_table, 60, 60, 60) == []
    assert check_dimensions(round_table, 60, 60, 46) == []  # 1.30: within 0.75–1.33
    assert len(check_dimensions(round_table, 60, 60, 30)) == 1  # round top, 60 vs 30
    assert len(check_dimensions(round_table, 30, 30, 60)) == 1  # 0.5
    rect_table = Interpretation(True, None, "mesa", 0.9, top_shape="rect", photo_aspect=1.0)
    assert check_dimensions(rect_table, 60, 60, 30) == []
    # Round caps on a piece that is not a table (round-ended sideboard): no depth warning.
    sideboard = Interpretation(False, "paneles", "aparador", 0.9, top_shape="round")
    assert check_dimensions(sideboard, 160, 80, 40) == []


# --------------------------------------------------------------------------- merge_answers

DEFAULTS = {"kind": "otro", "rectilinear": None, "support": "no_se"}
INFERRED = Interpretation(True, "paneles", "mesita", 0.8, support_confidence=0.75)


def test_merge_uses_inferred_values_for_default_answers():
    merged = merge_answers(DEFAULTS, INFERRED)
    assert (merged["kind"], merged["rectilinear"], merged["support"]) == (
        "mesita",
        True,
        "paneles",
    )
    assert merged["source"] == {
        "kind": "inferred",
        "rectilinear": "inferred",
        "support": "inferred",
    }
    assert merged["conflict"] == []


def test_merge_explicit_customer_answers_win():
    customer = {"kind": "mesa", "rectilinear": False, "support": "patas"}
    merged = merge_answers(customer, INFERRED)
    assert (merged["kind"], merged["rectilinear"], merged["support"]) == ("mesa", False, "patas")
    assert set(merged["source"].values()) == {"customer"}
    assert merged["conflict"] == []  # contradicted, but not with ≥ 0.85 confidence


def test_merge_trusts_a_confidence_exactly_at_the_threshold():
    exact = Interpretation(True, "caja", "mesita", 0.6, support_confidence=0.6)
    merged = merge_answers(DEFAULTS, exact, min_confidence=0.6)
    assert (merged["kind"], merged["rectilinear"], merged["support"]) == (
        "mesita",
        True,
        "caja",
    )
    assert merged["routing_kind"] == "box"
    below = Interpretation(True, "caja", "mesita", 0.599, support_confidence=0.599)
    assert merge_answers(DEFAULTS, below)["source"]["rectilinear"] == "default"


def test_merge_low_confidence_falls_back_to_defaults():
    unsure = Interpretation(True, "caja", "mesa", 0.55, support_confidence=0.55)
    merged = merge_answers(DEFAULTS, unsure)
    assert (merged["kind"], merged["rectilinear"], merged["support"]) == ("otro", None, "no_se")
    assert set(merged["source"].values()) == {"default"}
    assert merge_answers(DEFAULTS, unsure, min_confidence=0.5)["rectilinear"] is True


def test_merge_skips_support_for_organic_pieces():
    organic = Interpretation(False, "patas", "sillon", 0.9, support_confidence=0.8)
    merged = merge_answers(DEFAULTS, organic)
    assert (merged["support"], merged["routing_kind"]) == ("no_se", None)


def test_merge_routes_a_pedestal_without_storing_it_as_support():
    pedestal = Interpretation(
        True,
        "pie_central",
        "mesa",
        0.85,
        top_shape="round",
        base_ratio=0.5,
        support_confidence=0.9,
    )
    merged = merge_answers(DEFAULTS, pedestal)
    assert merged["support"] == "no_se"  # pieces.support never gets pie_central
    assert merged["source"]["support"] == "default"
    assert merged["routing_kind"] == "pedestal"
    assert merged["pedestal_params"] == {"base_diameter_ratio": 0.5, "top_shape": "round"}
    oval = merge_answers({**DEFAULTS, "width_cm": 120, "depth_cm": 80}, pedestal)
    assert oval["pedestal_params"] == {"base_diameter_ratio": 0.75, "top_shape": "oval"}
    # A customer who says it is not straight keeps the organic route.
    assert merge_answers({**DEFAULTS, "rectilinear": False}, pedestal)["routing_kind"] is None


@pytest.mark.parametrize(
    ("support", "notes", "routing"),
    [
        ("patas", "", "table"),
        ("paneles", "", "panel_table"),
        ("caja", "", "box"),
        ("caja", "sobre un zócalo", "box_legs"),
        ("pie_central", "", None),  # not a customer value: counts as unanswered
        ("no_se", "", None),
    ],
)
def test_merge_routing_kind_from_the_customer_support(support, notes, routing):
    customer = {"kind": "mesa", "rectilinear": True, "support": support, "notes": notes}
    merged = merge_answers(customer, Interpretation(None, None, None, 0.0))
    assert merged["routing_kind"] == routing
    assert merged["support"] in ("patas", "paneles", "caja", "no_se")
    assert merged["pedestal_params"] is None


def test_merge_headboard_without_support_is_a_box():
    customer = {"kind": "cabecero", "rectilinear": True, "support": "no_se"}
    assert merge_answers(customer, Interpretation(None, None, None, 0.0))["routing_kind"] == "box"


def test_merge_no_conflict_when_the_customer_agrees_with_the_photo():
    customer = {"kind": "mesa", "rectilinear": True, "support": "paneles"}
    photo = Interpretation(True, "paneles", "mesa", 0.95, support_confidence=0.95)
    merged = merge_answers(customer, photo)
    assert merged["conflict"] == []
    assert merged["routing_kind"] == "panel_table"


def test_merge_no_support_conflict_for_an_organic_piece():
    customer = {"kind": "sillon", "rectilinear": False, "support": "patas"}
    photo = Interpretation(False, "caja", "sillon", 0.9, support_confidence=0.9)
    assert merge_answers(customer, photo)["conflict"] == []


def test_merge_reports_confident_contradictions_as_conflicts():
    # The owner's case: support «patas» against a photo that clearly shows one pedestal.
    customer = {"kind": "mesa", "rectilinear": True, "support": "patas"}
    photo = Interpretation(
        False, "pie_central", None, 0.9, top_shape="round", support_confidence=0.9
    )
    merged = merge_answers(customer, photo)
    assert (merged["rectilinear"], merged["support"]) == (True, "patas")  # customer kept
    assert (merged["routing_kind"], merged["pedestal_params"]) == ("table", None)
    assert {c["field"] for c in merged["conflict"]} == {"rectilinear", "support"}
    support = next(c for c in merged["conflict"] if c["field"] == "support")
    assert support == {
        "field": "support",
        "customer": "patas",
        "inferred": "pie_central",
        "confidence": 0.9,
    }


def test_interpretation_to_dict_is_json_ready():
    data = INFERRED.to_dict()
    assert data["support"] == "paneles" and data["reasons"] == []
    assert set(data) >= {"rectilinear", "support", "kind", "confidence", "top_shape", "base_ratio"}


# --------------------------------------------------------------------------- real photos


def _eval_module():
    spec = importlib.util.spec_from_file_location(
        "eval_interpret", ROOT / "scripts" / "eval_interpret.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up there
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def evaluation():
    module = _eval_module()
    return module, module.cached_masker(None)


@real_eval
def test_real_photos_meet_the_targets(evaluation):
    module, masker = evaluation
    if not (ROOT / "data" / "images" / "p01" / "1.jpg").is_file():
        pytest.skip("pilot photos (data/images, gitignored) are not available")
    pieces, labels = module.load_pieces(), module.load_labels()
    with_names = module.evaluate(pieces, labels, masker, use_names=True)
    blind = module.evaluate(pieces, labels, masker, use_names=False)
    assert with_names.rectilinear >= module.TARGET_RECTILINEAR_NAMES
    assert blind.rectilinear >= module.TARGET_RECTILINEAR_BLIND
    for scores in (with_names, blind):
        assert scores.support >= module.TARGET_SUPPORT
        for piece_id in module.REQUIRED_SUPPORT_IDS:
            assert scores.support_ok(piece_id), piece_id


@real_eval
def test_real_travertine_pedestal(evaluation):
    module, masker = evaluation
    case = module.evaluate_pedestal(masker)
    assert case.pred.rectilinear is True  # buildable by E's pedestal kind
    assert case.pred.support == "pie_central"
    assert case.pred.top_shape == "round"
    assert 0.4 < (case.pred.base_ratio or 0) < 0.6
    assert len(case.warnings) == 2
    assert [c["field"] for c in case.merged["conflict"]] == ["support"]
    assert case.merged["support"] == "patas"  # the customer's answer is kept for review
    assert case.merged["routing_kind"] == "table"
