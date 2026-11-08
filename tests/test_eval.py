from __future__ import annotations

import csv
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
import trimesh
from PIL import Image

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.models import GeometryMetrics, Piece
from harness.eval import build_report, evaluate_run
from harness.eval.blind_sheet import (
    CandidateRef,
    assign_blind_ids,
    read_blind_key,
    write_blind_sheet,
)
from harness.eval.geometry import (
    match_extents,
    measure,
    measure_candidate,
    measure_details,
    measure_glb,
)
from harness.eval.judge import (
    JudgeError,
    escala_from_error,
    judge_candidate,
    scores_from_answer,
)
from harness.eval.render import VIEWS, render_views
from harness.eval.report import DENOMINATOR_NOTE, NOISE_NOTE, read_scores, summarize

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


def test_geometry_uniform_scale_is_forgiven(piece: Piece) -> None:
    box = trimesh.creation.box(extents=(1.08, 0.675, 0.54))  # 10 % too small, same proportions
    m = measure(box, piece)
    assert m.max_error == pytest.approx(0, abs=1e-9) and m.scale_ok


def test_geometry_wrong_proportions_signed_negative(piece: Piece) -> None:
    box = trimesh.creation.box(extents=(1.20, 0.675, 0.60))  # height 10 % short
    m = measure(box, piece)
    assert m.err_width == pytest.approx(0)
    assert m.err_height == pytest.approx(-0.10)
    assert m.err_depth == pytest.approx(0)
    assert not m.scale_ok


def test_geometry_raw_and_prescaled_give_identical_metrics(tmp_path: Path, piece: Piece) -> None:
    raw = trimesh.creation.box(extents=(0.9, 0.5, 0.3))  # wrong proportions on purpose
    prescaled = raw.copy()
    prescaled.apply_scale(1 / 2.7)
    m_raw, m_pre = measure(raw, piece).model_dump(), measure(prescaled, piece).model_dump()
    assert m_raw == pytest.approx(m_pre, rel=1e-9, abs=1e-12)  # identical up to float rounding
    assert m_raw["err_height"] != pytest.approx(0)  # proportions are still measured
    raw_glb, pre_glb = tmp_path / "raw.glb", tmp_path / "model_post.glb"
    raw.export(raw_glb)
    prescaled.export(pre_glb)
    a, b = measure_candidate(raw_glb, piece), measure_candidate(pre_glb, piece)
    assert a.metrics and b.metrics and a.source == b.source == "trimesh"
    # GLB stores float32 vertices: equal up to float32 rounding.
    assert a.metrics.model_dump() == pytest.approx(b.metrics.model_dump(), rel=1e-5, abs=1e-6)
    assert a.raw_extents_cm == pytest.approx((90, 50, 30))
    assert a.scale_factor == pytest.approx(120 / 90)
    assert b.scale_factor == pytest.approx(120 / 90 * 2.7)


def test_geometry_sofa_at_native_one_metre_scale_gets_escala_5() -> None:
    sofa = Piece(
        id="s1", name="Sofá", store="T", source_url="https://example.com",
        category="tapizado", images=[Path("x.jpg")],
        width_cm=200, height_cm=80, depth_cm=90,
    )  # fmt: skip
    native = trimesh.creation.box(extents=(1.0, 0.40, 0.45))  # generator's unit-size output
    details = measure_details(native, sofa)
    assert details.metrics.max_error == pytest.approx(0, abs=1e-9)
    assert details.scale_factor == pytest.approx(2.0)
    assert escala_from_error(details.metrics.max_error) == 5


def test_geometry_rotation_about_vertical_is_forgiven(piece: Piece) -> None:
    # Turned 90° on the floor: width along Z, depth along X.
    box = trimesh.creation.box(extents=(0.60, 0.75, 1.20))
    m = measure(box, piece)
    assert (m.width_cm, m.height_cm, m.depth_cm) == pytest.approx((120, 75, 60))
    assert m.scale_ok


def test_geometry_chair_lying_on_its_side_detected() -> None:
    chair = Piece(
        id="c1", name="Silla", store="T", source_url="https://example.com",
        category="patas_finas", images=[Path("x.jpg")],
        width_cm=50, height_cm=90, depth_cm=50,
    )  # fmt: skip
    lying = trimesh.creation.box(extents=(0.90, 0.50, 0.50))  # Y extent 50 cm
    m = measure(lying, chair)
    assert m.height_cm == pytest.approx(50)
    assert m.err_height == pytest.approx((50 - 90) / 90)
    assert not m.scale_ok
    assert match_extents((90.0, 50.0, 50.0), chair) == (90.0, 50.0, 50.0)


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
    m = measure_glb(cube_glb, piece)  # 1 m cube rescaled by 120/100
    assert m.width_cm == pytest.approx(120)
    assert m.err_height == pytest.approx(120 / 75 - 1)


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
    assert (scores["parecido"], scores["geometria"], scores["materiales"]) == (5, 4, 4)
    assert scores["escala"] == 5 and scores["apt"] and scores["comentario"] == "ok"
    prompt, images, schema = vlm.calls[0]
    assert "B007" in prompt and images == [*photos, *renders]
    assert '"parecido"' in schema and "escala" not in schema
    for name in VARIANT_NAMES:
        assert f"variante {name}" not in prompt.lower()


