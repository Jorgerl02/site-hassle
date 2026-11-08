from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import trimesh
from PIL import Image

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.config import Settings
from harness.core.models import GeometryMetrics, Piece
from harness.eval import build_report, evaluate_run
from harness.eval.blind_sheet import (
    CandidateRef,
    assign_blind_ids,
    read_blind_key,
    write_blind_sheet,
)
from harness.eval.geometry import match_extents, measure, measure_glb
from harness.eval.judge import (
    JudgeError,
    escala_from_error,
    judge_candidate,
    scores_from_answer,
)
from harness.eval.render import VIEWS, render_views
from harness.eval.report import NOISE_NOTE, read_scores, summarize

VARIANT_NAMES = ("A", "B", "C", "D", "E", "F", "FAKE")


class StubVLM:
    def __init__(self, answer: dict[str, Any]) -> None:
        self.answer = answer
        self.calls: list[tuple[str, list[Path], str]] = []
        self.total_cost_usd = 0.0

    def ask_json(self, prompt: str, images: list[Path], schema_hint: str) -> dict[str, Any]:
        self.calls.append((prompt, list(images), schema_hint))
        self.total_cost_usd += 0.01
        return dict(self.answer)


def _metrics(max_err: float) -> GeometryMetrics:
    return GeometryMetrics(
        width_cm=1,
        height_cm=1,
        depth_cm=1,
        err_width=-max_err,
        err_height=0,
        err_depth=0,
        watertight=True,
        n_components=1,
        n_faces=12,
    )


def _png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), "white").save(path)
    return path


# ---------- geometry ----------


def test_geometry_exact_box(piece: Piece) -> None:
    box = trimesh.creation.box(extents=(1.20, 0.75, 0.60))
    m = measure(box, piece)
    assert (m.width_cm, m.height_cm, m.depth_cm) == pytest.approx((120, 75, 60))
    assert m.max_error == pytest.approx(0, abs=1e-9)
    assert m.scale_ok and m.watertight
    assert m.n_components == 1 and m.n_faces == 12


def test_geometry_wrong_scale_signed_negative(piece: Piece) -> None:
    box = trimesh.creation.box(extents=(1.08, 0.675, 0.54))  # 10 % too small
    m = measure(box, piece)
    assert m.err_width == pytest.approx(-0.10)
    assert m.err_height == pytest.approx(-0.10)
    assert m.err_depth == pytest.approx(-0.10)
    assert not m.scale_ok


def test_geometry_axes_matched_by_sorted_size(piece: Piece) -> None:
    # Lying on its side: height along X, width along Z.
    box = trimesh.creation.box(extents=(0.75, 0.60, 1.20))
    m = measure(box, piece)
    assert m.scale_ok
    assert match_extents((10.0, 30.0, 20.0), (5.0, 1.0, 3.0)) == (30.0, 10.0, 20.0)


def test_geometry_from_glb_scene_and_components(tmp_path: Path, piece: Piece) -> None:
    scene = trimesh.Scene()
    scene.add_geometry(trimesh.creation.box(extents=(1.2, 0.75, 0.6)))
    small = trimesh.creation.box(extents=(0.1, 0.1, 0.1))
    small.apply_translation((0.2, 0.0, 0.0))
    scene.add_geometry(small)
    glb = tmp_path / "two.glb"
    scene.export(glb)
    m = measure_glb(glb, piece)
    assert m.n_components == 2 and m.n_faces == 24 and m.scale_ok


def test_geometry_cube_fixture(cube_glb: Path, piece: Piece) -> None:
    m = measure_glb(cube_glb, piece)
    assert m.width_cm == pytest.approx(100)
    assert m.err_height == pytest.approx(100 / 75 - 1)


# ---------- judge ----------


@pytest.mark.parametrize(
    ("err", "expected"), [(0.0, 5), (0.0299, 5), (0.03, 3), (0.0999, 3), (0.10, 1), (0.5, 1)]
)
def test_escala_thresholds(err: float, expected: int) -> None:
    assert escala_from_error(err) == expected


