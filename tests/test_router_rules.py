"""Variant F — rule-based routing (no VLM, no network)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness.core import storage
from harness.core.config import Settings
from harness.core.models import Candidate, Piece, VariantResult
from harness.variants.f_router import (
    ROUTE_VLM,
    RouteDecision,
    RouterVariant,
    is_thin,
    rule_classify,
)


def make_piece(
    tmp_path: Path,
    rectilinear: bool | None,
    dims: tuple[float, float, float] = (110, 106, 35),
    n_images: int = 2,
) -> Piece:
    w, h, d = dims
    return Piece(
        id="p99",
        name="X",
        store="Tienda",
        source_url="https://example.com",
        category="macizo_mate",
        images=[tmp_path / f"{i}.jpg" for i in range(1, n_images + 1)],
        width_cm=w,
        height_cm=h,
        depth_cm=d,
        rectilinear=rectilinear,
    )


class StubDelegate:
    """Writes one fake GLB candidate under ``workdir``."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        self.calls += 1
        cand = storage.candidate_dir(workdir, 1)
        glb = storage.model_path(cand)
        glb.write_bytes(b"glb")
        meta = {"variant": self.name}
        storage.write_meta(cand, meta)
        return VariantResult(
            variant=self.name,
            piece_id=piece.id,
            candidates=[Candidate(index=1, glb_path=glb, meta=meta)],
        )


class StubVLM:
    def __init__(self, rectilinear: bool) -> None:
        self.rectilinear = rectilinear
        self.total_cost_usd = 0.0
        self.calls = 0

    def ask_json(self, prompt: str, images: list[Path], schema_hint: str) -> dict[str, Any]:
        self.calls += 1
        self.total_cost_usd += 0.002
        return {"rectilinear": self.rectilinear, "motivo": "stub"}


NO_KEY = Settings(anthropic_api_key=None)
WITH_KEY = Settings(anthropic_api_key="sk-test")


def router(**kwargs: Any) -> tuple[RouterVariant, dict[str, StubDelegate]]:
    stubs = {name: StubDelegate(name) for name in ("E", "C", "B")}
    kwargs.setdefault("settings", NO_KEY)
    variant = RouterVariant(e=stubs["E"], c=stubs["C"], b=stubs["B"], **kwargs)
    return variant, stubs


# ---------------------------------------------------------------- rule_classify


def test_rectilinear_goes_to_e(tmp_path: Path) -> None:
    assert rule_classify(make_piece(tmp_path, True)) == RouteDecision("E", "rectilínea", False)


def test_rectilinear_thin_piece_still_goes_to_e(tmp_path: Path) -> None:
    decision = rule_classify(make_piece(tmp_path, True, dims=(180, 3, 90)))
    assert decision.route == "E" and decision.thin
    assert "fina" in decision.reason


@pytest.mark.parametrize(
    ("dims", "thin"),
    [
        ((110, 106, 35), False),
        ((200, 3, 90), True),  # a dimension below 8 cm
        ((160, 80, 10), True),  # width/depth = 16 > 15
        ((40, 160, 10), True),  # height/depth = 16 > 15
        ((150, 150, 10), False),  # exactly 15 is not thin
        ((8, 8, 8), False),
    ],
)
def test_is_thin(tmp_path: Path, dims, thin: bool) -> None:
    assert is_thin(make_piece(tmp_path, True, dims=dims)) is thin


def test_organic_goes_to_c_or_b_by_photos(tmp_path: Path) -> None:
    assert rule_classify(make_piece(tmp_path, False, n_images=2)).route == "C"
    assert rule_classify(make_piece(tmp_path, False, n_images=1)).route == "B"
    trellis = rule_classify(make_piece(tmp_path, False), organic_variant="TRELLIS")
    assert trellis == RouteDecision("TRELLIS", "orgánica", False)


def test_unlabelled_asks_vlm_only_when_available(tmp_path: Path) -> None:
    piece = make_piece(tmp_path, None)
    assert rule_classify(piece, vlm_available=True).route == ROUTE_VLM
    no_vlm = rule_classify(piece)
    assert no_vlm == RouteDecision("C", "sin etiqueta", False)


