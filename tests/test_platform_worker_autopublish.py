"""Routing (``intake.decide_route``), the admin's material note and the automatic
publishing rule (``autopublish.decide``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_worker import autopublish, cli, intake
from platform_worker.interpret import Interpretation

PIECE_ID = "44444444-4444-4444-4444-444444444444"
TOL = 0.03

# The owner's travertine fixture as the silhouette interpreter reads it (interpret report):
# buildable 0.82, central pedestal 0.90, round top, base ratio 0.51.
TRAVERTINE = Interpretation(
    rectilinear=True,
    support="pie_central",
    kind="mesa",
    confidence=0.82,
    reasons=["pedestal: top on one central column → buildable (parametric pedestal)"],
    top_shape="round",
    base_ratio=0.51,
    photo_aspect=1.10,
    support_confidence=0.90,
)
NO_EVIDENCE = Interpretation(None, None, None, 0.0, ["no evidence"])


def row(**overrides) -> dict:
    base = {
        "id": PIECE_ID,
        "name": "Mesa Travertino",
        "kind": "otro",
        "rectilinear": None,
        "support": "no_se",
        "notes": "",
        "width_cm": 60,
        "height_cm": 45,
        "depth_cm": 60,
    }
    base.update(overrides)
    return base


def interp(**overrides) -> Interpretation:
    base = {
        "rectilinear": True,
        "support": "patas",
        "kind": "mesa",
        "confidence": 0.9,
        "reasons": [],
        "support_confidence": 0.9,
    }
    base.update(overrides)
    return Interpretation(**base)


# ------------------------------------------------------------------------------ routing


def test_travertine_with_default_answers_is_an_e_pedestal() -> None:
    routing = intake.decide_route(row(), TRAVERTINE, provider_available=False)
    assert routing.route == intake.ROUTE_E and routing.rectilinear is True
    assert routing.kind == "pedestal"
    assert routing.params["base_diameter_ratio"] == pytest.approx(0.5, abs=0.02)
    assert routing.params["top_shape"] == "round"
    assert routing.effective["support"] == "no_se"  # never pie_central for pieces.support
    assert routing.effective["conflict"] == []


def test_travertine_support_conflict_builds_the_photo_pedestal() -> None:
    """The owner's case: «mesa», support «patas», photo = one central column."""
    routing = intake.decide_route(
        row(kind="mesa", support="patas"), TRAVERTINE, provider_available=False
    )
    assert routing.route == intake.ROUTE_E
    assert routing.kind == "pedestal" and routing.photo_overrides_support is True
    assert routing.params["base_diameter_ratio"] == pytest.approx(0.5, abs=0.02)
    assert routing.effective["support"] == "patas"  # the customer's answer is what is stored
    [conflict] = routing.effective["conflict"]
    assert conflict["field"] == "support" and conflict["inferred"] == "pie_central"
    assert any("Conflicto de apoyo" in r for r in routing.reasons)


def test_travertine_original_inputs_still_route_to_a_valid_pedestal() -> None:
    """60 × 30 × 25 (wrong depth): oval top, ratio clamped to E's range."""
    routing = intake.decide_route(
        row(kind="mesa", support="patas", height_cm=30, depth_cm=25),
        TRAVERTINE,
        provider_available=False,
    )
    assert routing.kind == "pedestal" and routing.params["top_shape"] == "oval"
    assert 0.15 <= routing.params["base_diameter_ratio"] <= 0.95


@pytest.mark.parametrize(
    ("support", "notes", "expected"),
    [
        ("patas", "", "table"),
        ("paneles", "", "panel_table"),
        ("caja", "", "box"),
        ("caja", "con zócalo", "box_legs"),
    ],
)
def test_customer_support_picks_the_parametric_kind(support, notes, expected) -> None:
    routing = intake.decide_route(
        row(kind="aparador", support=support, notes=notes), NO_EVIDENCE, provider_available=True
    )
    assert (routing.route, routing.kind, routing.params) == (intake.ROUTE_E, expected, {})


def test_default_answers_route_by_the_photo() -> None:
    """otro / null / no_se: the interpretation decides (never straight to organic)."""
    table = intake.decide_route(row(), interp(), provider_available=True)
    assert (table.route, table.kind) == (intake.ROUTE_E, "table")
    assert table.effective["source"] == {
        "kind": "inferred",
        "rectilinear": "inferred",
        "support": "inferred",
    }
    sofa = intake.decide_route(
        row(name="Sofá"),
        interp(rectilinear=False, support=None, kind="sofa", support_confidence=0.0),
        provider_available=True,
    )
    assert sofa.route == intake.ROUTE_ORGANIC


