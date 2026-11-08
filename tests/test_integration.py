"""End-to-end: ``bakeoff run`` (FAKE + A–D + F with stubbed clients) → ``eval`` (real
geometry, stubbed judge, pre-existing renders) → ``report``. Offline, no Blender."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw
from typer.testing import CliRunner

import harness.cli as cli_module
import harness.eval as eval_module
from harness.cli import app
from harness.clients.meshy import GenerationOutcome as MeshyOutcome
from harness.clients.tripo import GenerationOutcome as TripoOutcome
from harness.core import pricing, registry
from harness.core.models import CSV_COLUMNS
from harness.eval.render import VIEWS
from harness.prep import clean
from harness.variants.a_tripo_direct import TripoDirectVariant
from harness.variants.b_clean_tripo import CleanTripoVariant
from harness.variants.c_synth_tripo import SynthTripoVariant
from harness.variants.d_clean_meshy import CleanMeshyVariant
from harness.variants.e_parametric import ParametricVariant
from harness.variants.f_router import ROUTER_PROMPT, RouterVariant

FIXTURES = Path(__file__).parent / "fixtures"
CUBE = FIXTURES / "cube.glb"


# --- stubs ------------------------------------------------------------------------------------


class StubGenerator:
    """Tripo/Meshy stand-in: copies the cube fixture to ``dst_glb``."""

    def __init__(self, outcome_cls: type, price: float) -> None:
        self.outcome_cls = outcome_cls
        self.price = price
        self.calls: list[dict[str, Any]] = []

    def generate(self, images: list[Path], dst_glb: Path, *, seed: int | None = None) -> Any:
        dst_glb = Path(dst_glb)
        dst_glb.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CUBE, dst_glb)
        self.calls.append({"images": [str(p) for p in images], "seed": seed})
        return self.outcome_cls(
            glb_path=dst_glb, cost_usd=self.price, seconds=0.1, meta={"task_id": "stub"}
        )


class StubImageEditor:
    """Gemini stand-in: returns the input unchanged (no green key → C degrades to the photo)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def edit(self, image: Path, prompt: str, dst: Path) -> Path:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image, dst)
        self.calls.append({"cost_usd": pricing.GEMINI_IMAGE_USD, "seconds": 0.0})
        return Path(dst)