def test_judge_not_apt_when_scale_bad(tmp_path: Path) -> None:
    vlm = StubVLM({"parecido": 5, "geometria": 5, "materiales": 5, "comentario": ""})
    scores = judge_candidate(vlm, blind_id="B001", photos=[], renders=[], geometry=_metrics(0.05))
    assert scores["escala"] == 3 and not scores["apt"]


def test_judge_without_geometry_still_scores_visual_axes() -> None:
    vlm = StubVLM({"parecido": 5, "geometria": 5, "materiales": 5, "comentario": "x"})
    scores = judge_candidate(vlm, blind_id="B002", photos=[], renders=[], geometry=None)
    assert scores["parecido"] == 5 and scores["escala"] is None and scores["apt"] is False
    assert len(vlm.calls) == 1


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
    blender = os.environ.get("HARNESS_BLENDER_TEST_BIN")
    if not blender:
        pytest.skip("HARNESS_BLENDER_TEST_BIN no definido (opt-in para tests con Blender)")
    paths = render_views(cube_glb, tmp_path / "renders", blender_bin=Path(blender))
    assert [p.stem for p in paths] == list(VIEWS)
    for p in paths:
        with Image.open(p) as im:
            assert im.size == (1024, 1024)


def test_render_real_blender_textured_pbr_shows_albedo(tmp_path: Path) -> None:
    """Opt-in: the cube fixture has no texture, so the Workbench albedo selection is only
    exercised with a textured PBR GLB (base colour + normal map at least) given in
    ``HARNESS_TEXTURED_GLB`` — e.g. a real Tripo/Meshy output, or Khronos' sample
    ``DamagedHelmet.glb``. No binary fixture is committed; see README, ``blender-test``."""
    blender = os.environ.get("HARNESS_BLENDER_TEST_BIN")
    textured = os.environ.get("HARNESS_TEXTURED_GLB")
    if not blender or not textured:
        pytest.skip("HARNESS_BLENDER_TEST_BIN y HARNESS_TEXTURED_GLB no definidos (opt-in)")
    paths = render_views(Path(textured), tmp_path / "renders", blender_bin=Path(blender))
    with Image.open(paths[0]) as im:
        pixels = [p for p in im.convert("RGB").getdata() if p != (255, 255, 255)]
    assert pixels, "render vacío"
    r, g, b = (sum(c[i] for c in pixels) / len(pixels) for i in range(3))
    # A tangent-space normal map averages ≈ (128, 128, 255): clearly blue-dominant.
    assert not (b > 200 and b - max(r, g) > 60), f"parece un mapa de normales: {(r, g, b)}"
    # Lighting floor: the old "Default" studio light left a mid-tone texture ~30 % darker
    # than its albedo (p04 MG_TRELLIS2: 0.30); paint.sl + 0.15 EV gives ≈ albedo (0.45).
    lum = sum(0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in pixels) / len(pixels)
    assert lum / 255 > 0.35, f"render demasiado oscuro: luminancia media {lum / 255:.3f}"


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
    broken = {
        "piece_id": "z",
        "variant": "A",
        "category": "tapizado",
        "status": "candidate_failed",
        "scores": None,
        "cost_usd": 0.25,
        "seconds": 1.0,
    }
    s = summarize([*base, second, failed, unscored, broken])["A"]
    # piece apt via cand 2; generation_failed and candidate_failed count as not apt;
    # the infrastructure-unscored piece is excluded.
    assert s.apt_by_category["tapizado"] == (1, 3)
    assert s.unscored == 1
    assert s.cost_per_piece == pytest.approx((1.0 + 0.25 + 0.25) / 3)


def test_report_states_denominator_rule(tmp_path: Path) -> None:
    _write_scores(tmp_path, _records("A", {"tapizado": (1, 2)}))
    report = build_report("r1", runs_root=tmp_path).read_text(encoding="utf-8")
    assert DENOMINATOR_NOTE in report and "Sin puntuar (infraestructura)" in report


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