def test_judge_with_stub_vlm(tmp_path: Path) -> None:
    vlm = StubVLM({"parecido": 5, "geometria": 4, "materiales": 4, "comentario": "ok"})
    photos = [_png(tmp_path / "photo.png")]
    renders = [_png(tmp_path / "blind" / "B007" / f"{v}.png") for v in VIEWS]
    scores = judge_candidate(
        vlm, blind_id="B007", photos=photos, renders=renders, geometry=_metrics(0.01)
    )
    assert (scores.parecido, scores.geometria, scores.materiales, scores.escala) == (5, 4, 4, 5)
    assert scores.apt and scores.comentario == "ok"
    prompt, images, schema = vlm.calls[0]
    assert "B007" in prompt and images == [*photos, *renders]
    assert '"parecido"' in schema and "escala" not in schema
    for name in VARIANT_NAMES:
        assert f"variante {name}" not in prompt.lower()


def test_judge_not_apt_when_scale_bad(tmp_path: Path) -> None:
    vlm = StubVLM({"parecido": 5, "geometria": 5, "materiales": 5, "comentario": ""})
    scores = judge_candidate(vlm, blind_id="B001", photos=[], renders=[], geometry=_metrics(0.05))
    assert scores.escala == 3 and not scores.apt


def test_judge_rejects_bad_json() -> None:
    with pytest.raises(JudgeError):
        scores_from_answer({"parecido": 6, "geometria": 4, "materiales": 4}, 5)
    with pytest.raises(JudgeError):
        scores_from_answer({"parecido": "4", "geometria": 4, "materiales": 4}, 5)


# ---------- render ----------


def test_render_without_blender_raises(tmp_path: Path, cube_glb: Path) -> None:
    with pytest.raises(BlenderNotAvailable):
        render_views(cube_glb, tmp_path / "renders")


def test_render_real_blender(tmp_path: Path, cube_glb: Path) -> None:
    blender = Settings.load(env_file=None).blender_bin
    if blender is None:
        pytest.skip("BLENDER_BIN no definido")
    paths = render_views(cube_glb, tmp_path / "renders", blender_bin=blender)
    assert [p.stem for p in paths] == list(VIEWS)
    for p in paths:
        with Image.open(p) as im:
            assert im.size == (1024, 1024)


# ---------- blind sheet ----------


def test_blind_sheet_hides_variant_and_key_recovers(tmp_path: Path) -> None:
    refs = [
        CandidateRef(pid, variant, cand)
        for pid in ("p01", "p02")
        for variant in ("A", "B", "FAKE")
        for cand in (1, 2)
    ]
    assigned = assign_blind_ids(refs, seed=7)
    assert assign_blind_ids(list(reversed(refs)), seed=7) == assigned  # order independent
    assert [b for b, _ in assigned][:2] == ["B001", "B002"]
    assert [r for _, r in assigned] != sorted(refs, key=lambda r: (r.piece_id, r.variant))
    entries = [
        (b, r, [], [tmp_path / "blind" / b / f"{v}.png" for v in VIEWS]) for b, r in assigned
    ]
    sheet, key = tmp_path / "blind_sheet.csv", tmp_path / "blind_key.csv"
    write_blind_sheet(sheet, key, entries)

    with sheet.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(refs)
    for row in rows:
        for col in ("parecido", "geometria", "materiales", "escala", "apto", "comentario"):
            assert row[col] == ""
        assert row["render_front"] == f"blind/{row['blind_id']}/front.png"
    text = sheet.read_text(encoding="utf-8")
    for name in ("FAKE", "variant", ",A,", ",B,", "/A/", "/B/"):
        assert name not in text
    assert read_blind_key(key) == dict(assigned)


# ---------- report ----------

CATS = ("macizo_mate", "tapizado", "metal_vidrio", "patas_finas")


