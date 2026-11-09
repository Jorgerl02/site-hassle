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
from pytest_httpx import HTTPXMock

from harness.clients.gemini_image import DEFAULT_MODEL, GeminiImageClient, GeminiImageError
from harness.clients.tripo import DEFAULT_BASE_URL as TRIPO_BASE_URL
from harness.clients.tripo import TripoClient, TripoSettings
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

# conftest `piece`: width 120, height 75, depth 60 → front/back 1.6, left/right 0.8

GREEN = (0, 255, 0)
WHITE = (255, 255, 255)
WOOD = (90, 60, 30)


def draw(aspect: float, size: int = 256, bg=GREEN, color=WOOD) -> Image.Image:
    """Canvas with a centred rectangle of the given width/height; ``aspect < 0`` → empty."""
    img = Image.new("RGB", (size, size), bg)
    if aspect >= 0:
        h = int(size * 0.6 / max(aspect, 1))
        w = int(h * aspect)
        left, top = (size - w) // 2, (size - h) // 2
        img.paste(color, (left, top, left + w, top + h))
    return img


def silhouette(path: Path, aspect: float, bg=GREEN, color=WOOD) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    draw(aspect, 512, bg, color).save(path)
    return path


def png_b64(aspect: float) -> str:
    buf = io.BytesIO()
    draw(aspect).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@dataclass
class FakeInteractions:
    """Stands in for ``genai.Client().interactions``; picks the output from the prompt.

    Values: float aspect → green-background image; ``None`` → response without image;
    an Exception instance → raised like an SDK error."""

    outputs: dict[str, Any]
    requests: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **body: Any) -> SimpleNamespace:
        self.requests.append(body)
        prompt = body["input"][0]["text"]
        for key, value in self.outputs.items():
            if key in prompt:
                if isinstance(value, Exception):
                    raise value
                return SimpleNamespace(
                    id=f"int-{len(self.requests)}",
                    output_image=SimpleNamespace(data=png_b64(value))
                    if value is not None
                    else None,
                    output_text="" if value is not None else "refused",
                )
        raise AssertionError(f"unexpected prompt: {prompt}")


def fake_sdk(**outputs: Any) -> SimpleNamespace:
    return SimpleNamespace(interactions=FakeInteractions(outputs))


def outputs(front=1.6, left=0.8, back=1.6, right=0.8) -> dict[str, Any]:
    return {"FRONT view": front, "LEFT side": left, "BACK view": back, "RIGHT side": right}


def views_from(tmp_path: Path, **aspects: float) -> dict[str, Path]:
    return {v: silhouette(tmp_path / f"{v}.png", a) for v, a in aspects.items()}


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
    client = GeminiImageClient(client=fake_sdk(x=None), model="custom-model")
    with pytest.raises(GeminiImageError):
        client.edit(src, "x", tmp_path / "out.png")
    assert client.calls[0]["ok"] is False
    assert client.calls[0]["model"] == "custom-model"
    assert client.total_cost_usd == pytest.approx(pricing.GEMINI_IMAGE_USD)


def test_gemini_sdk_exception_is_wrapped_and_recorded(tmp_path: Path) -> None:
    src = silhouette(tmp_path / "in.png", 1.6)
    client = GeminiImageClient(client=fake_sdk(x=RuntimeError("503 overloaded")))
    with pytest.raises(GeminiImageError):
        client.edit(src, "x", tmp_path / "out.png")
    assert client.calls[0]["ok"] is False
    assert "503 overloaded" in client.calls[0]["error"]
    assert client.calls[0]["cost_usd"] == 0.0


def test_gemini_requires_key_without_injected_client() -> None:
    with pytest.raises(GeminiImageError):
        GeminiImageClient(api_key=None)


# --- prompts -----------------------------------------------------------------------------


def test_view_set_matches_tripo_slots() -> None:
    assert VIEW_NAMES == ("front", "left", "back", "right")


def test_view_prompts_state_constraints_and_measures(piece: Piece) -> None:
    for view in VIEW_NAMES:
        prompt = view_prompt(view, piece)
        assert "orthographic" in prompt
        assert "SAME object" in prompt
        assert "pure green background (#00FF00" in prompt
        assert "no shadows" in prompt
        assert "no additional objects" in prompt
        assert "studio lighting" in prompt
        assert "120 cm" in prompt and "75 cm" in prompt and "60 cm" in prompt
    assert "depth 60 cm × height 75 cm" in view_prompt("left", piece)
    assert "width 120 cm × height 75 cm" in view_prompt("back", piece)


# --- silhouettes -------------------------------------------------------------------------