def _cube_piece(tmp_path: Path) -> Piece:
    return Piece(
        id="p01", name="Cubo", store="T", source_url="https://example.com",
        category="tapizado", images=[_png(tmp_path / "photo.png")],
        width_cm=100, height_cm=100, depth_cm=100,
    )  # fmt: skip


def test_evaluate_run_unreadable_glb_uses_post_meta(tmp_path: Path, cube_glb: Path) -> None:
    piece = _cube_piece(tmp_path)
    runs = _fake_run(tmp_path, cube_glb, piece)
    cand = runs / "run1" / "p01" / "A" / "cand_1"
    storage.model_post_path(cand).write_bytes(b"glTF draco garbage")
    (cand / "post_meta.json").write_text(
        json.dumps({"errors": {"width": 0.01, "height": -0.02, "depth": 0.0}, "tris_after": 12}),
        encoding="utf-8",
    )
    cand2 = runs / "run1" / "p01" / "A" / "cand_2"
    storage.model_post_path(cand2).write_bytes(b"not a glb")  # no post_meta.json
    vlm = StubVLM({"parecido": 4, "geometria": 4, "materiales": 4, "comentario": ""})
    scores_file = evaluate_run("run1", runs_root=runs, judge=vlm, render=False, pieces=[piece])
    by_cand = {
        (r["variant"], r["candidate"]): r
        for r in read_scores(scores_file)
        if r["status"] != "generation_failed"
    }
    rec = by_cand[("A", 1)]
    assert rec["status"] == "scored" and rec["geometry"]["source"] == "post_meta"
    assert rec["geometry"]["err_height"] == pytest.approx(-0.02)
    assert rec["scores"]["escala"] == 5 and rec["scores"]["apt"]
    # Unreadable without post_meta: judged anyway (renders exist), escala None, not apt.
    rec2 = by_cand[("A", 2)]
    assert rec2["status"] == "scored" and rec2["geometry"] is None
    assert rec2["scores"]["escala"] is None and rec2["scores"]["apt"] is False
    assert any(r.startswith("sin geometría") for r in rec2["reasons"])
    assert len(vlm.calls) == 4


def test_evaluate_run_missing_glb_with_renders_is_judged(tmp_path: Path, cube_glb: Path) -> None:
    piece = _cube_piece(tmp_path)
    runs = _fake_run(tmp_path, cube_glb, piece)
    storage.model_path(runs / "run1" / "p01" / "B" / "cand_1").unlink()
    vlm = StubVLM({"parecido": 5, "geometria": 5, "materiales": 5, "comentario": ""})
    scores_file = evaluate_run("run1", runs_root=runs, judge=vlm, render=False, pieces=[piece])
    rec = next(r for r in read_scores(scores_file) if (r["variant"], r["candidate"]) == ("B", 1))
    assert rec["status"] == "scored" and rec["scores"]["escala"] is None
    assert rec["scores"]["apt"] is False
    assert any("sin geometría: no existe el modelo" in r for r in rec["reasons"])


def test_evaluate_run_missing_glb_without_renders_counts_not_apt(
    tmp_path: Path, cube_glb: Path
) -> None:
    piece = _cube_piece(tmp_path)
    runs = _fake_run(tmp_path, cube_glb, piece)
    cand = runs / "run1" / "p01" / "B" / "cand_1"
    storage.model_path(cand).unlink()
    for png in (cand / "renders").glob("*.png"):
        png.unlink()
    scores_file = evaluate_run(
        "run1", runs_root=runs, judge=StubVLM({}), render=False, pieces=[piece]
    )
    rec = next(r for r in read_scores(scores_file) if (r["variant"], r["candidate"]) == ("B", 1))
    assert rec["status"] == "candidate_failed"


def test_blind_dir_is_cleared_before_copy(tmp_path: Path) -> None:
    from harness.eval.blind_sheet import copy_blind_renders

    stale = _png(tmp_path / "eval" / "blind" / "B001" / "old.png")
    src = _png(tmp_path / "src" / "front.png")
    copies = copy_blind_renders([src], tmp_path / "eval", "B001")
    assert not stale.exists() and [c.name for c in copies] == ["front.png"]


def test_report_excludes_not_applicable_from_e_denominator(tmp_path: Path) -> None:
    applicable = _records("E", {"macizo_mate": (6, 8)})
    na = [
        {"piece_id": f"org_{i}", "variant": "E", "category": "tapizado",
         "status": "not_applicable", "from_run_meta": True, "candidate": None}
        for i in range(5)
    ]  # fmt: skip
    s = summarize([*applicable, *na])["E"]
    assert s.apt_total == (6, 8) and s.pct() == pytest.approx(75)
    assert s.not_applicable == 5 and s.unscored == 0 and s.applicable == 8
    assert s.n_pieces == 13
    _write_scores(tmp_path, [*applicable, *na])
    report = build_report("r1", runs_root=tmp_path).read_text(encoding="utf-8")
    assert "- E: 8/13 piezas aplicables" in report


