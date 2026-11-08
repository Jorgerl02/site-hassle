from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from harness.clients.gemini_image import DEFAULT_MODEL, GeminiImageClient, GeminiImageError
from harness.core import pricing
from harness.core.models import Piece
from harness.prep import clean
from harness.prep.synth_views import (
    VIEW_NAMES,
    check_views,
    generate_views,
    silhouette_aspect,
    view_prompt,
)
from harness.variants.c_synth_tripo import SynthTripoVariant

# conftest `piece`: width 120, height 75, depth 60 → front/back 1.6, side 0.8


def silhouette(path: Path, aspect: float, size: int = 512, color=(90, 60, 30)) -> Path:
    """White canvas with a centred dark rectangle of the given width/height aspect."""
    img = Image.new("RGB", (size, size), (255, 255, 255))
    h = int(size * 0.6 / max(aspect, 1))
    w = int(h * aspect)
    left, top = (size - w) // 2, (size - h) // 2
    img.paste(color, (left, top, left + w, top + h))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def png_b64(aspect: float) -> str:
    """Base64 PNG with a dark rectangle of ``aspect``; ``aspect < 0`` → blank white image."""
    buf = io.BytesIO()
    img = Image.new("RGB", (256, 256), (255, 255, 255))
    if aspect < 0:
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    h = int(256 * 0.6 / max(aspect, 1))
    w = int(h * aspect)
    img.paste(
        (20, 20, 20), ((256 - w) // 2, (256 - h) // 2, (256 - w) // 2 + w, (256 - h) // 2 + h)
    )
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@dataclass
class FakeInteractions:
    """Stands in for ``genai.Client().interactions``; picks an aspect from the prompt."""

    aspects: dict[str, float]
    requests: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **body: Any) -> SimpleNamespace:
        self.requests.append(body)
        prompt = body["input"][0]["text"]
        for key, aspect in self.aspects.items():
            if key in prompt:
                data = png_b64(aspect) if aspect else None
                return SimpleNamespace(
                    id=f"int-{len(self.requests)}",
                    output_image=SimpleNamespace(data=data) if data else None,
                    output_text="refused" if not data else "",
                )
        raise AssertionError(f"unexpected prompt: {prompt}")


def fake_sdk(**aspects: float) -> SimpleNamespace:
    return SimpleNamespace(interactions=FakeInteractions(aspects))


GOOD = {"FRONT view": 1.6, "SIDE view": 0.8, "BACK view": 1.6, "THREE-QUARTER": 1.2}


# --- Gemini client -----------------------------------------------------------------------


def test_gemini_edit_sends_image_and_prompt_and_writes_png(tmp_path: Path) -> None:
    src = silhouette(tmp_path / "in.png", 1.6)
    sdk = fake_sdk(**{"make it": 0.8})
    client = GeminiImageClient(client=sdk)

    out = client.edit(src, "make it a side view", tmp_path / "out" / "side.png")

    assert out.exists()
    assert silhouette_aspect(out) == pytest.approx(0.8, rel=0.05)
    body = sdk.interactions.requests[0]
    assert body["model"] == DEFAULT_MODEL
    assert body["input"][0] == {"type": "text", "text": "make it a side view"}
    assert body["input"][1]["type"] == "image"
    assert body["input"][1]["mime_type"] == "image/png"
    assert base64.b64decode(body["input"][1]["data"]) == src.read_bytes()
    assert body["response_format"]["type"] == "image"
    assert client.calls[0]["cost_usd"] == pricing.GEMINI_IMAGE_USD
    assert client.total_cost_usd == pytest.approx(pricing.GEMINI_IMAGE_USD)


def test_gemini_edit_without_image_raises_and_records_cost(tmp_path: Path) -> None:
    src = silhouette(tmp_path / "in.png", 1.6)
    client = GeminiImageClient(client=fake_sdk(**{"x": 0}), model="custom-model")
    with pytest.raises(GeminiImageError):
        client.edit(src, "x", tmp_path / "out.png")
    assert client.calls[0]["ok"] is False
    assert client.calls[0]["model"] == "custom-model"
    assert client.total_cost_usd == pytest.approx(pricing.GEMINI_IMAGE_USD)