class StubVLM:
    def __init__(self, answer: dict[str, Any] | None = None, cost: float = 0.0) -> None:
        self.answer = answer
        self.cost = cost
        self.total_cost_usd = 0.0
        self.prompts: list[str] = []

    def ask_json(self, prompt: str, images: list[Path], schema_hint: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.total_cost_usd += self.cost
        if self.answer is not None:
            return self.answer
        return {"parecido": 5, "geometria": 4, "materiales": 4, "comentario": "correcto"}


class RouterVLM(StubVLM):
    """Answers ``rectilinear`` from the piece id found in the image paths."""

    def __init__(self, rectilinear_ids: set[str], cost: float = 0.002) -> None:
        super().__init__(cost=cost)
        self.rectilinear_ids = rectilinear_ids

    def ask_json(self, prompt: str, images: list[Path], schema_hint: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.total_cost_usd += self.cost
        rect = any(Path(p).parent.name in self.rectilinear_ids for p in images)
        return {"rectilinear": rect, "motivo": "stub"}


def _fake_remove_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    mask = image.convert("L").point(lambda v: 255 if v < 128 else 0)
    rgba.putalpha(mask)
    return rgba


# --- fixtures ---------------------------------------------------------------------------------


def _photo(path: Path, box: tuple[int, int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1200, 1200), (255, 255, 255))
    ImageDraw.Draw(img).rectangle(box, fill=(40, 30, 20))
    img.save(path, quality=95)
    return path


def _write_sample(root: Path) -> Path:
    rows = [
        {  # rectilinear, 1 photo: F → E → (no Blender) fallback → B
            "id": "t01",
            "name": "Mesa auxiliar",
            "store": "Tienda",
            "source_url": "https://example.com/t01",
            "category": "macizo_mate",
            "images": str(_photo(root / "images/t01/1.jpg", (300, 400, 900, 800))),
            "width_cm": "60",
            "height_cm": "40",
            "depth_cm": "40",
            "description": "Mesa de madera",
            "rectilinear": "true",
        },
        {  # organic, 2 photos: F → C
            "id": "t02",
            "name": "Butaca",
            "store": "Tienda",
            "source_url": "https://example.com/t02",
            "category": "tapizado",
            "images": ";".join(
                str(_photo(root / f"images/t02/{n}.jpg", (350, 300, 850, 900))) for n in (1, 2)
            ),
            "width_cm": "70",
            "height_cm": "80",
            "depth_cm": "75",
            "description": "Butaca tapizada",
            "rectilinear": "false",
        },
    ]
    sample = root / "sample.csv"
    with sample.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return sample


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    monkeypatch.chdir(tmp_path)  # no stray .env; relative paths land in tmp_path
    monkeypatch.setattr(clean, "_remove_background", _fake_remove_background)
    tripo = StubGenerator(TripoOutcome, pricing.TRIPO_USD_PER_MODEL)
    meshy = StubGenerator(MeshyOutcome, pricing.MESHY_USD_PER_MODEL)
    gemini = StubImageEditor()
    router_vlm = RouterVLM({"t01"})

    def router() -> RouterVariant:
        return RouterVariant(
            vlm=router_vlm,
            e=ParametricVariant(),  # real: raises BlenderNotAvailable here
            c=SynthTripoVariant(tripo=tripo, image_client=gemini),
            b=CleanTripoVariant(tripo),
        )

    factories = {
        "A": lambda: TripoDirectVariant(tripo),
        "B": lambda: CleanTripoVariant(tripo),
        "C": lambda: SynthTripoVariant(tripo=tripo, image_client=gemini),
        "D": lambda: CleanMeshyVariant(meshy),
        "E": ParametricVariant,
        "F": router,
    }
    for name, factory in factories.items():
        monkeypatch.setitem(registry._FACTORIES, name, factory)
    return {"tripo": tripo, "meshy": meshy, "gemini": gemini, "router_vlm": router_vlm}


# --- tests ------------------------------------------------------------------------------------


def test_registry_lists_a_to_f_without_keys() -> None:
    assert set("ABCDEF") <= set(registry.available_variants())
    for name in "abcdef":
        assert registry.get_variant(name).name == name.upper()


def test_router_falls_back_to_organic_without_blender(stubs: dict[str, Any], tmp_path: Path):
    from harness.core.models import load_pieces

    pieces = {p.id: p for p in load_pieces(_write_sample(tmp_path))}
    variant = registry.get_variant("F")
    workdir = tmp_path / "runs/r/t01/F"
    result = variant.run(pieces["t01"], workdir, 2)

    assert result.variant == "F" and len(result.candidates) == 2
    assert "E no disponible" in result.notes
    assert stubs["router_vlm"].prompts == [ROUTER_PROMPT]
    for cand in result.candidates:
        assert cand.glb_path == workdir / f"cand_{cand.index}" / "model.glb"
        assert cand.glb_path.is_file()
        assert cand.meta["routed_to"] == "B"
        assert cand.meta["router"]["rectilinear"] is True
        assert cand.meta["router"]["fallback"]
        assert cand.cost_usd == pytest.approx(pricing.TRIPO_USD_PER_MODEL + 0.001)
        meta = json.loads((cand.glb_path.parent / "meta.json").read_text())
        assert meta["variant"] == "F" and meta["routed_to"] == "B"

    organic = variant.run(pieces["t02"], tmp_path / "runs/r/t02/F", 2)
    assert {c.meta["routed_to"] for c in organic.candidates} == {"C"}
    assert (
        "fallback" not in organic.notes and organic.candidates[0].meta["router"]["fallback"] is None
    )


def test_end_to_end_run_eval_report(
    stubs: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = _write_sample(tmp_path)
    runs = tmp_path / "runs"
    cli = CliRunner()
    common = ["--run-id", "it", "--runs-root", str(runs)]

    result = cli.invoke(
        app, ["run", "--variants", "FAKE,A,B,C,D,F", "--sample", str(sample), *common]
    )
    assert result.exit_code == 0, result.output
    run_meta = json.loads((runs / "it/meta.json").read_text())
    assert run_meta["errors"] == []
    assert {(r["piece_id"], r["variant"]) for r in run_meta["results"]} == {
        (p, v) for p in ("t01", "t02") for v in ("FAKE", "A", "B", "C", "D", "F")
    }
    f_meta = json.loads((runs / "it/t02/F/cand_1/meta.json").read_text())
    assert f_meta["variant"] == "F" and f_meta["routed_to"] == "C"
    assert "rectilinear" in f_meta["router"] and "cost_usd" in f_meta["router"]
    # Post-processing is applied to every candidate; without Blender it is recorded, not fatal.
    cand_metas = [json.loads(p.read_text()) for p in runs.glob("it/*/*/cand_*/meta.json")]
    assert len(cand_metas) == 2 * 2 * 6
    assert all(m["post"] == {"ok": False, "reason": "sin Blender"} for m in cand_metas)
    assert not list(runs.glob("it/*/*/cand_*/model_post.glb"))

    # Renders as a previous Blender pass would have left them (eval runs with --no-render).
    for cand_dir in runs.glob("it/*/*/cand_*"):
        renders = cand_dir / "renders"
        renders.mkdir(exist_ok=True)
        for view in VIEWS:
            Image.new("RGB", (64, 64), (200, 200, 200)).save(renders / f"{view}.png")

    judge = StubVLM()
    monkeypatch.setattr(eval_module, "_default_judge", lambda: (judge, None))
    result = cli.invoke(app, ["eval", "--no-render", "--sample", str(sample), *common])
    assert result.exit_code == 0, result.output
    records = [
        json.loads(line) for line in (runs / "it/eval/scores.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2 * 2 * 6
    assert all(r["status"] == "scored" and r["geometry"] for r in records)
    assert (runs / "it/eval/blind_sheet.csv").is_file()
    # F's delegate folders (F/route_<X>/cand_*) are not discovered as variants of their own.
    assert {r["variant"] for r in records} == {"FAKE", "A", "B", "C", "D", "F"}

    result = cli.invoke(app, ["report", *common])
    assert result.exit_code == 0, result.output
    report = (runs / "it/eval/report.md").read_text(encoding="utf-8")
    assert "| Variante |" in report
    for variant in ("FAKE", "A", "B", "C", "D", "F"):
        assert f"| {variant} |" in report
    assert "Denominador:" in report


def test_run_postprocesses_every_candidate_and_eval_uses_model_post(
    stubs: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.post.blender_post import PostResult

    calls: list[Path] = []

    def fake_postprocess(glb_in: Path, glb_out: Path, piece: Any, **_: Any) -> PostResult:
        calls.append(Path(glb_in))
        shutil.copyfile(glb_in, glb_out)
        return PostResult(
            glb_path=Path(glb_out),
            meta_path=Path(glb_out).with_name("post_meta.json"),
            errors={"width": 0.01, "height": 0.0, "depth": -0.01},
            tris_before=12,
            tris_after=12,
            textures=[],
            seconds=0.5,
            scale_factor=1.0,
            errors_axis={"x": 0.01, "y": 0.0, "z": -0.01},
        )

    monkeypatch.setattr(cli_module, "postprocess", fake_postprocess)
    sample = _write_sample(tmp_path)
    runs = tmp_path / "runs"
    common = ["--run-id", "pp", "--runs-root", str(runs)]
    cli = CliRunner()
    result = cli.invoke(app, ["run", "--variants", "FAKE,A", "--sample", str(sample), *common])
    assert result.exit_code == 0, result.output

    cand_dirs = sorted(runs.glob("pp/*/*/cand_*"))
    assert len(cand_dirs) == 2 * 2 * 2 and len(calls) == len(cand_dirs)
    for cand_dir in cand_dirs:
        post = json.loads((cand_dir / "meta.json").read_text())["post"]
        assert post["ok"] is True and post["draco"] is False
        assert post["triangles_before"] == 12 and post["errors"]["width"] == 0.01
        assert (cand_dir / "model_post.glb").is_file()

    monkeypatch.setattr(eval_module, "_default_judge", lambda: (StubVLM(), None))
    result = cli.invoke(app, ["eval", "--no-render", "--sample", str(sample), *common])
    assert result.exit_code == 0, result.output
    records = [
        json.loads(line) for line in (runs / "pp/eval/scores.jsonl").read_text().splitlines()
    ]
    assert len(records) == len(cand_dirs)
    assert all(r["glb_path"].endswith("model_post.glb") for r in records)
    assert all(r["geometry"]["source"] == "trimesh" for r in records)


def test_run_no_post_skips_postprocessing(
    stubs: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: Any, **__: Any) -> None:
        raise AssertionError("postprocess no debe llamarse con --no-post")

    monkeypatch.setattr(cli_module, "postprocess", boom)
    sample = _write_sample(tmp_path)
    runs = tmp_path / "runs"
    result = CliRunner().invoke(
        app,
        ["run", "--variants", "FAKE", "--no-post", "--sample", str(sample)]
        + ["--run-id", "np", "--runs-root", str(runs)],
    )
    assert result.exit_code == 0, result.output
    metas = [json.loads(p.read_text()) for p in runs.glob("np/*/*/cand_*/meta.json")]
    assert metas and all("post" not in m for m in metas)