def test_report_total_cost_minutes_and_topology(tmp_path: Path) -> None:
    records = _records("A", {"tapizado": (1, 2)})
    for rec, (wt, comps) in zip(records, [(True, 1), (False, 3)], strict=True):
        rec["geometry"] = {"source": "trimesh", "watertight": wt, "n_components": comps}
        rec["judge_cost_usd"] = 0.02
    f_rec = dict(_records("F", {"tapizado": (0, 1)})[0], router_cost_usd=0.1)
    _write_scores(tmp_path, [*records, f_rec])
    s = summarize(read_scores(storage.scores_path("r1", tmp_path)))
    assert s["A"].watertight_pct == pytest.approx(50) and s["A"].components_mean == 2
    report = build_report("r1", runs_root=tmp_path).read_text(encoding="utf-8")
    # generation 1.5 (incl. 0.1 router) + judge 0.04
    assert "**Coste total:** 1,54 USD = generación 1,40 USD + enrutado VLM (F) 0,10 USD" in report
    assert "+ juez VLM 0,04 USD" in report
    assert "10,0 s (0,2 min)" in report
    assert "% mallas cerradas" in report and "| 50 % | 2,0 |" in report


def test_evaluate_run_records_judge_model_and_scale(tmp_path: Path, cube_glb: Path) -> None:
    piece = _cube_piece(tmp_path)
    runs = _fake_run(tmp_path, cube_glb, piece)

    class ModelVLM(StubVLM):
        last_model = "claude-sonnet-5-5"

    vlm = ModelVLM({"parecido": 4, "geometria": 4, "materiales": 4, "comentario": ""})
    scores_file = evaluate_run("run1", runs_root=runs, judge=vlm, render=False, pieces=[piece])
    scored = [r for r in read_scores(scores_file) if r["status"] == "scored"]
    assert scored and all(r["judge_model"] == "claude-sonnet-5-5" for r in scored)
    geo = scored[0]["geometry"]
    assert geo["raw_extents_cm"] == pytest.approx([100, 100, 100])
    assert geo["scale_factor"] == pytest.approx(1.0) and geo["source"] == "trimesh"


def test_evaluate_run_superseded_errors_are_ignored(tmp_path: Path, cube_glb: Path) -> None:
    piece = _cube_piece(tmp_path)
    runs = _fake_run(tmp_path, cube_glb, piece)
    storage.write_meta(
        runs / "run1",
        {"errors": [{"piece_id": "p01", "variant": "C", "error": "x", "superseded": True}]},
    )
    scores_file = evaluate_run(
        "run1", runs_root=runs, judge=StubVLM({}), render=False, pieces=[piece]
    )
    assert all(r["variant"] != "C" for r in read_scores(scores_file))


# ---------- Workbench texture selection (pure Python, no Blender) ----------


def _node(kind: str, name: str, inputs: dict[str, list[Any]] | None = None) -> Any:
    from types import SimpleNamespace

    socks = [
        SimpleNamespace(name=k, links=[SimpleNamespace(from_node=n) for n in v])
        for k, v in (inputs or {}).items()
    ]
    return SimpleNamespace(type=kind, name=name, inputs=socks)


def test_albedo_node_is_the_one_feeding_base_color() -> None:
    from harness.eval.bpy_render import albedo_image_node

    normal = _node("TEX_IMAGE", "normal")
    rough = _node("TEX_IMAGE", "roughness")
    albedo = _node("TEX_IMAGE", "albedo")
    normal_map = _node("NORMAL_MAP", "nm", {"Color": [normal]})
    bsdf = _node(
        "BSDF_PRINCIPLED",
        "bsdf",
        {"Base Color": [albedo], "Roughness": [rough], "Normal": [normal_map]},
    )
    assert albedo_image_node([normal, rough, normal_map, bsdf, albedo]).name == "albedo"