def test_gemini_requires_key_without_injected_client() -> None:
    with pytest.raises(GeminiImageError):
        GeminiImageClient(api_key=None)


# --- prompts -----------------------------------------------------------------------------


def test_view_prompts_state_constraints_and_measures(piece: Piece) -> None:
    for view in VIEW_NAMES:
        prompt = view_prompt(view, piece)
        assert "orthographic" in prompt
        assert "SAME object" in prompt
        assert "white background" in prompt
        assert "no shadows" in prompt
        assert "no additional objects" in prompt
        assert "studio lighting" in prompt
        assert "120 cm" in prompt and "75 cm" in prompt and "60 cm" in prompt
    assert "depth 60 cm × height 75 cm" in view_prompt("side", piece)


# --- check_views -------------------------------------------------------------------------


def test_check_views_all_pass(tmp_path: Path, piece: Piece) -> None:
    views = {
        "front": silhouette(tmp_path / "front.png", 1.6),
        "side": silhouette(tmp_path / "side.png", 0.85),  # +6 % → within 10 %
        "back": silhouette(tmp_path / "back.png", 1.5),
        "three_quarter": silhouette(tmp_path / "tq.png", 1.2),
    }
    check = check_views(views, piece)
    assert not check.degraded
    assert list(check.passed) == ["front", "side", "back", "three_quarter"]
    assert check.reasons == []
    assert check.checks["side"]["expected"] == pytest.approx(0.8)


def test_check_views_drops_failing_view(tmp_path: Path, piece: Piece) -> None:
    views = {
        "front": silhouette(tmp_path / "front.png", 1.6),
        "side": silhouette(tmp_path / "side.png", 1.6),  # side drawn as wide as the front
        "back": silhouette(tmp_path / "back.png", 1.6),
        "three_quarter": silhouette(tmp_path / "tq.png", 1.2),
    }
    check = check_views(views, piece)
    assert not check.degraded
    assert list(check.passed) == ["front", "back", "three_quarter"]
    assert check.checks["side"]["ok"] is False
    assert check.checks["side"]["error"] == pytest.approx(1.0, rel=0.05)
    assert any(r.startswith("side:") for r in check.reasons)


def test_check_views_blank_view_fails(tmp_path: Path, piece: Piece) -> None:
    blank = tmp_path / "blank.png"
    Image.new("RGB", (64, 64), (255, 255, 255)).save(blank)
    views = {"front": silhouette(tmp_path / "front.png", 1.6), "side": blank}
    check = check_views(views, piece)
    assert check.checks["side"]["ok"] is False
    assert check.degraded  # only front left


def test_check_views_degrades_to_front_only(tmp_path: Path, piece: Piece) -> None:
    views = {
        "front": silhouette(tmp_path / "front.png", 1.6),
        "side": silhouette(tmp_path / "side.png", 2.0),
        "back": silhouette(tmp_path / "back.png", 0.7),
    }
    check = check_views(views, piece)
    assert check.degraded
    assert check.passed == {"front": views["front"]}
    assert any("solo frontal" in r for r in check.reasons)


def test_check_views_degrades_when_front_fails(tmp_path: Path, piece: Piece) -> None:
    views = {
        "front": silhouette(tmp_path / "front.png", 1.0),
        "side": silhouette(tmp_path / "side.png", 0.8),
        "back": silhouette(tmp_path / "back.png", 1.6),
    }
    check = check_views(views, piece)
    assert check.degraded
    assert list(check.passed) == ["front"]
    assert check.to_dict()["degraded"] is True


# --- generate_views ----------------------------------------------------------------------


def test_generate_views_reuses_frontal_photo(tmp_path: Path, piece: Piece) -> None:
    front = silhouette(tmp_path / "clean.png", 1.6)
    client = GeminiImageClient(client=fake_sdk(**GOOD))
    views = generate_views(front, piece, tmp_path / "work", client=client)
    assert list(views) == list(VIEW_NAMES)
    assert all(p.exists() and p.parent.name == "views" for p in views.values())
    assert len(client.calls) == 3  # front is the photo itself