def _records(variant: str, apt_per_category: dict[str, tuple[int, int]]) -> list[dict]:
    out = []
    for category, (apt, n) in apt_per_category.items():
        for i in range(n):
            good = i < apt
            out.append(
                {
                    "piece_id": f"{category}_{i}",
                    "variant": variant,
                    "candidate": 1,
                    "category": category,
                    "status": "scored",
                    "cost_usd": 0.5,
                    "seconds": 10.0,
                    "scores": {
                        "parecido": 5 if good else 2,
                        "geometria": 4,
                        "materiales": 4,
                        "escala": 5,
                        "apt": good,
                        "comentario": "",
                    },
                }
            )
    return out


def _write_scores(tmp_path: Path, records: list[dict]) -> Path:
    path = storage.scores_path("r1", tmp_path)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def test_report_winner_rule(tmp_path: Path) -> None:
    records = (
        # A: 3/10 per category -> 12/40 = 30 %
        _records("A", {c: (3, 10) for c in CATS})
        # W: 70 % in two categories, 40 % in two -> 22/40 = 55 % (+25 pp) -> wins
        + _records(
            "W",
            {
                "macizo_mate": (7, 10),
                "tapizado": (7, 10),
                "metal_vidrio": (4, 10),
                "patas_finas": (4, 10),
            },
        )
        # D: 70 % in two categories, 20 % elsewhere -> 18/40 = 45 % (+15, not > 15)
        + _records(
            "D",
            {
                "macizo_mate": (7, 10),
                "tapizado": (7, 10),
                "metal_vidrio": (2, 10),
                "patas_finas": (2, 10),
            },
        )
        # K: 100 % in one category, 60 % (not > 60) elsewhere -> +40 pp, 1 category
        + _records(
            "K",
            {
                "macizo_mate": (10, 10),
                "tapizado": (6, 10),
                "metal_vidrio": (6, 10),
                "patas_finas": (6, 10),
            },
        )
    )
    _write_scores(tmp_path, records)
    s = summarize(read_scores(storage.scores_path("r1", tmp_path)))
    assert s["A"].pct() == pytest.approx(30) and not s["A"].winner
    assert s["W"].delta_pp == pytest.approx(25) and s["W"].winner
    assert s["D"].delta_pp == pytest.approx(15) and not s["D"].winner
    assert s["K"].delta_pp == pytest.approx(40) and s["K"].categories_over() == ["macizo_mate"]
    assert not s["K"].winner
    assert s["W"].cost_per_piece == pytest.approx(0.5)
    assert s["W"].seconds_per_piece == pytest.approx(10.0)

    report = build_report("r1", runs_root=tmp_path).read_text(encoding="utf-8")
    assert "Variantes ganadoras: W." in report
    assert NOISE_NOTE in report
    assert "| A | 30,0 % (3/10)" in report and "línea base" in report
    assert "+25,0 pp" in report


def test_report_best_candidate_and_failed_generation() -> None:
    base = _records("A", {"tapizado": (0, 1)})
    second = dict(base[0], candidate=2, scores=dict(base[0]["scores"], apt=True))
    failed = {
        "piece_id": "x",
        "variant": "A",
        "category": "tapizado",
        "status": "generation_failed",
    }
    unscored = {
        "piece_id": "y",
        "variant": "A",
        "category": "tapizado",
        "status": "unscored",
        "scores": None,
        "cost_usd": 0.25,
        "seconds": 1.0,
    }
    s = summarize([*base, second, failed, unscored])["A"]
    assert s.apt_by_category["tapizado"] == (1, 2)  # piece apt via cand 2; failed = not apt
    assert s.unscored == 1
    assert s.cost_per_piece == pytest.approx((1.0 + 0.25) / 2)


def test_report_without_baseline_declares_no_winner() -> None:
    s = summarize(_records("W", {c: (10, 10) for c in CATS}))
    assert s["W"].delta_pp is None and not s["W"].winner


# ---------- end to end ----------