def test_albedo_node_through_mix_and_fallbacks() -> None:
    from types import SimpleNamespace

    from harness.eval.bpy_render import activate_albedo_textures, albedo_image_node

    normal = _node("TEX_IMAGE", "normal")
    albedo = _node("TEX_IMAGE", "albedo")
    mix = _node("MIX", "mix", {"A": [albedo]})  # e.g. glTF vertex colour × texture
    bsdf = _node("BSDF_PRINCIPLED", "bsdf", {"Base Color": [mix], "Normal": [normal]})
    assert albedo_image_node([normal, bsdf, mix, albedo]).name == "albedo"
    # No Base Color texture: any image node; no image node at all: None.
    plain = _node("BSDF_PRINCIPLED", "bsdf", {"Base Color": []})
    assert albedo_image_node([plain, normal]).name == "normal"
    assert albedo_image_node([plain]) is None

    class Nodes(list):  # stands in for bpy's node collection (iterable + ``active``)
        active: Any = None

    nodes = Nodes([normal, bsdf, mix, albedo])
    nodes.active = normal
    mats = [
        SimpleNamespace(node_tree=SimpleNamespace(nodes=nodes)),
        SimpleNamespace(node_tree=None),
    ]
    assert activate_albedo_textures(mats) == 1 and nodes.active is albedo


def test_pick_studio_light_prefers_paint_and_falls_back_to_default() -> None:
    from harness.eval.bpy_render import STUDIO_LIGHT, pick_studio_light

    assert STUDIO_LIGHT == "paint.sl"
    assert pick_studio_light(["Default", "basic.sl", "paint.sl"]) == "paint.sl"
    assert pick_studio_light(iter(["Default", "studio.sl"])) == "Default"
    assert pick_studio_light([], preferred="studio.sl") == "Default"


# ---------------------------------------------------------------- fit-to-box bookkeeping


def test_evaluate_run_carries_fit_box_info(tmp_path: Path, cube_glb: Path) -> None:
    piece = _cube_piece(tmp_path)
    runs = _fake_run(tmp_path, cube_glb, piece)
    a1 = runs / "run1" / "p01" / "A" / "cand_1"
    shutil.copyfile(cube_glb, storage.model_post_path(a1))
    (a1 / "post_meta.json").write_text(
        json.dumps(
            {
                "errors": {"width": 0.0, "height": 0.0, "depth": 0.0},
                "fit_box_applied": True,
                "errors_before_fit": {"width": 0.0, "height": -0.06, "depth": 0.04},
            }
        ),
        encoding="utf-8",
    )
    # B/cand_1: only the candidate meta carries the fit fields (no post_meta.json).
    b1 = runs / "run1" / "p01" / "B" / "cand_1"
    shutil.copyfile(cube_glb, storage.model_post_path(b1))
    meta = storage.read_meta(b1)
    meta["post"] = {
        "ok": True,
        "fit_box_applied": False,
        "errors_before_fit": {"width": 0.2, "height": 0.0, "depth": 0.0},
    }
    storage.write_meta(b1, meta)
    vlm = StubVLM({"parecido": 4, "geometria": 4, "materiales": 4, "comentario": ""})
    scores_file = evaluate_run("run1", runs_root=runs, judge=vlm, render=False, pieces=[piece])
    by_cand = {
        (r["variant"], r["candidate"]): r
        for r in read_scores(scores_file)
        if r["status"] != "generation_failed"
    }
    assert by_cand[("A", 1)]["fit_box_applied"] is True
    assert by_cand[("A", 1)]["errors_before_fit"]["height"] == -0.06
    assert by_cand[("B", 1)]["fit_box_applied"] is False
    assert by_cand[("B", 1)]["errors_before_fit"]["width"] == 0.2
    assert "fit_box_applied" not in by_cand[("A", 2)]  # raw model.glb, no post step


def test_report_shows_scale_before_fit(tmp_path: Path) -> None:
    records = _records("A", {"tapizado": (1, 3)})
    for rec in records:
        rec["geometry"] = {"source": "trimesh", "max_error": 0.0}
    records[0]["fit_box_applied"] = True
    records[0]["errors_before_fit"] = {"width": 0.0, "height": -0.06, "depth": 0.03}
    records[1]["fit_box_applied"] = False
    records[1]["errors_before_fit"] = {"width": 0.12, "height": 0.0, "depth": 0.0}
    records[1]["geometry"]["max_error"] = 0.12
    # records[2]: no fit fields (older run) → its measured max_error (0.0) is the pre-fit one.
    s = summarize(records)["A"]
    assert s.fit_applied == 1 and s.fit_measured == 3
    assert s.pre_fit_error_mean == pytest.approx((0.06 + 0.12 + 0.0) / 3)
    _write_scores(tmp_path, records)
    report = build_report("r1", runs_root=tmp_path).read_text(encoding="utf-8")
    assert "| Escala | Escala antes del ajuste |" in report
    assert "| 5,00 | 6,0 % |" in report
    assert "aplicado en 1 de 3 candidatos medidos" in report
