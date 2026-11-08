"""CLI wiring of the pre-GTM polish: ``deliver``, ``refine``, ``report --sheets``,
``--scale-tolerance``, F's preflight without the VLM key and photo validation.

Offline: FAKE variants, a fake ``postprocess`` and a fake ``run_blender_script``."""

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
from harness.core import registry
from harness.core.blender import BlenderNotAvailable, BlenderRun
from harness.core.models import CSV_COLUMNS
from harness.core.variant import FakeVariant
from harness.eval.render import VIEWS
from harness.post import blender_post, bpy_deliver
from harness.post import deliver as post_deliver
from harness.post.blender_post import PostResult
from harness.prep import clean

FIXTURES = Path(__file__).parent / "fixtures"
CUBE = FIXTURES / "cube.glb"
SHEETS = FIXTURES / "sheets"


# --- helpers ---------------------------------------------------------------------------------


def _photo(path: Path, box: tuple[int, int, int, int] = (300, 300, 900, 900)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1200, 1200), (255, 255, 255))
    ImageDraw.Draw(img).rectangle(box, fill=(40, 30, 20))
    img.save(path, quality=95)
    return path


def _sample(root: Path, dims: dict[str, tuple[int, int, int]] | None = None) -> Path:
    dims = dims or {"t01": (60, 40, 40), "t02": (70, 80, 75)}
    rows = []
    for pid, (w, h, d) in dims.items():
        rows.append(
            {
                "id": pid,
                "name": f"Pieza {pid}",
                "store": "Tienda",
                "source_url": f"https://example.com/{pid}",
                "category": "macizo_mate",
                "images": str(_photo(root / f"images/{pid}/1.jpg")),
                "width_cm": str(w),
                "height_cm": str(h),
                "depth_cm": str(d),
                "description": "Pieza de prueba",
                "rectilinear": "true",
            }
        )
    path = root / "sample.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _fake_postprocess(calls: list[dict[str, Any]], *, error: float = 0.05):
    """Uniform scale leaves ``error`` on depth; ``fit_box`` (guard 10 %) removes it."""

    def fake(glb_in: Path, glb_out: Path, piece: Any, **kwargs: Any) -> PostResult:
        calls.append(kwargs)
        shutil.copyfile(glb_in, glb_out)
        before = {"width": 0.0, "height": 0.0, "depth": error}
        applied = bool(kwargs.get("fit_box")) and error <= kwargs.get("fit_guard", 0.10)
        return PostResult(
            glb_path=Path(glb_out),
            meta_path=Path(glb_out).with_name("post_meta.json"),
            errors={"width": 0.0, "height": 0.0, "depth": 0.0 if applied else error},
            tris_before=12,
            tris_after=12,
            textures=[],
            seconds=0.1,
            scale_factor=1.0,
            fit_box_applied=applied,
            errors_before_fit=before,
            raw={"fit_box_requested": bool(kwargs.get("fit_box")), "fit_skip_reason": None},
        )

    return fake


def _fake_blender(calls: list[list[str]], glb_bytes: int = 1_000_000):
    """``run_blender_script`` stand-in for ``bpy_deliver.py``."""

    def fake(script: Path, args: list[str], timeout: int = 600, blender_bin=None) -> BlenderRun:
        assert script == post_deliver.BPY_DELIVER_SCRIPT
        ns = bpy_deliver.parse_args(args)
        calls.append(args)
        Path(ns.out_glb).write_bytes(b"\0" * glb_bytes)
        Path(ns.out_usdz).write_bytes(b"\0" * 2_000_000)
        meta = {
            "glb_bytes": glb_bytes,
            "usdz_bytes": 2_000_000,
            "usdz_error": None,
            "tris_before": 95_118,
            "tris_after": min(ns.max_tris, 58_798),
            "textures": [],
            "seconds": 1.0,
        }
        Path(ns.meta).write_text(json.dumps(meta), encoding="utf-8")
        return BlenderRun(["blender", *args], 0, "ok", "", 1.0)

    return fake