def test_generate_views_synthesises_front_for_non_frontal_photo(
    tmp_path: Path, piece: Piece
) -> None:
    three_quarter_photo = silhouette(tmp_path / "clean.png", 1.0)
    client = GeminiImageClient(client=fake_sdk(**GOOD))
    views = generate_views(three_quarter_photo, piece, tmp_path / "work", client=client)
    assert len(client.calls) == 4
    assert silhouette_aspect(views["front"]) == pytest.approx(1.6, rel=0.05)


# --- variant C end to end ----------------------------------------------------------------


@dataclass
class StubTripo:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate(self, images: list[Path], dst_glb: Path, *, seed: int | None = None):
        self.calls.append({"images": list(images), "seed": seed})
        dst_glb.parent.mkdir(parents=True, exist_ok=True)
        dst_glb.write_bytes(b"glTF")
        return SimpleNamespace(
            glb_path=dst_glb, cost_usd=0.25, seconds=1.0, meta={"task_id": f"t{seed}"}
        )


@pytest.fixture
def photo(piece: Piece, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = piece.images[0]
    img = Image.new("RGB", (1200, 900), (200, 200, 200))
    img.paste((40, 30, 20), (200, 250, 1000, 750))  # 800×500 → aspect 1.6
    img.save(path)

    def fake_remove(image: Image.Image) -> Image.Image:
        rgba = image.convert("RGBA")
        alpha = image.convert("L").point(lambda v: 255 if v < 128 else 0)
        rgba.putalpha(alpha)
        return rgba

    monkeypatch.setattr(clean, "_remove_background", fake_remove)
    return path


def test_variant_c_end_to_end(tmp_path: Path, piece: Piece, photo: Path) -> None:
    tripo = StubTripo()
    gemini = GeminiImageClient(client=fake_sdk(**GOOD))
    variant = SynthTripoVariant(tripo=tripo, image_client=gemini)
    workdir = tmp_path / "run" / "p01" / "C"

    result = variant.run(piece, workdir, candidates=2)

    assert variant.name == "C" and result.variant == "C"
    assert [c.index for c in result.candidates] == [1, 2]
    assert [c["seed"] for c in tripo.calls] == [1, 2]
    names = [p.stem for p in tripo.calls[0]["images"]]
    assert names == ["front", "side", "back", "three_quarter"]

    image_cost = 3 * pricing.GEMINI_IMAGE_USD
    assert sum(c.cost_usd for c in result.candidates) == pytest.approx(2 * 0.25 + image_cost)

    meta = json.loads((workdir / "cand_1" / "meta.json").read_text())
    assert meta["views_passed"] == ["front", "side", "back", "three_quarter"]
    assert meta["views_degraded"] is False
    assert meta["view_checks"]["side"]["ok"] is True
    assert meta["views_cost_usd_total"] == pytest.approx(image_cost)
    assert meta["tripo_cost_usd"] == 0.25
    assert len(meta["image_calls"]) == 3
    assert "multivista" in result.notes


def test_variant_c_degrades_to_front_only(tmp_path: Path, piece: Piece, photo: Path) -> None:
    tripo = StubTripo()
    # side and back with wrong proportions, three-quarter comes back blank
    bad = {"FRONT view": 1.6, "SIDE view": 2.5, "BACK view": 0.5, "THREE-QUARTER": -1}
    gemini = GeminiImageClient(client=fake_sdk(**bad))
    variant = SynthTripoVariant(tripo=tripo, image_client=gemini)

    result = variant.run(piece, tmp_path / "C", candidates=1)

    images = tripo.calls[0]["images"]
    assert [p.stem for p in images] == ["front"]
    meta = json.loads((tmp_path / "C" / "cand_1" / "meta.json").read_text())
    assert meta["views_degraded"] is True
    assert meta["views_passed"] == ["front"]
    assert meta["view_checks"]["side"]["ok"] is False
    assert "degradada" in result.notes


def test_variant_c_lazy_clients_need_keys(tmp_path: Path, piece: Piece) -> None:
    from harness.core.config import Settings

    variant = SynthTripoVariant(settings=Settings())
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        _ = variant.image_client