def _fake_run(tmp_path: Path, cube_glb: Path, piece: Piece) -> Path:
    runs = tmp_path / "runs"
    for variant in ("A", "B"):
        workdir = storage.variant_dir("run1", piece.id, variant, runs)
        for index in (1, 2):
            cand = storage.candidate_dir(workdir, index)
            shutil.copyfile(cube_glb, storage.model_path(cand))
            storage.write_meta(
                cand,
                {
                    "piece_id": piece.id,
                    "variant": variant,
                    "index": index,
                    "cost_usd": 0.25,
                    "seconds": 3.0,
                },
            )
            for view in VIEWS:
                _png(storage.renders_dir(cand) / f"{view}.png")
    storage.write_meta(
        storage.run_dir("run1", runs),
        {"run_id": "run1", "errors": [{"piece_id": piece.id, "variant": "C", "error": "boom"}]},
    )
    return runs


def test_evaluate_run_end_to_end(tmp_path: Path, cube_glb: Path) -> None:
    photo = _png(tmp_path / "photo.png")
    cube_piece = Piece(
        id="p01",
        name="Cubo",
        store="T",
        source_url="https://example.com",
        category="tapizado",
        images=[photo],
        width_cm=100,
        height_cm=100,
        depth_cm=100,
    )
    runs = _fake_run(tmp_path, cube_glb, cube_piece)
    vlm = StubVLM({"parecido": 4, "geometria": 4, "materiales": 5, "comentario": "bien"})

    scores_file = evaluate_run(
        "run1", runs_root=runs, judge=vlm, render=False, pieces=[cube_piece], seed=1
    )
    records = read_scores(scores_file)
    scored = [r for r in records if r["status"] == "scored"]
    assert len(scored) == 4 and len(vlm.calls) == 4
    assert {(r["variant"], r["candidate"]) for r in scored} == {
        ("A", 1),
        ("A", 2),
        ("B", 1),
        ("B", 2),
    }
    assert all(r["scores"]["apt"] and r["scores"]["escala"] == 5 for r in scored)
    assert all(r["geometry"]["scale_ok"] for r in scored)
    assert all(r["judge_cost_usd"] == pytest.approx(0.01) for r in scored)
    failed = [r for r in records if r["status"] == "generation_failed"]
    assert failed == [failed[0]] and failed[0]["variant"] == "C"

    # The judge never sees variant paths: images are the photo plus blind copies.
    for prompt, images, _ in vlm.calls:
        assert images[0] == photo
        assert all("/blind/B" in str(p) for p in images[1:])
        assert "/A/" not in prompt and "/B/" not in prompt

    sheet = storage.blind_sheet_path("run1", runs).read_text(encoding="utf-8")
    assert "/A/" not in sheet and "/B/" not in sheet
    key = read_blind_key(storage.blind_key_path("run1", runs))
    assert {r.variant for r in key.values()} == {"A", "B"}
    for blind_id in key:
        assert (storage.eval_dir("run1", runs) / "blind" / blind_id / "front.png").is_file()

    report = build_report("run1", runs_root=runs).read_text(encoding="utf-8")
    assert "| B |" in report and "Ninguna variante" in report


def test_evaluate_run_records_skip_reasons(
    tmp_path: Path, cube_glb: Path, piece: Piece, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # no repo .env: no API key, no Blender
    runs = _fake_run(tmp_path, cube_glb, piece)
    for png in runs.glob("**/renders/*.png"):
        png.unlink()
    scores_file = evaluate_run("run1", runs_root=runs, judge=None, render=True, pieces=[piece])
    records = [r for r in read_scores(scores_file) if r["status"] != "generation_failed"]
    assert records and all(r["status"] == "unscored" for r in records)
    assert all(any("render omitido" in x for x in r["reasons"]) for r in records)
    assert all(any("ANTHROPIC_API_KEY" in x for x in r["reasons"]) for r in records)
    assert all(r["geometry"] is not None and not r["geometry"]["scale_ok"] for r in records)


def test_evaluate_run_missing_run(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        evaluate_run("nope", runs_root=tmp_path, judge=StubVLM({}), pieces=[])