def test_light_grey_object_on_green_passes(tmp_path: Path, piece: Piece) -> None:
    light = (245, 245, 245)  # would vanish under a white-background threshold
    views = {
        v: silhouette(tmp_path / f"{v}.png", a, color=light)
        for v, a in {"front": 1.6, "left": 0.8, "back": 1.6, "right": 0.8}.items()
    }
    on_white = silhouette(tmp_path / "white.png", 1.6, bg=WHITE, color=light)
    assert silhouette_aspect(on_white, "white") is None  # the old white key loses it
    check = check_views(views, piece)
    assert not check.degraded
    assert list(check.passed) == list(VIEW_NAMES)
    assert all(c["silhouette_method"] == "green" for c in check.checks.values())


def test_white_method_for_clean_photo(tmp_path: Path) -> None:
    photo = silhouette(tmp_path / "photo.png", 1.6, bg=WHITE)
    assert silhouette_aspect(photo, "white") == pytest.approx(1.6, rel=0.02)


# --- check_views: slot prefix rule ------------------------------------------------------


def test_check_views_all_pass_in_slot_order(tmp_path: Path, piece: Piece) -> None:
    views = views_from(tmp_path, right=0.8, back=1.5, left=0.85, front=1.6)  # unordered input
    check = check_views(views, piece)
    assert not check.degraded
    assert list(check.passed) == ["front", "left", "back", "right"]
    assert check.reasons == []
    assert check.checks["left"]["expected"] == pytest.approx(0.8)


def test_check_views_back_dropped_drops_right(tmp_path: Path, piece: Piece) -> None:
    views = views_from(tmp_path, front=1.6, left=0.8, back=0.5, right=0.8)
    check = check_views(views, piece, fallback_front=tmp_path / "photo.png")
    assert not check.degraded
    assert list(check.passed) == ["front", "left"]
    assert check.checks["back"]["ok"] is False
    assert check.checks["right"]["dropped_by_prefix"] is True
    assert any(r.startswith("right: descartada") for r in check.reasons)


def test_check_views_right_dropped_keeps_three(tmp_path: Path, piece: Piece) -> None:
    views = views_from(tmp_path, front=1.6, left=0.8, back=1.6, right=1.6)
    check = check_views(views, piece)
    assert list(check.passed) == ["front", "left", "back"]


def test_check_views_left_dropped_degrades_to_photo(tmp_path: Path, piece: Piece) -> None:
    photo = silhouette(tmp_path / "photo.png", 1.6, bg=WHITE)
    views = views_from(tmp_path, front=1.6, left=1.6, back=1.6, right=0.8)
    check = check_views(views, piece, fallback_front=photo)
    assert check.degraded
    assert check.passed == {"front": photo}
    assert check.checks["back"]["dropped_by_prefix"] is True
    assert any("solo la foto limpia" in r for r in check.reasons)


def test_check_views_failing_front_falls_back_to_photo(tmp_path: Path, piece: Piece) -> None:
    photo = silhouette(tmp_path / "photo.png", 1.6, bg=WHITE)
    views = views_from(tmp_path, front=1.0, left=0.8, back=1.6, right=0.8)
    check = check_views(views, piece, fallback_front=photo)
    assert check.degraded
    assert check.passed == {"front": photo}  # never the synthesised front that failed
    assert check.to_dict()["degraded"] is True


def test_check_views_missing_view_and_blank_view(tmp_path: Path, piece: Piece) -> None:
    views = views_from(tmp_path, front=1.6, left=0.8, right=0.8)  # back not generated
    check = check_views(views, piece)
    assert list(check.passed) == ["front", "left"]
    assert "back: no se generó" in check.reasons

    views = views_from(tmp_path, front=1.6, left=-1)  # blank left
    check = check_views(views, piece, fallback_front=views["front"])
    assert check.checks["left"]["ok"] is False
    assert check.degraded


# --- generate_views ----------------------------------------------------------------------


def test_generate_views_synthesises_all_four(tmp_path: Path, piece: Piece) -> None:
    photo = silhouette(tmp_path / "clean.png", 1.6, bg=WHITE)
    client = GeminiImageClient(client=fake_sdk(**outputs()))
    views = generate_views(photo, piece, tmp_path / "work", client=client)
    assert list(views) == list(VIEW_NAMES)
    assert all(p.exists() and p.parent.name == "views" for p in views.values())
    assert len(client.calls) == 4  # front is synthesised too


def test_generate_views_skips_failed_view(tmp_path: Path, piece: Piece) -> None:
    photo = silhouette(tmp_path / "clean.png", 1.6, bg=WHITE)
    client = GeminiImageClient(client=fake_sdk(**outputs(back=RuntimeError("boom"), right=None)))
    views = generate_views(photo, piece, tmp_path / "work", client=client)
    assert list(views) == ["front", "left"]
    assert len(client.calls) == 4
    assert client.total_cost_usd == pytest.approx(3 * pricing.GEMINI_IMAGE_USD)


# --- variant C end to end ----------------------------------------------------------------