class StubJudge:
    total_cost_usd = 0.0
    last_model = "stub"

    def ask_json(self, prompt: str, images: list[Path], schema_hint: str) -> dict[str, Any]:
        return {"parecido": 5, "geometria": 4, "materiales": 4, "comentario": "correcto"}


def _fake_renders(runs: Path, run_id: str) -> None:
    for cand_dir in runs.glob(f"{run_id}/*/*/cand_*"):
        renders = cand_dir / "renders"
        renders.mkdir(exist_ok=True)
        for view in VIEWS:
            Image.new("RGB", (64, 64), (200, 200, 200)).save(renders / f"{view}.png")


def _records(runs: Path, run_id: str) -> list[dict[str, Any]]:
    path = runs / run_id / "eval/scores.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.chdir(tmp_path)
    post_calls: list[dict[str, Any]] = []
    blender_calls: list[list[str]] = []
    monkeypatch.setattr(cli_module, "postprocess", _fake_postprocess(post_calls))
    monkeypatch.setattr(blender_post, "postprocess", _fake_postprocess(post_calls))
    monkeypatch.setattr(post_deliver, "run_blender_script", _fake_blender(blender_calls))
    monkeypatch.setattr(eval_module, "_default_judge", lambda: (StubJudge(), None))
    return {
        "sample": _sample(tmp_path),
        "runs": tmp_path / "runs",
        "post_calls": post_calls,
        "blender_calls": blender_calls,
    }


def _invoke(*args: str) -> Any:
    return CliRunner().invoke(app, list(args))


# --- end to end ------------------------------------------------------------------------------