def test_dont_know_never_forces_e_by_itself() -> None:
    """«mesa» + «no sé» used to go to E: now only the photo (or an explicit yes) does."""
    routing = intake.decide_route(row(kind="mesa"), NO_EVIDENCE, provider_available=True)
    assert routing.route == intake.ROUTE_ORGANIC


def test_explicit_yes_without_support_uses_e_classification() -> None:
    routing = intake.decide_route(
        row(kind="mesa", rectilinear=True), NO_EVIDENCE, provider_available=True
    )
    assert (routing.route, routing.kind) == (intake.ROUTE_E, None)


def test_headboard_without_support_is_a_box() -> None:
    routing = intake.decide_route(
        row(kind="cabecero", width_cm=165, height_cm=60, depth_cm=6),
        NO_EVIDENCE,
        provider_available=False,
    )
    assert (routing.route, routing.kind) == (intake.ROUTE_E, "box")


def test_unsure_without_provider_goes_to_manual_review() -> None:
    low = interp(rectilinear=True, confidence=0.55, support=None, support_confidence=0.0)
    routing = intake.decide_route(row(), low, provider_available=False)
    assert routing.route == intake.ROUTE_MANUAL
    assert "no es fiable" in routing.reasons[-1]
    # Straight by the photo but the support is unknown: also manual, with that reason.
    straight = interp(support=None, support_confidence=0.0)
    routing = intake.decide_route(row(), straight, provider_available=False)
    assert routing.route == intake.ROUTE_MANUAL and "apoya" in routing.reasons[-1]


def test_sure_organic_without_provider_stays_organic() -> None:
    """The pipeline fails it with the «no provider» message (as before)."""
    routing = intake.decide_route(
        row(rectilinear=False, kind="sillon"), NO_EVIDENCE, provider_available=False
    )
    assert routing.route == intake.ROUTE_ORGANIC


def test_round_or_oval_text_does_not_force_organic_with_a_pedestal() -> None:
    routing = intake.decide_route(
        row(name="Mesa redonda de travertino"), TRAVERTINE, provider_available=True
    )
    assert routing.kind == "pedestal"


def test_build_piece_uses_the_route() -> None:
    routing = intake.decide_route(row(), TRAVERTINE, provider_available=False)
    piece = intake.build_piece(row(), [Path("1.jpg")], routing)
    assert piece.rectilinear is True and "mesa" in piece.description
    organic = intake.decide_route(row(kind="mesa"), NO_EVIDENCE, provider_available=True)
    assert intake.build_piece(row(kind="mesa"), [Path("1.jpg")], organic).rectilinear is False


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        (None, None),
        ("", None),
        ("Patas muy gruesas", None),
        ("material:oak", "oak"),
        ("Más claro.\nmaterial:white_marble", "white_marble"),
        ("material:oak material:travertine", "travertine"),
        ("material:none", "none"),
        ("supermaterial:oak", None),
    ],
)
def test_material_from_note(note, expected) -> None:
    assert intake.material_from_note(note) == expected


def test_no_object_wording_has_no_technical_detail() -> None:
    message = intake._english_issue("Objeto no detectado tras rembg (máscara vacía)")
    assert message == (
        "We couldn't find the piece in the photo. Use a photo where the whole piece is "
        "visible on a plain background."
    )
    assert "rembg" not in message and "background removal" not in message


# ------------------------------------------------------------------------- auto-publish


def decide(**overrides) -> autopublish.AutoReview:
    routing = overrides.pop("routing", None) or intake.decide_route(
        row(), TRAVERTINE, provider_available=False
    )
    args = {
        "enabled": True,
        "route": routing.route,
        "deliverable": True,
        "max_error": 0.002,
        "tolerance": TOL,
        "routing": routing,
        "interpretation": TRAVERTINE,
        "conflicts": list(routing.effective["conflict"]),
        "warnings": [],
        "judge": None,
    }
    args.update(overrides)
    return autopublish.decide(**args)


def test_e_with_confident_photo_is_published() -> None:
    review = decide()
    assert review.auto and review.gate == "rules"
    assert review.to_dict()["decision"] == "auto"


def test_scale_failure_goes_to_manual() -> None:
    review = decide(max_error=0.04)
    assert not review.auto and "Error de escala 4,0 %" in review.reasons[0]
    assert not decide(max_error=None).auto
    assert not decide(deliverable=False).auto


def test_e_with_confidence_0_9_is_auto_and_0_5_manual() -> None:
    sure = interp(confidence=0.9, support_confidence=0.9)
    routing = intake.decide_route(row(), sure, provider_available=False)
    assert routing.route == intake.ROUTE_E and decide(routing=routing, interpretation=sure).auto
    # 0.5: the rectilinear reading is not used at all, yet the confident support still
    # picks E's table — the shape is not confirmed, so it waits for the admin.
    unsure = interp(confidence=0.5, support_confidence=0.9)
    routing = intake.decide_route(row(), unsure, provider_available=False)
    assert (routing.route, routing.kind) == (intake.ROUTE_E, "table")
    review = decide(routing=routing, interpretation=unsure)
    assert not review.auto and "recta: sin respuesta" in review.reasons[0]