@dataclass
class StubTripo:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate(
        self,
        images: list[Path],
        dst_glb: Path,
        *,
        seed: int | None = None,
        views: dict[str, Path] | None = None,
    ):
        assert views is not None and not images, "variant C must send labelled views only"
        self.calls.append({"images": list(views.values()), "views": dict(views), "seed": seed})
        dst_glb.parent.mkdir(parents=True, exist_ok=True)
        dst_glb.write_bytes(b"glTF")
        return SimpleNamespace(
            glb_path=dst_glb, cost_usd=0.25, seconds=1.0, meta={"task_id": f"t{seed}"}
        )


@pytest.fixture
def photo(piece: Piece, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = piece.images[0]
    img = Image.new("RGB", (1200, 900), (200, 200, 200))
    img.paste((40, 30, 20), (200, 250, 1000, 750))
    img.save(path)

    def fake_remove(image: Image.Image) -> Image.Image:
        rgba = image.convert("RGBA")
        rgba.putalpha(image.convert("L").point(lambda v: 255 if v < 128 else 0))
        return rgba

    monkeypatch.setattr(clean, "_remove_background", fake_remove)
    return path


def test_variant_c_end_to_end(tmp_path: Path, piece: Piece, photo: Path) -> None:
    tripo = StubTripo()
    variant = SynthTripoVariant(
        tripo=tripo, image_client=GeminiImageClient(client=fake_sdk(**outputs()))
    )
    workdir = tmp_path / "run" / "p01" / "C"

    result = variant.run(piece, workdir, candidates=2)

    assert variant.name == "C" and result.variant == "C"
    assert [c.index for c in result.candidates] == [1, 2]
    assert [c["seed"] for c in tripo.calls] == [1, 2]
    assert list(tripo.calls[0]["views"]) == ["front", "left", "back", "right"]
    assert all(p.stem == v for v, p in tripo.calls[0]["views"].items())

    image_cost = 4 * pricing.GEMINI_IMAGE_USD
    assert sum(c.cost_usd for c in result.candidates) == pytest.approx(2 * 0.25 + image_cost)

    meta = json.loads((workdir / "cand_1" / "meta.json").read_text())
    assert meta["views_passed"] == ["front", "left", "back", "right"]
    assert meta["views_degraded"] is False
    assert meta["view_checks"]["left"]["ok"] is True
    assert meta["view_checks"]["left"]["silhouette_method"] == "green"
    assert meta["clean_image"].endswith("clean/front.png")
    assert meta["clean_image_check"]["silhouette_method"] == "white"
    assert meta["views_cost_usd_total"] == pytest.approx(image_cost)
    assert meta["tripo_cost_usd"] == 0.25
    assert len(meta["image_calls"]) == 4
    assert "multivista" in result.notes


def test_variant_c_back_dropped_sends_front_left(tmp_path: Path, piece: Piece, photo: Path) -> None:
    tripo = StubTripo()
    gemini = GeminiImageClient(client=fake_sdk(**outputs(back=0.5)))
    SynthTripoVariant(tripo=tripo, image_client=gemini).run(piece, tmp_path / "C", candidates=1)
    assert [p.stem for p in tripo.calls[0]["images"]] == ["front", "left"]


def test_variant_c_left_dropped_sends_clean_photo(
    tmp_path: Path, piece: Piece, photo: Path
) -> None:
    tripo = StubTripo()
    gemini = GeminiImageClient(client=fake_sdk(**outputs(left=2.5)))
    result = SynthTripoVariant(tripo=tripo, image_client=gemini).run(
        piece, tmp_path / "C", candidates=1
    )
    meta = json.loads((tmp_path / "C" / "cand_1" / "meta.json").read_text())
    assert tripo.calls[0]["views"] == {"front": Path(meta["clean_image"])}
    assert meta["views_degraded"] is True
    assert meta["views_passed"] == ["front"]
    assert meta["view_checks"]["left"]["ok"] is False
    assert "degradada" in result.notes


def test_variant_c_failed_view_does_not_abort(tmp_path: Path, piece: Piece, photo: Path) -> None:
    tripo = StubTripo()
    gemini = GeminiImageClient(client=fake_sdk(**outputs(back=RuntimeError("500"), right=None)))
    result = SynthTripoVariant(tripo=tripo, image_client=gemini).run(
        piece, tmp_path / "C", candidates=1
    )
    assert [p.stem for p in tripo.calls[0]["images"]] == ["front", "left"]
    meta = json.loads((tmp_path / "C" / "cand_1" / "meta.json").read_text())
    assert meta["views_failed_generation"] == ["back", "right"]
    assert len(meta["image_calls"]) == 4
    assert [c["ok"] for c in meta["image_calls"]] == [True, True, False, False]
    # 3 billed calls (SDK error on `back` is not billed) + Tripo
    assert result.candidates[0].cost_usd == pytest.approx(0.25 + 3 * pricing.GEMINI_IMAGE_USD)


def test_variant_c_lazy_clients_need_keys(tmp_path: Path, piece: Piece) -> None:
    from harness.core.config import Settings

    variant = SynthTripoVariant(settings=Settings())
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        _ = variant.image_client


class FlakyTripo(StubTripo):
    """Fails on the seeds in ``fail_seeds`` (provider task failed)."""

    def __init__(self, fail_seeds: set[int]) -> None:
        super().__init__()
        self.fail_seeds = fail_seeds

    def generate(
        self,
        images: list[Path],
        dst_glb: Path,
        *,
        seed: int | None = None,
        views: dict[str, Path] | None = None,
    ):
        if seed in self.fail_seeds:
            self.calls.append({"images": list((views or {}).values()), "seed": seed})
            raise RuntimeError(f"tarea {seed} fallida")
        return super().generate(images, dst_glb, seed=seed, views=views)


def test_variant_c_keeps_paid_candidates_when_a_later_one_fails(
    tmp_path: Path, piece: Piece, photo: Path
) -> None:
    tripo = FlakyTripo({2})
    gemini = GeminiImageClient(client=fake_sdk(**outputs()))
    result = SynthTripoVariant(tripo=tripo, image_client=gemini).run(
        piece, tmp_path / "C", candidates=3
    )
    assert [c.index for c in result.candidates] == [1, 3]
    assert "cand_2: tarea 2 fallida" in result.notes
    failed = json.loads((tmp_path / "C" / "cand_2" / "meta.json").read_text())
    assert failed["error"] == "tarea 2 fallida"
    assert failed["cost_usd"] == pytest.approx(4 * pricing.GEMINI_IMAGE_USD / 3)


def test_variant_c_raises_when_every_candidate_fails(
    tmp_path: Path, piece: Piece, photo: Path
) -> None:
    gemini = GeminiImageClient(client=fake_sdk(**outputs()))
    with pytest.raises(RuntimeError, match="tarea 2"):
        SynthTripoVariant(tripo=FlakyTripo({1, 2}), image_client=gemini).run(
            piece, tmp_path / "C", candidates=2
        )
    assert json.loads((tmp_path / "C" / "cand_1" / "meta.json").read_text())["error"]


# --- variant C against a real TripoClient (HTTP mocked) -------------------------------------


def test_variant_c_sends_labelled_multiview_to_tripo(
    tmp_path: Path, piece: Piece, photo: Path, httpx_mock: HTTPXMock
) -> None:
    task_id = "1ec04ced-4b87-44f6-a296-beee80777941"
    glb_url = "https://tripo-data.example.com/out/model_pbr.glb"
    tripo_fixtures = Path(__file__).parent / "fixtures" / "tripo"
    for view in VIEW_NAMES:  # uploads happen in slot order: front, left, back, right
        httpx_mock.add_response(
            method="POST",
            url=f"{TRIPO_BASE_URL}/files",
            json={"code": 0, "data": {"file_token": f"tok-{view}"}},
        )
    httpx_mock.add_response(
        method="POST",
        url=f"{TRIPO_BASE_URL}/generation/multiview-to-model",
        json={"code": 0, "data": {"task_id": task_id}},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{TRIPO_BASE_URL}/tasks/{task_id}",
        json=json.loads((tripo_fixtures / "task_success.json").read_text()),
    )
    httpx_mock.add_response(method="GET", url=glb_url, content=b"glTF-fake")
    tripo = TripoClient("tsk_test", settings=TripoSettings(), sleep=lambda s: None)
    gemini = GeminiImageClient(client=fake_sdk(**outputs()))

    result = SynthTripoVariant(tripo=tripo, image_client=gemini).run(
        piece, tmp_path / "C", candidates=1
    )

    uploads = httpx_mock.get_requests(method="POST", url=f"{TRIPO_BASE_URL}/files")
    assert [
        f'filename="{v}.png"'.encode() in u.content
        for v, u in zip(VIEW_NAMES, uploads, strict=True)
    ] == [True] * 4
    assert not httpx_mock.get_requests(url=f"{TRIPO_BASE_URL}/generation/image-to-model")
    [create] = httpx_mock.get_requests(url=f"{TRIPO_BASE_URL}/generation/multiview-to-model")
    body = json.loads(create.content)
    assert body["inputs"] == [
        {"front": "tok-front"},
        {"left": "tok-left"},
        {"back": "tok-back"},
        {"right": "tok-right"},
    ]
    assert body["model_seed"] == 1
    assert result.candidates[0].glb_path.read_bytes() == b"glTF-fake"
    meta = json.loads((tmp_path / "C" / "cand_1" / "meta.json").read_text())
    assert meta["tripo_meta"]["task_type"] == "multiview_to_model"