def test_run_refine_deliver_report_with_human_sheet(env: dict[str, Any], tmp_path: Path) -> None:
    sample, runs = str(env["sample"]), env["runs"]
    common = ["--run-id", "e2e", "--runs-root", str(runs)]

    # run: FAKE, post without fit-box → 5 % residual on depth (between tolerance and guard).
    result = _invoke("run", "--variants", "FAKE", "--sample", sample, "--skip-preflight", *common)
    assert result.exit_code == 0, result.output
    meta = json.loads((runs / "e2e/t01/FAKE/cand_1/meta.json").read_text())
    assert meta["post"]["fit_box_requested"] is False and meta["post"]["fit_box_applied"] is False

    # refine: dry run first (nothing applied), then the free fit-to-box only.
    result = _invoke(
        "refine", "--piece", "t01", "--candidate", "1", "--dry-run", "--sample", sample, *common
    )
    assert result.exit_code == 0, result.output
    assert "ajuste a la caja (gratis)" in result.output and "--dry-run" in result.output
    assert not (runs / "e2e/t01/FAKE/cand_1/refine.json").exists()

    result = _invoke(
        "refine",
        "--piece",
        "t01",
        "--variant",
        "FAKE",
        "--candidate",
        "1",
        "--sample",
        sample,
        *common,
    )
    assert result.exit_code == 0, result.output
    assert "ajuste a la caja (gratis) en cand_1: hecho" in result.output
    assert "0 acción(es) de pago, coste 0,00 USD" in result.output
    meta = json.loads((runs / "e2e/t01/FAKE/cand_1/meta.json").read_text())
    assert meta["post"]["fit_box_applied"] is True
    history = json.loads((runs / "e2e/t01/FAKE/cand_1/refine.json").read_text())["history"]
    assert [s["action"] for s in history[0]["steps"]] == ["fit_box"]
    assert history[0]["issues_after"] == []

    # deliver: Blender mocked; one folder per piece under --out-dir.
    out = tmp_path / "deliver"
    result = _invoke(
        "deliver",
        "--pieces",
        "t01",
        "--variant",
        "FAKE",
        "--candidate",
        "1",
        "--out-dir",
        str(out),
        "--sample",
        sample,
        *common,
    )
    assert result.exit_code == 0, result.output
    assert "GLB web: 1,00 MB" in result.output and "dentro del límite" in result.output
    assert "USDZ: 2,00 MB" in result.output and "95.118 → 58.798" in result.output
    assert (out / "t01/viewer.html").is_file() and (out / "t01/deliver_meta.json").is_file()
    assert "http.server" in result.output

    # eval + report with one human sheet filled from the run's own blind sheet.
    _fake_renders(runs, "e2e")
    result = _invoke("eval", "--no-render", "--sample", sample, *common)
    assert result.exit_code == 0, result.output
    sheet = tmp_path / "marta.csv"
    with (runs / "e2e/eval/blind_sheet.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row.update(parecido="4", geometria="4", materiales="4", escala="", apto="sí")
    with sheet.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = _invoke("report", "--sheets", str(sheet), *common)
    assert result.exit_code == 0, result.output
    report = (runs / "e2e/eval/report.md").read_text(encoding="utf-8")
    assert "Tolerancia de escala: 3 %." in report
    assert "## Jueces humanos" in report and "marta" in report
    assert "juez automático" in report


# --- report --sheets -------------------------------------------------------------------------


def _evaluated_run(env: dict[str, Any], run_id: str, *extra: str) -> list[str]:
    common = ["--run-id", run_id, "--runs-root", str(env["runs"])]
    sample = str(env["sample"])
    result = _invoke("run", "--variants", "FAKE", "--no-post", "--sample", sample, *common)
    assert result.exit_code == 0, result.output
    _fake_renders(env["runs"], run_id)
    result = _invoke("eval", "--no-render", "--sample", sample, *extra, *common)
    assert result.exit_code == 0, result.output
    return common


def test_report_sheets_t5_fixtures(env: dict[str, Any], tmp_path: Path) -> None:
    env["sample"] = _sample(tmp_path, {p: (60, 40, 40) for p in ("t01", "t02", "t03")})
    common = _evaluated_run(env, "sh")  # 3 pieces × 2 candidates → B001…B006
    both = f"{SHEETS / 'ana.csv'},{SHEETS / 'luis.csv'}"  # luis.csv: ';' + BOM
    result = _invoke("report", "--sheets", both, *common)
    assert result.exit_code == 0, result.output
    assert "ana.csv: hoja sin eval_id" in result.output  # pre-stamp sheets: accepted, warned
    report = (env["runs"] / "sh/eval/report.md").read_text(encoding="utf-8")
    assert "## Jueces humanos" in report and "| ana |" in report and "| luis |" in report
    assert "### Acuerdo entre jueces" in report

    # A run with only 4 candidates has no B005/B006: clear error, no traceback.
    env["sample"] = _sample(tmp_path)
    common = _evaluated_run(env, "sh2")
    result = _invoke("report", "--sheets", str(SHEETS / "luis.csv"), *common)
    assert result.exit_code == 1
    assert "blind_id sin entrada en la clave: B005, B006" in result.output
    assert "otra ejecución" in result.output and "Traceback" not in result.output

    result = _invoke("report", "--sheets", "no-existe.csv", *common)
    assert result.exit_code == 1 and "No existe la hoja" in result.output


# --- --scale-tolerance -----------------------------------------------------------------------


def test_scale_tolerance_flips_apt(
    env: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The cube scaled uniformly to 100 cm leaves 100/96 − 1 ≈ 4,2 % on depth.
    env["sample"] = _sample(tmp_path, {"t01": (100, 100, 96)})
    monkeypatch.setitem(registry._FACTORIES, "FAKE", lambda: FakeVariant(source_glb=CUBE))

    _evaluated_run(env, "tol")
    strict = _records(env["runs"], "tol")[0]
    assert strict["scale_tolerance"] == 0.03
    assert strict["scores"]["escala"] == 3 and strict["scores"]["apt"] is False
    assert strict["geometry"]["scale_ok"] is False

    common = _evaluated_run(env, "tol5", "--scale-tolerance", "0.05")
    loose = _records(env["runs"], "tol5")[0]
    assert loose["scale_tolerance"] == 0.05
    assert loose["scores"]["escala"] == 5 and loose["scores"]["apt"] is True
    assert loose["geometry"]["scale_ok"] is True
    assert _invoke("report", *common).exit_code == 0
    report = (env["runs"] / "tol5/eval/report.md").read_text(encoding="utf-8")
    assert "Tolerancia de escala: 5 %." in report

    result = _invoke("eval", "--scale-tolerance", "1.5", "--run-id", "tol5")
    assert result.exit_code == 2 and "--scale-tolerance" in result.output


def test_run_passes_scale_tolerance_from_env(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCALE_TOLERANCE", "0,04")
    result = _invoke(
        "run", "--variants", "FAKE", "--sample", str(env["sample"]), "--skip-preflight",
        "--run-id", "te", "--runs-root", str(env["runs"]),
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert env["post_calls"] and all(c["tolerance"] == 0.04 for c in env["post_calls"])


# --- F preflight and router options ----------------------------------------------------------


def test_f_preflight_needs_vlm_key_only_with_vlm_classifier(env: dict[str, Any]) -> None:
    common = ["--sample", str(env["sample"]), "--no-post", "--run-id", "pf"]
    result = _invoke("run", "--variants", "F", *common)
    assert result.exit_code == 2
    assert "Variante F: falta TRIPO_API_KEY, GEMINI_API_KEY" in result.output
    assert "ANTHROPIC_API_KEY" not in result.output

    result = _invoke("run", "--variants", "F", "--router-classifier", "vlm", *common)
    assert result.exit_code == 2
    assert "Variante F: falta ANTHROPIC_API_KEY, TRIPO_API_KEY, GEMINI_API_KEY" in result.output

    result = _invoke("run", "--variants", "F", "--organic-variant", "D", *common)
    assert result.exit_code == 2 and "Variante F: falta MESHY_API_KEY" in result.output

    result = _invoke("run", "--variants", "F", "--router-classifier", "magia", *common)
    assert result.exit_code == 2 and "--router-classifier" in result.output


def test_router_options_reach_the_variant(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, Any]] = []

    def factory(**options: Any) -> FakeVariant:
        seen.append(options)
        return FakeVariant(name="F")

    monkeypatch.setitem(registry._FACTORIES, "F", factory)
    result = _invoke(
        "run", "--variants", "F", "--router-classifier", "rules", "--organic-variant", "b",
        "--sample", str(env["sample"]), "--no-post", "--skip-preflight", "--run-id", "ro",
        "--runs-root", str(env["runs"]),
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert seen == [{"classifier": "rules", "organic_variant": "B"}]


def test_registry_builds_router_with_options() -> None:
    router = registry.get_variant("F", classifier="rules", organic_variant="D")
    assert router.classifier == "rules" and router.organic_variant == "D"
    assert registry.get_variant("F").classifier == "auto"
    with pytest.raises(ValueError):
        registry.get_variant("F", organic_variant="E")


# --- deliver ---------------------------------------------------------------------------------


def _posted_run(env: dict[str, Any], run_id: str) -> list[str]:
    common = ["--run-id", run_id, "--runs-root", str(env["runs"])]
    result = _invoke(
        "run", "--variants", "FAKE", "--sample", str(env["sample"]), "--skip-preflight", *common
    )
    assert result.exit_code == 0, result.output
    return common


def test_deliver_requires_choice_when_ambiguous_and_exit_codes(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    common = [*_posted_run(env, "dl"), "--sample", str(env["sample"])]
    result = _invoke("deliver", "--pieces", "t01", *common)  # FAKE has 2 candidates
    assert (
        result.exit_code == 1
        and "indica --candidate (candidatos con model_post.glb: 1, 2)" in result.output
    )
    assert env["blender_calls"] == []

    # Default output: the candidate's own folder.
    result = _invoke("deliver", "--pieces", "t01,t02", "--candidate", "2", *common)
    assert result.exit_code == 0, result.output
    assert (env["runs"] / "dl/t02/FAKE/cand_2/viewer.html").is_file()

    # Over the limit even after the retry → exit 1.
    calls: list[list[str]] = []
    monkeypatch.setattr(post_deliver, "run_blender_script", _fake_blender(calls, 6_000_000))
    result = _invoke("deliver", "--pieces", "t01", "--candidate", "1", *common)
    assert result.exit_code == 1 and "SUPERA el límite" in result.output and len(calls) == 2

    def no_blender(*_: Any, **__: Any) -> None:
        raise BlenderNotAvailable("BLENDER_BIN no definido")

    monkeypatch.setattr(post_deliver, "run_blender_script", no_blender)
    result = _invoke("deliver", "--pieces", "t01", "--candidate", "1", *common)
    assert result.exit_code == 2 and "necesita Blender" in result.output


# --- refine ----------------------------------------------------------------------------------


def _write_candidate(runs: Path, run_id: str, piece: str, variant: str, post: dict) -> Path:
    cand = runs / run_id / piece / variant / "cand_1"
    cand.mkdir(parents=True)
    shutil.copyfile(CUBE, cand / "model.glb")
    shutil.copyfile(CUBE, cand / "model_post.glb")
    meta = {"piece_id": piece, "variant": variant, "index": 1, "cost_usd": 0.0, "post": post}
    (cand / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return cand


BAD_POST = {
    "ok": True,
    "errors": {"width": 0.0, "height": -0.30, "depth": -0.15},
    "errors_before_fit": {"width": 0.0, "height": -0.30, "depth": -0.15},
    "fit_box_applied": False,
}


def test_refine_paid_action_without_key_exits_2(env: dict[str, Any]) -> None:
    runs = env["runs"]
    cand = _write_candidate(runs, "rf", "t01", "A", BAD_POST)
    common = ["--run-id", "rf", "--runs-root", str(runs), "--sample", str(env["sample"])]
    result = _invoke("refine", "--piece", "t01", *common)
    assert result.exit_code == 2
    assert "regenerar necesita TRIPO_API_KEY" in result.output
    assert not (cand / "refine.json").exists()  # aborted before any action

    result = _invoke("refine", "--piece", "t01", "--max-rounds", "0", *common)
    assert result.exit_code == 0, result.output
    assert "fuera de --max-rounds" in result.output and "ninguna acción aplicable" in result.output


def test_refine_imported_variant_is_not_regenerable(env: dict[str, Any]) -> None:
    runs = env["runs"]
    _write_candidate(runs, "rf", "t01", "MG_TRELLIS2", BAD_POST)
    common = ["--run-id", "rf", "--runs-root", str(runs), "--sample", str(env["sample"])]
    result = _invoke("refine", "--piece", "t01", "--variant", "MG_TRELLIS2", "--dry-run", *common)
    assert result.exit_code == 0, result.output
    assert "no regenerable: variante importada" in result.output

    result = _invoke("refine", "--piece", "t09", *common)
    assert result.exit_code == 1 and "Ningún candidato" in result.output


def test_refine_cost_goes_into_run_total(tmp_path: Path) -> None:
    run_root = tmp_path / "r"
    run_root.mkdir()
    (run_root / "meta.json").write_text(json.dumps({"total_cost_usd": 1.0}), encoding="utf-8")
    cli_module._add_refine_cost(run_root, 0.5)
    data = json.loads((run_root / "meta.json").read_text())
    assert data["total_cost_usd"] == 1.5 and data["refine_cost_usd"] == 0.5


# --- photo validation ------------------------------------------------------------------------


def _fake_remove_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    rgba.putalpha(image.convert("L").point(lambda v: 255 if v < 128 else 0))
    return rgba


def test_validar_explains_problems_and_survives_corrupt_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clean, "_remove_background", _fake_remove_background)
    good = _photo(tmp_path / "good.jpg")
    tiny = _photo(tmp_path / "tiny.jpg", (590, 590, 610, 610))
    garbage = tmp_path / "garbage.jpg"
    garbage.write_bytes(b"esto no es una imagen")
    truncated = tmp_path / "truncated.jpg"
    truncated.write_bytes(good.read_bytes()[:400])

    result = _invoke("validar", str(good))
    assert result.exit_code == 0, result.output
    assert "1/1 fotos cumplen" in result.output

    result = _invoke("validar", str(good), str(tiny), str(garbage), str(truncated))
    assert result.exit_code == 1
    out = result.output
    assert "Objeto demasiado pequeño" in out and "Requisitos de la foto:" in out
    assert out.count("La imagen no se puede leer") == 2
    assert "1/4 fotos cumplen" in out
    assert "Traceback" not in out

    result = _invoke("requisitos")
    assert result.exit_code == 0 and "1.000 px" in result.output


# --- polish round ----------------------------------------------------------------------------


def test_refine_labels_in_spanish_and_repost(env: dict[str, Any]) -> None:
    runs = env["runs"]
    _write_candidate(runs, "rl", "t01", "MG_X", {"ok": False, "reason": "sin Blender"})
    _write_candidate(runs, "rl", "t02", "A", BAD_POST)
    common = ["--run-id", "rl", "--runs-root", str(runs), "--sample", str(env["sample"])]
    result = _invoke("refine", "--piece", "all", "--variant", "mg_x", "--dry-run", *common)
    assert result.exit_code == 0, result.output
    assert "problema (geometría): sin postprocesado" in result.output
    assert "plan: re-postprocesado (gratis)" in result.output
    assert "ajuste a la caja" not in result.output

    result = _invoke("refine", "--piece", "t02", "--dry-run", *common)
    assert "problema (geometría)" in result.output and "(geometry)" not in result.output


def test_refine_failure_is_reported_and_earlier_cost_kept(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    import harness.refine as refine_module
    from harness.refine import RefineReport

    runs = env["runs"]
    for piece in ("t01", "t02"):
        _write_candidate(runs, "rc", piece, "MG_X", BAD_POST)
    (runs / "rc/meta.json").write_text(json.dumps({"total_cost_usd": 1.0}), encoding="utf-8")

    def fake_refine(run_id: str, piece_id: str, variant: str, candidate: int, **_: Any):
        if piece_id == "t02":
            raise httpx.ConnectError("sin red")
        return RefineReport(run_id, piece_id, variant, candidate, candidate, [], [], cost_usd=0.4)

    monkeypatch.setattr(refine_module, "refine_candidate", fake_refine)
    common = ["--run-id", "rc", "--runs-root", str(runs), "--sample", str(env["sample"])]
    result = _invoke("refine", "--piece", "t01,t02", "--max-rounds", "0", *common)
    assert result.exit_code == 1
    assert "error de red con el proveedor: sin red" in result.output
    assert "Traceback" not in result.output
    data = json.loads((runs / "rc/meta.json").read_text())
    assert data["refine_cost_usd"] == pytest.approx(0.4)
    assert data["total_cost_usd"] == pytest.approx(1.4)


def test_run_warns_when_router_options_without_f(env: dict[str, Any]) -> None:
    result = _invoke(
        "run", "--variants", "FAKE", "--router-classifier", "rules", "--no-post",
        "--sample", str(env["sample"]), "--run-id", "w", "--runs-root", str(env["runs"]),
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "--router-classifier solo afecta a la variante F" in result.stderr


def test_deliver_upper_cases_variant(env: dict[str, Any]) -> None:
    common = [*_posted_run(env, "up"), "--sample", str(env["sample"])]
    result = _invoke("deliver", "--pieces", "t01", "--variant", "fake", "--candidate", "1", *common)
    assert result.exit_code == 0, result.output
    assert "t01 · FAKE/cand_1" in result.output


# --- final fixes: stable blind ids, refine spend, deliver guard, settings ---------------------


def _read_key(runs: Path, run_id: str) -> dict[str, tuple[str, str, str, str]]:
    with (runs / run_id / "eval/blind_key.csv").open(encoding="utf-8") as fh:
        return {
            r["blind_id"]: (r["piece_id"], r["variant"], r["candidate"], r["eval_id"])
            for r in csv.DictReader(fh)
        }


def _filled_copy(runs: Path, run_id: str, dst: Path) -> Path:
    with (runs / run_id / "eval/blind_sheet.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row.update(parecido="4", geometria="4", materiales="4", apto="sí")
    with dst.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return dst


def test_eval_after_refine_keeps_blind_ids_and_rejects_foreign_sheet(
    env: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 20 % residual: above the fit guard → geometry issue → FAKE regenerates cand_3.
    monkeypatch.setattr(cli_module, "postprocess", _fake_postprocess(env["post_calls"], error=0.2))
    monkeypatch.setattr(
        blender_post, "postprocess", _fake_postprocess(env["post_calls"], error=0.2)
    )
    runs, sample = env["runs"], str(env["sample"])
    common = ["--run-id", "st", "--runs-root", str(runs)]
    result = _invoke("run", "--variants", "FAKE", "--sample", sample, "--skip-preflight", *common)
    assert result.exit_code == 0, result.output
    _fake_renders(runs, "st")
    assert _invoke("eval", "--no-render", "--sample", sample, *common).exit_code == 0
    first = _read_key(runs, "st")
    assert len(first) == 4 and len({v[3] for v in first.values()}) == 1
    old_sheet = _filled_copy(runs, "st", tmp_path / "marta.csv")

    result = _invoke(
        "refine", "--piece", "t01", "--variant", "FAKE", "--candidate", "1",
        "--max-rounds", "1", "--sample", sample, *common,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "regenerar (de pago) en cand_1: hecho → cand_3" in result.output

    _fake_renders(runs, "st")
    assert _invoke("eval", "--no-render", "--sample", sample, *common).exit_code == 0
    second = _read_key(runs, "st")
    for blind_id, row in first.items():
        assert second[blind_id] == row  # same candidate and same eval_id
    assert second["B005"][:3] == ("t01", "FAKE", "3")
    records = {(r["piece_id"], r["candidate"]): r for r in _records(runs, "st")}
    assert records[("t01", 3)]["refined"] is True
    assert records[("t01", 1)]["refined"] is True  # has refine.json
    assert records[("t02", 1)]["refined"] is False

    # The sheet dealt before the refinement still matches the key.
    result = _invoke("report", "--sheets", str(old_sheet), *common)
    assert result.exit_code == 0, result.output
    report = (runs / "st/eval/report.md").read_text(encoding="utf-8")
    assert "| Refinado |" in report and "2 candidatos de refinado" in report

    # A sheet dealt from another run's key is rejected, naming both eval_ids.
    other = ["--run-id", "ot", "--runs-root", str(runs)]
    assert (
        _invoke("run", "--variants", "FAKE", "--no-post", "--sample", sample, *other).exit_code == 0
    )
    _fake_renders(runs, "ot")
    assert _invoke("eval", "--no-render", "--sample", sample, *other).exit_code == 0
    foreign = _filled_copy(runs, "ot", tmp_path / "luis.csv")
    foreign_id = next(iter(_read_key(runs, "ot").values()))[3]
    current_id = second["B001"][3]
    assert foreign_id != current_id
    result = _invoke("report", "--sheets", str(foreign), *common)
    assert result.exit_code == 1
    assert f"es de otra evaluación (eval_id {foreign_id})" in result.output
    assert f"clave actual tiene eval_id {current_id}" in result.output
    assert "Traceback" not in result.output


def test_deliver_refuses_without_ok_post_and_records_provenance(env: dict[str, Any]) -> None:
    runs = env["runs"]
    common = [*_posted_run(env, "dp"), "--sample", str(env["sample"])]
    cand = runs / "dp/t01/FAKE/cand_1"
    meta = json.loads((cand / "meta.json").read_text())
    meta["post"] = {"ok": False, "reason": "timeout de Blender (600 s)"}
    (cand / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    result = _invoke("deliver", "--pieces", "t01", "--candidate", "1", *common)
    assert result.exit_code == 1
    assert "el postprocesado no consta como correcto" in result.output
    assert "timeout de Blender" in result.output and env["blender_calls"] == []

    del meta["post"]
    (cand / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    result = _invoke("deliver", "--pieces", "t01", "--candidate", "1", *common)
    assert result.exit_code == 1 and "no consta como correcto" in result.output

    result = _invoke("deliver", "--pieces", "t01", "--candidate", "2", *common)
    assert result.exit_code == 0, result.output
    deliver_meta = json.loads((runs / "dp/t01/FAKE/cand_2/deliver_meta.json").read_text())
    assert {k: deliver_meta[k] for k in ("run_id", "piece_id", "variant", "candidate")} == {
        "run_id": "dp",
        "piece_id": "t01",
        "variant": "FAKE",
        "candidate": 2,
    }


def test_refine_parametric_candidates_are_not_regenerable(env: dict[str, Any]) -> None:
    runs = env["runs"]
    _write_candidate(runs, "rp", "t01", "E", BAD_POST)
    f_cand = _write_candidate(runs, "rp", "t02", "F", BAD_POST)
    f_meta = json.loads((f_cand / "meta.json").read_text())
    (f_cand / "meta.json").write_text(json.dumps({**f_meta, "routed_to": "E"}), encoding="utf-8")
    common = ["--run-id", "rp", "--runs-root", str(runs), "--sample", str(env["sample"])]
    result = _invoke("refine", "--piece", "all", "--dry-run", *common)
    assert result.exit_code == 0, result.output
    assert "no regenerable: variante E (paramétrica)" in result.output
    assert "no regenerable: F enrutada a E" in result.output

    result = _invoke("refine", "--piece", "all", *common)  # F would need keys if it regenerated
    assert result.exit_code == 0, result.output
    assert result.output.count("regenerar (de pago) en cand_1: omitido") == 2
    assert "0 acción(es) de pago, coste 0,00 USD" in result.output


def test_refine_corrupt_candidate_meta_exits_1(env: dict[str, Any]) -> None:
    runs = env["runs"]
    cand = _write_candidate(runs, "rc", "t01", "A", BAD_POST)
    (cand / "meta.json").write_text("{roto", encoding="utf-8")
    common = ["--run-id", "rc", "--runs-root", str(runs), "--sample", str(env["sample"])]
    result = _invoke("refine", "--piece", "t01", "--dry-run", *common)
    assert result.exit_code == 1
    assert "t01/A/cand_1: no se puede leer meta.json" in result.output
    assert "Traceback" not in result.output and not isinstance(result.exception, ValueError)


def test_refine_prefers_recorded_tolerance_and_says_which(env: dict[str, Any]) -> None:
    runs = env["runs"]
    post = {**BAD_POST, "errors": {"width": 0.04}, "errors_before_fit": {"width": 0.04}}
    _write_candidate(runs, "rt", "t01", "A", post)
    common = ["--run-id", "rt", "--runs-root", str(runs), "--sample", str(env["sample"])]
    args = ["refine", "--piece", "t01", "--dry-run", *common]
    result = _invoke(*args)
    assert "tolerancia de escala: 3 % (SCALE_TOLERANCE de .env" in result.output
    assert "problema (escala)" in result.output

    row = {"piece_id": "t01", "variant": "A", "candidate": 1, "scale_tolerance": 0.05}
    (runs / "rt/eval").mkdir(parents=True, exist_ok=True)
    (runs / "rt/eval/scores.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    result = _invoke(*args)
    assert result.exit_code == 0, result.output
    assert "tolerancia de escala: 5 % (registrada en scores.jsonl" in result.output
    assert "sin problemas detectados" in result.output

    result = _invoke(*args, "--scale-tolerance", "0.03")
    assert "tolerancia de escala: 3 % (--scale-tolerance)" in result.output
    assert "problema (escala)" in result.output


def test_invalid_env_tolerance_exits_2_without_traceback(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCALE_TOLERANCE", "tres")
    runs, sample = env["runs"], str(env["sample"])
    _write_candidate(runs, "bad", "t01", "A", BAD_POST)
    common = ["--run-id", "bad", "--runs-root", str(runs), "--sample", sample]
    calls = [
        ["run", "--variants", "FAKE", "--no-post", *common],
        ["run", "--variants", "FAKE", "--no-post", "--scale-tolerance", "0.05", *common],
        ["eval", "--no-render", *common],
        ["refine", "--piece", "t01", *common],
    ]
    for args in calls:
        result = _invoke(*args)
        assert result.exit_code == 2, (args, result.output)
        assert "SCALE_TOLERANCE" in result.output and "Traceback" not in result.output
        assert not isinstance(result.exception, ValueError)