# ---------------------------------------------------------------- RouterVariant


def test_auto_without_key_uses_rules(tmp_path: Path) -> None:
    variant, stubs = router()
    assert variant.resolved_classifier() == "rules"
    result = variant.run(make_piece(tmp_path, True), tmp_path / "F")
    assert stubs["E"].calls == 1 and stubs["C"].calls == 0
    meta = result.candidates[0].meta
    assert meta["routed_to"] == "E" and meta["variant"] == "F"
    assert meta["router"]["source"] == "rules"
    assert meta["router"]["rule"] == {"route": "E", "reason": "rectilínea", "thin": False}
    assert meta["router"]["cost_usd"] == 0.0 and meta["router_cost_usd_share"] == 0.0
    assert variant.decide(make_piece(tmp_path, True))[1]["classifier"] == "rules"
    assert storage.read_meta(storage.candidate_dir(tmp_path / "F", 1))["routed_to"] == "E"
    assert result.notes.startswith("Reglas: rectilínea → ruta E")


def test_rules_route_organic_and_unlabelled(tmp_path: Path) -> None:
    variant, stubs = router(classifier="rules")
    organic = variant.run(make_piece(tmp_path, False, n_images=1), tmp_path / "F1")
    assert organic.candidates[0].meta["routed_to"] == "B" and stubs["B"].calls == 1
    unlabelled = variant.run(make_piece(tmp_path, None), tmp_path / "F2")
    router_meta = unlabelled.candidates[0].meta["router"]
    assert unlabelled.candidates[0].meta["routed_to"] == "C"
    assert router_meta["motivo"] == "sin etiqueta" and router_meta["rectilinear"] is False


def test_rules_never_consult_vlm_even_when_available(tmp_path: Path) -> None:
    vlm = StubVLM(rectilinear=True)
    variant, stubs = router(classifier="rules", vlm=vlm, settings=WITH_KEY)
    result = variant.run(make_piece(tmp_path, None), tmp_path / "F")
    assert vlm.calls == 0 and stubs["E"].calls == 0 and stubs["C"].calls == 1
    router_meta = result.candidates[0].meta["router"]
    assert router_meta["source"] == "rules" and router_meta["motivo"] == "sin etiqueta"
    assert router_meta["classifier"] == "rules" and router_meta["cost_usd"] == 0.0
    variant.run(make_piece(tmp_path, False), tmp_path / "F2")
    assert vlm.calls == 0


def test_auto_with_key_uses_vlm(tmp_path: Path) -> None:
    vlm = StubVLM(rectilinear=False)
    variant, stubs = router(vlm=vlm, settings=WITH_KEY)
    assert variant.resolved_classifier() == "vlm"
    result = variant.run(make_piece(tmp_path, True), tmp_path / "F")
    assert vlm.calls == 1 and stubs["C"].calls == 1
    assert result.candidates[0].meta["router"]["classifier"] == "vlm"
    assert RouterVariant(settings=WITH_KEY).resolved_classifier() == "vlm"


def test_organic_variant_is_configurable(tmp_path: Path) -> None:
    trellis = StubDelegate("TRELLIS")
    variant, _ = router(organic_variant="TRELLIS", others={"TRELLIS": trellis})
    result = variant.run(make_piece(tmp_path, False), tmp_path / "F")
    assert trellis.calls == 1 and result.candidates[0].meta["routed_to"] == "TRELLIS"
    with pytest.raises(ValueError, match="TRELLIS"):
        router(organic_variant="TRELLIS")  # rejected early: no delegate in others
    fixed, stubs = router(organic_variant="B")
    assert fixed.run(make_piece(tmp_path, False), tmp_path / "F2").candidates
    assert stubs["B"].calls == 1


def test_unknown_classifier_rejected() -> None:
    with pytest.raises(ValueError, match="clasificador"):
        RouterVariant(classifier="dice")