def test_e_with_low_rectilinear_confidence_is_manual() -> None:
    weak = interp(confidence=0.7, support_confidence=0.9)  # trusted (≥ 0.6) but < 0.8
    routing = intake.decide_route(row(), weak, provider_available=False)
    assert routing.route == intake.ROUTE_E
    review = decide(routing=routing, interpretation=weak)
    assert not review.auto and "70,0 %" in review.reasons[0]


def test_customer_answers_are_trusted() -> None:
    routing = intake.decide_route(
        row(kind="aparador", rectilinear=True, support="paneles"),
        NO_EVIDENCE,
        provider_available=False,
    )
    assert decide(routing=routing, interpretation=NO_EVIDENCE).auto


def test_e_heuristic_kind_is_not_trusted() -> None:
    routing = intake.decide_route(
        row(kind="mesa", rectilinear=True), NO_EVIDENCE, provider_available=False
    )
    review = decide(routing=routing, interpretation=NO_EVIDENCE)
    assert not review.auto and "clasificación de E" in review.reasons[0]


def test_conflict_goes_to_manual() -> None:
    routing = intake.decide_route(
        row(kind="mesa", support="patas"), TRAVERTINE, provider_available=False
    )
    review = decide(routing=routing)
    assert not review.auto
    assert "Conflicto en «support»" in review.reasons[0]


def test_any_warning_goes_to_manual() -> None:
    review = decide(warnings=["From the photo, the height looks closer to ~45 cm than 30 cm."])
    assert not review.auto and review.reasons[0].startswith("Aviso: From the photo")


def test_organic_without_judge_is_manual() -> None:
    routing = intake.decide_route(row(name="Sofá"), NO_EVIDENCE, provider_available=True)
    review = decide(routing=routing, interpretation=NO_EVIDENCE)
    assert not review.auto and "sin juez visual" in review.reasons[0]


def scores(p: int, g: int, m: int, apt: bool | None = None) -> dict:
    ok = all(v >= 4 for v in (p, g, m))
    return {
        "parecido": p,
        "geometria": g,
        "materiales": m,
        "escala": 5,
        "apt": ok if apt is None else apt,
        "comentario": "Patas algo finas.",
    }


def test_judge_5_5_4_publishes_even_organic() -> None:
    routing = intake.decide_route(row(name="Sofá"), NO_EVIDENCE, provider_available=True)
    review = decide(routing=routing, interpretation=NO_EVIDENCE, judge=lambda: scores(5, 5, 4))
    assert review.auto and review.gate == "vlm" and review.scores["materiales"] == 4


def test_judge_3_is_manual_with_the_scores() -> None:
    review = decide(judge=lambda: scores(5, 3, 5))
    assert not review.auto and review.gate == "vlm"
    assert "geometria 3" in review.reasons[0] and review.scores["geometria"] == 3
    assert review.reasons[1] == "Comentario del juez: Patas algo finas."
    assert not decide(judge=lambda: scores(5, 5, 5, apt=False)).auto


def test_judge_error_is_manual() -> None:
    def broken() -> dict:
        raise RuntimeError("timeout")

    review = decide(judge=broken)
    assert not review.auto and "El juez visual falló: RuntimeError: timeout" in review.reasons


def test_judge_does_not_run_when_hard_requirements_fail() -> None:
    calls: list[int] = []
    decide(max_error=0.2, judge=lambda: calls.append(1) or scores(5, 5, 5))
    assert calls == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, True), ("1", True), ("true", True), ("0", False), ("off", False), ("NO", False)],
)
def test_auto_publish_flag(raw, expected) -> None:
    assert autopublish.auto_publish_enabled({"AUTO_PUBLISH": raw}) is expected


def test_auto_publish_off_is_manual() -> None:
    review = decide(enabled=False)
    assert not review.auto and review.reasons == ["Publicación automática desactivada"]


# ------------------------------------------------------------------------ startup check


def test_startup_warns_without_gltf_transform_or_materials(tmp_path: Path) -> None:
    warnings = cli.startup_warnings(tmp_path / "no-gltf", tmp_path / "no-materials")
    assert len(warnings) == 2
    assert "gltf-transform" in warnings[0] and "setup_worker.sh" in warnings[0]
    assert "materiales" in warnings[1]
    tool = tmp_path / "gltf-transform"
    tool.write_text("#!/bin/sh\n")
    folder = tmp_path / "materials"
    (folder / "oak").mkdir(parents=True)
    assert cli.startup_warnings(tool, folder) == []
