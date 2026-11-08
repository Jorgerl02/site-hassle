from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from pytest_httpx import HTTPXMock

from harness.clients import meshy
from harness.clients.meshy import (
    MESHY_USD_PER_RETEXTURE,
    GenerationOutcome,
    MeshyClient,
    MeshyError,
)
from harness.core import storage
from harness.core.models import Candidate, Piece, VariantResult
from harness.post.blender_post import PostResult
from harness.refine import REFINE_FILENAME, RefineProviders, refine_candidate
from harness.refine.rules import Action, Issue, diagnose, plan

RUN = "r1"
GLB = b"glTF-fake"


# ----------------------------------------------------------------------------- helpers


def post_block(errors: dict[str, float], *, applied: bool = False, **extra: Any) -> dict:
    return {
        "ok": True,
        "errors": {k: 0.0 for k in errors} if applied else errors,
        "errors_before_fit": errors,
        "fit_box_applied": applied,
        "triangles_after": 1000,
        **extra,
    }


def score_row(materiales: int | None = 4, n_components: int = 10, max_error: float = 0.0):
    scores = None
    if materiales is not None:
        scores = {"parecido": 4, "geometria": 4, "materiales": materiales, "escala": 4}
    return {
        "piece_id": "p01",
        "variant": "B",
        "candidate": 1,
        "scores": scores,
        "geometry": {"n_components": n_components, "max_error": max_error},
    }


def make_candidate(root: Path, index: int, post: dict | None, variant: str = "B") -> Path:
    cand = storage.candidate_dir(storage.variant_dir(RUN, "p01", variant, root=root), index)
    storage.model_path(cand).write_bytes(GLB + str(index).encode())
    meta: dict[str, Any] = {"piece_id": "p01", "variant": variant, "index": index}
    if post is not None:
        meta["post"] = post
    storage.write_meta(cand, meta)
    return cand


def write_scores(root: Path, rows: list[dict]) -> None:
    path = storage.scores_path(RUN, root=root)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class FakePost:
    """Stands in for ``blender_post.postprocess``; residuals per input file name."""

    def __init__(self, errors_before_fit: dict[str, float], guard_ok: bool = True) -> None:
        self.errors_before_fit = errors_before_fit
        self.guard_ok = guard_ok
        self.calls: list[dict[str, Any]] = []

    def __call__(self, glb_in, glb_out, piece, **kwargs) -> PostResult:
        self.calls.append({"glb_in": Path(glb_in), "glb_out": Path(glb_out), **kwargs})
        Path(glb_out).write_bytes(Path(glb_in).read_bytes())
        applied = kwargs.get("fit_box") and self.guard_ok
        errors = {k: 0.0 for k in self.errors_before_fit} if applied else self.errors_before_fit
        return PostResult(
            glb_path=Path(glb_out),
            meta_path=Path(glb_out).with_name("post_meta.json"),
            errors=errors,
            tris_before=2000,
            tris_after=1000,
            textures=[],
            seconds=0.1,
            fit_box_applied=bool(applied),
            errors_before_fit=dict(self.errors_before_fit),
            raw={"fit_skip_reason": None if applied else "error fuera de la guarda"},
        )


class FakeVariant:
    name = "B"

    def __init__(self) -> None:
        self.calls: list[tuple[Path, int]] = []

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        self.calls.append((Path(workdir), candidates))
        out = []
        for index in range(1, candidates + 1):
            cand = storage.candidate_dir(workdir, index)
            storage.model_path(cand).write_bytes(b"regen" + str(index).encode())
            storage.write_meta(cand, {"variant": "B", "index": index, "seed": index})
            out.append(Candidate(index=index, glb_path=storage.model_path(cand), cost_usd=0.25))
        return VariantResult(variant="B", piece_id=piece.id, candidates=out)


class FakeRetexturer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def retexture(self, model_url_or_path, *, image_ref=None, text_prompt=None, dst_glb):
        self.calls.append(
            {"model": Path(model_url_or_path), "image_ref": image_ref, "text_prompt": text_prompt}
        )
        Path(dst_glb).write_bytes(b"retex")
        return GenerationOutcome(
            glb_path=Path(dst_glb), cost_usd=0.22, seconds=1.0, meta={"task_id": "t-retex"}
        )


def providers(post: FakePost, variant: FakeVariant | None = None, retexturer=None):
    def get_variant(name: str):
        if variant is None:
            raise KeyError(name)
        return variant

    return RefineProviders(get_variant=get_variant, retexturer=retexturer, postprocess=post)


# ----------------------------------------------------------------------------- diagnose


def test_diagnose_scale_issue_between_tolerance_and_guard():
    meta = {"post": post_block({"width": 0.01, "height": -0.06, "depth": 0.02})}
    issues = diagnose(meta, None)
    assert [i.kind for i in issues] == ["scale"]
    assert issues[0].value == pytest.approx(0.06)
    assert "6,0 %" in issues[0].detail


def test_diagnose_no_scale_issue_when_fit_applied_or_within_tolerance():
    fitted = {"post": post_block({"width": 0.01, "height": -0.06, "depth": 0.02}, applied=True)}
    assert diagnose(fitted, score_row()) == []
    tight = {"post": post_block({"width": 0.01, "height": -0.02, "depth": 0.0})}
    assert diagnose(tight, None) == []


def test_diagnose_geometry_issue_above_guard():
    meta = {"post": post_block({"width": 0.4, "height": 0.0, "depth": 0.02})}
    issues = diagnose(meta, None)
    assert [i.kind for i in issues] == ["geometry"]
    assert "guarda" in issues[0].detail


def test_diagnose_geometry_issue_when_guard_rejected_fit():
    post = post_block({"width": 0.05, "height": 0.0, "depth": 0.0})
    post.update(fit_box_requested=True, fit_skip_reason="caja degenerada")
    issues = diagnose({"post": post}, None)
    # no "scale": fit_box would be rejected again by the guard
    assert [i.kind for i in issues] == ["geometry"]
    assert "caja degenerada" in issues[0].detail


def test_diagnose_geometry_issue_from_components():
    meta = {"post": post_block({"width": 0.0, "height": 0.0, "depth": 0.0})}
    issues = diagnose(meta, score_row(n_components=8023))
    assert [i.kind for i in issues] == ["geometry"]
    assert "8023 componentes" in issues[0].detail


def test_diagnose_material_issue_only_with_scores():
    meta = {"post": post_block({"width": 0.0, "height": 0.0, "depth": 0.0})}
    assert [i.kind for i in diagnose(meta, score_row(materiales=3))] == ["material"]
    assert diagnose(meta, score_row(materiales=4)) == []
    assert diagnose(meta, score_row(materiales=None)) == []
    assert diagnose(meta, None) == []


def test_diagnose_all_three_issues():
    meta = {"post": post_block({"width": 0.0, "height": 0.08, "depth": 0.0})}
    issues = diagnose(meta, score_row(materiales=2, n_components=6000))
    assert [i.kind for i in issues] == ["scale", "geometry", "material"]


def test_diagnose_falls_back_to_eval_error_without_post():
    assert [i.kind for i in diagnose({}, score_row(max_error=0.05))] == ["scale"]
    assert [i.kind for i in diagnose({"post": {"ok": False}}, score_row(max_error=43.0))] == [
        "geometry"
    ]


def test_diagnose_without_post_or_eval_is_not_clean():
    for meta in ({}, {"post": {"ok": False, "reason": "sin Blender"}}):
        issues = diagnose(meta, None)
        assert [(i.kind, i.detail, i.action) for i in issues] == [
            ("geometry", "sin postprocesado", "fit_box")
        ]
        # planned as a free re-post, never as a paid regeneration
        assert [a.kind for a in plan(issues, can_retexture=True)] == ["fit_box"]


def test_diagnose_zero_pre_fit_error_is_not_missing():
    post = post_block({"width": 0.0, "height": 0.0, "depth": 0.0})
    post["errors"] = {"width": 0.05, "height": 0.0, "depth": 0.0}
    assert diagnose({"post": post}, None) == []


def test_diagnose_non_numeric_scores_mean_no_score():
    meta = {"post": post_block({"width": 0.0, "height": 0.0, "depth": 0.0})}
    row = score_row()
    row["scores"]["materiales"] = "n/a"
    row["geometry"]["n_components"] = "muchos"
    assert diagnose(meta, row) == []
    assert diagnose(meta, {"scores": "roto", "geometry": None}) == []


# ----------------------------------------------------------------------------- plan

ALL = [Issue("scale", "s"), Issue("geometry", "g"), Issue("material", "m")]


def test_plan_orders_actions_and_marks_paid():
    actions = plan(ALL, can_retexture=True)
    assert [a.kind for a in actions] == ["fit_box", "regenerate", "retexture"]
    assert [a.paid for a in actions] == [False, True, True]
    assert actions[0] == Action("fit_box", "s")


def test_plan_respects_regeneration_cap():
    assert [a.kind for a in plan(ALL, regenerations_done=1)] == ["fit_box", "regenerate"]
    assert [a.kind for a in plan(ALL, regenerations_done=2)] == ["fit_box"]


def test_plan_retexture_needs_provider_and_paid_budget():
    assert [a.kind for a in plan(ALL)] == ["fit_box", "regenerate"]
    assert [a.kind for a in plan(ALL, can_retexture=True, paid_budget=1)] == [
        "fit_box",
        "regenerate",
    ]
    assert [a.kind for a in plan(ALL, can_retexture=True, paid_budget=0)] == ["fit_box"]
    assert plan([]) == []


# ----------------------------------------------------------------------------- refine_candidate


def test_refine_applies_fit_box_without_paid_actions(tmp_path, piece):
    root = tmp_path / "runs"
    cand = make_candidate(root, 1, post_block({"width": 0.01, "height": -0.06, "depth": 0.02}))
    post = FakePost({"width": 0.01, "height": -0.06, "depth": 0.02})
    variant = FakeVariant()

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, providers=providers(post, variant)
    )

    assert [s["action"] for s in report.steps] == ["fit_box"]
    assert report.steps[0]["status"] == "ok"
    assert report.paid_actions == 0 and report.cost_usd == 0.0
    assert report.issues_after == [] and report.final_candidate == 1
    assert post.calls[0]["fit_box"] is True
    assert post.calls[0]["glb_in"] == storage.model_path(cand)
    assert post.calls[0]["glb_out"] == storage.model_post_path(cand)
    assert variant.calls == []
    meta = storage.read_meta(cand)
    assert meta["post"]["fit_box_applied"] is True and meta["index"] == 1
    saved = json.loads((cand / REFINE_FILENAME).read_text())
    assert saved["history"][0]["steps"][0]["action"] == "fit_box"
    assert saved["history"][0]["issues_before"][0]["kind"] == "scale"


def test_refine_regenerates_one_more_candidate(tmp_path, piece):
    root = tmp_path / "runs"
    bad = post_block({"width": 0.4, "height": 0.0, "depth": 0.0})
    cand1 = make_candidate(root, 1, bad)
    cand2 = make_candidate(root, 2, bad)
    post = FakePost({"width": 0.02, "height": 0.05, "depth": 0.0})  # new candidate: fits
    variant = FakeVariant()

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, providers=providers(post, variant)
    )

    workdir = cand1.parent
    assert [s["action"] for s in report.steps] == ["regenerate"]
    assert report.steps[0]["new_candidate"] == 3
    assert report.paid_actions == 1
    assert report.cost_usd == pytest.approx(0.75)  # 3 generations billed (see module doc)
    assert report.final_candidate == 3 and report.issues_after == []
    # run with N + 1 in a scratch dir; only cand_3 is moved in; originals untouched
    assert variant.calls == [(workdir / "_refine_regen", 3)]
    assert not (workdir / "_refine_regen").exists()
    assert storage.model_path(cand1).read_bytes() == GLB + b"1"
    assert storage.model_path(cand2).read_bytes() == GLB + b"2"
    cand3 = workdir / "cand_3"
    assert storage.model_path(cand3).read_bytes() == b"regen3"
    meta3 = storage.read_meta(cand3)
    assert meta3["index"] == 3 and meta3["refine_origin"]["from_candidate"] == 1
    assert meta3["post"]["fit_box_applied"] is True
    assert post.calls[-1]["fit_box"] is True
    assert post.calls[-1]["glb_out"] == storage.model_post_path(cand3)


def test_refine_never_exceeds_max_rounds(tmp_path, piece):
    root = tmp_path / "runs"
    make_candidate(root, 1, post_block({"width": 0.4, "height": 0.0, "depth": 0.0}))
    post = FakePost({"width": 0.4, "height": 0.0, "depth": 0.0}, guard_ok=False)
    variant = FakeVariant()

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, max_rounds=1,
        providers=providers(post, variant),
    )  # fmt: skip

    assert report.paid_actions == 1 and len(variant.calls) == 1
    assert [i.kind for i in report.issues_after] == ["geometry"]


def test_refine_caps_regenerations_at_two_across_calls(tmp_path, piece):
    root = tmp_path / "runs"
    cand1 = make_candidate(root, 1, post_block({"width": 0.4, "height": 0.0, "depth": 0.0}))
    post = FakePost({"width": 0.4, "height": 0.0, "depth": 0.0}, guard_ok=False)
    variant = FakeVariant()
    prov = providers(post, variant)

    first = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, max_rounds=5, providers=prov
    )
    assert [s["action"] for s in first.steps] == ["regenerate", "regenerate"]
    assert first.final_candidate == 3 and first.paid_actions == 2

    second = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, max_rounds=5, providers=prov
    )
    assert second.steps == [] and len(variant.calls) == 2
    history = json.loads((cand1 / REFINE_FILENAME).read_text())["history"]
    assert len(history) == 2


def test_refine_regeneration_cap_is_per_workdir(tmp_path, piece):
    root = tmp_path / "runs"
    bad = post_block({"width": 0.4, "height": 0.0, "depth": 0.0})
    cand1 = make_candidate(root, 1, bad)
    make_candidate(root, 2, bad)  # sibling, never refined
    post = FakePost({"width": 0.4, "height": 0.0, "depth": 0.0}, guard_ok=False)
    variant = FakeVariant()
    prov = providers(post, variant)

    first = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, max_rounds=5, providers=prov
    )
    assert [s["new_candidate"] for s in first.steps] == [3, 4]
    assert len(variant.calls) == 2

    for start in (2, 3, 4):  # a sibling, and both regenerated candidates
        report = refine_candidate(
            RUN, "p01", "B", start, piece=piece, root=root, max_rounds=5, providers=prov
        )
        assert report.steps == [] and report.paid_actions == 0
    assert len(variant.calls) == 2
    assert sorted(p.name for p in cand1.parent.glob("cand_*")) == [f"cand_{i}" for i in range(1, 5)]


def test_refine_corrupt_sibling_meta_counts_as_regeneration(tmp_path, piece):
    root = tmp_path / "runs"
    make_candidate(root, 1, post_block({"width": 0.4, "height": 0.0, "depth": 0.0}))
    for index in (2, 3):
        sibling = make_candidate(root, index, None)
        (sibling / "meta.json").write_text("{roto", encoding="utf-8")
    variant = FakeVariant()

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, max_rounds=5,
        providers=providers(FakePost({"width": 0.4, "height": 0.0, "depth": 0.0}), variant),
    )  # fmt: skip

    assert report.steps == [] and variant.calls == []
    assert sum("ilegible" in w for w in report.warnings) == 2


def test_refine_regenerated_meta_carries_attribution(tmp_path, piece):
    root = tmp_path / "runs"
    make_candidate(root, 1, post_block({"width": 0.4, "height": 0.0, "depth": 0.0}))
    post = FakePost({"width": 0.0, "height": 0.0, "depth": 0.0})
    refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, providers=providers(post, FakeVariant())
    )
    meta = storage.read_meta(root / RUN / "p01" / "B" / "cand_2")
    assert meta["piece_id"] == "p01" and meta["variant"] == "B"
    assert meta["index"] == 2 and meta["cost_usd"] == 0.25 and meta["seconds"] == 0.0
    assert meta["glb_path"].endswith("B/cand_2/model.glb")


def test_refine_keeps_billed_cost_when_post_fails_after_move(tmp_path, piece):
    root = tmp_path / "runs"
    make_candidate(root, 1, post_block({"width": 0.4, "height": 0.0, "depth": 0.0}))

    def broken_post(*args, **kwargs):
        raise RuntimeError("Blender se cayó")

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root,
        providers=providers(broken_post, FakeVariant()),
    )  # fmt: skip

    step = report.steps[0]
    assert step["status"] == "failed" and "Blender se cayó" in step["detail"]
    assert step["new_candidate"] == 2 and step["cost_usd"] == pytest.approx(0.5)
    assert report.paid_actions == 1 and report.cost_usd == pytest.approx(0.5)
    assert report.final_candidate == 2
    # one free re-post retry on the new candidate, then stop; the result is not "clean"
    assert [(s["action"], s["status"]) for s in report.steps[1:]] == [("fit_box", "failed")]
    assert [(i.kind, i.detail) for i in report.issues_after] == [("geometry", "sin postprocesado")]
    cand2 = root / RUN / "p01" / "B" / "cand_2"
    assert "refine_origin" in storage.read_meta(cand2)
    saved = json.loads((root / RUN / "p01" / "B" / "cand_1" / REFINE_FILENAME).read_text())
    assert saved["history"][0]["cost_usd"] == pytest.approx(0.5)


def test_refine_keeps_billed_cost_when_variant_leaves_no_candidate(tmp_path, piece):
    root = tmp_path / "runs"
    make_candidate(root, 1, post_block({"width": 0.4, "height": 0.0, "depth": 0.0}))

    class Short(FakeVariant):
        def run(self, piece, workdir, candidates=2):
            return super().run(piece, workdir, candidates=candidates - 1)

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root,
        providers=providers(FakePost({"width": 0.4, "height": 0.0, "depth": 0.0}), Short()),
    )  # fmt: skip

    step = report.steps[0]
    assert step["status"] == "failed" and "cand_2" in step["detail"]
    assert step["cost_usd"] == pytest.approx(0.25) and report.paid_actions == 1
    assert not (root / RUN / "p01" / "B" / "cand_2").exists()


def test_refine_survives_corrupt_refine_json(tmp_path, piece):
    root = tmp_path / "runs"
    cand = make_candidate(root, 1, post_block({"width": 0.01, "height": -0.06, "depth": 0.0}))
    (cand / REFINE_FILENAME).write_text("{no es json", encoding="utf-8")

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root,
        providers=providers(FakePost({"width": 0.01, "height": -0.06, "depth": 0.0})),
    )  # fmt: skip

    assert [s["action"] for s in report.steps] == ["fit_box"]
    assert report.warnings and "corrupto" in report.warnings[0]
    assert (cand / (REFINE_FILENAME + ".corrupt")).read_text() == "{no es json"
    assert len(json.loads((cand / REFINE_FILENAME).read_text())["history"]) == 1


def test_refine_retexture_uses_provider_and_scores(tmp_path, piece):
    root = tmp_path / "runs"
    cand = make_candidate(root, 1, post_block({"width": 0.0, "height": 0.0, "depth": 0.0}))
    write_scores(root, [score_row(materiales=2)])
    image = tmp_path / "1.jpg"
    Image.new("RGB", (64, 64), (120, 80, 40)).save(image)
    post = FakePost({"width": 0.0, "height": 0.0, "depth": 0.0})
    retex = FakeRetexturer()

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root, providers=providers(post, None, retex)
    )

    assert [s["action"] for s in report.steps] == ["retexture"]
    assert report.paid_actions == 1 and report.cost_usd == pytest.approx(0.22)
    assert retex.calls == [
        {"model": storage.model_path(cand), "image_ref": image, "text_prompt": piece.description}
    ]
    assert post.calls[0]["glb_in"] == cand / "model_retex.glb"
    assert storage.model_path(cand).read_bytes() == GLB + b"1"  # original kept
    assert storage.read_meta(cand)["retexture"]["task_id"] == "t-retex"


def test_refine_without_retexturer_or_registered_variant_records_nothing_paid(tmp_path, piece):
    root = tmp_path / "runs"
    make_candidate(root, 1, post_block({"width": 0.5, "height": 0.0, "depth": 0.0}), variant="MG_X")
    write_scores(root, [{**score_row(materiales=1), "variant": "MG_X"}])
    post = FakePost({"width": 0.5, "height": 0.0, "depth": 0.0})

    report = refine_candidate(
        RUN, "p01", "MG_X", 1, piece=piece, root=root, providers=providers(post)
    )

    assert [(s["action"], s["status"]) for s in report.steps] == [("regenerate", "skipped")]
    assert report.paid_actions == 0 and report.cost_usd == 0.0
    assert {i.kind for i in report.issues_after} == {"geometry", "material"}


@pytest.mark.parametrize(("variant_name", "extra_meta"), [("E", {}), ("F", {"routed_to": "E"})])
def test_refine_parametric_candidate_is_not_regenerable(tmp_path, piece, variant_name, extra_meta):
    root = tmp_path / "runs"
    cand = make_candidate(
        root, 1, post_block({"width": 0.4, "height": 0.0, "depth": 0.0}), variant=variant_name
    )
    storage.write_meta(cand, {**storage.read_meta(cand), **extra_meta})
    post = FakePost({"width": 0.4, "height": 0.0, "depth": 0.0})
    variant = FakeVariant()

    report = refine_candidate(
        RUN, "p01", variant_name, 1, piece=piece, root=root, providers=providers(post, variant)
    )

    assert [(s["action"], s["status"]) for s in report.steps] == [("regenerate", "skipped")]
    assert "no regenerable" in report.steps[0]["detail"]
    assert report.paid_actions == 0 and report.cost_usd == 0.0 and variant.calls == []


def test_refine_fit_box_reposts_from_retextured_model(tmp_path, piece):
    root = tmp_path / "runs"
    cand = make_candidate(root, 1, post_block({"width": 0.01, "height": -0.06, "depth": 0.02}))
    (cand / "model_retex.glb").write_bytes(b"retex")
    post = FakePost({"width": 0.01, "height": -0.06, "depth": 0.02})

    report = refine_candidate(RUN, "p01", "B", 1, piece=piece, root=root, providers=providers(post))

    assert [s["action"] for s in report.steps] == ["fit_box"]
    assert post.calls[0]["glb_in"] == cand / "model_retex.glb"
    assert report.steps[0]["source_glb"] == "model_retex.glb"


def test_refine_tolerance_defaults_to_env(tmp_path, piece, monkeypatch):
    # 6 % residual: a scale issue with the default 3 %, clean with SCALE_TOLERANCE=0.08.
    monkeypatch.setenv("SCALE_TOLERANCE", "0.08")
    root = tmp_path / "runs"
    make_candidate(root, 1, post_block({"width": 0.01, "height": -0.06, "depth": 0.02}))
    post = FakePost({"width": 0.01, "height": -0.06, "depth": 0.02})

    report = refine_candidate(RUN, "p01", "B", 1, piece=piece, root=root, providers=providers(post))

    assert report.issues_before == [] and report.steps == []


def test_refine_records_failed_paid_action(tmp_path, piece):
    root = tmp_path / "runs"
    make_candidate(root, 1, post_block({"width": 0.4, "height": 0.0, "depth": 0.0}))

    class Broken(FakeVariant):
        def run(self, piece, workdir, candidates=2):
            raise RuntimeError("Tripo caído")

    report = refine_candidate(
        RUN, "p01", "B", 1, piece=piece, root=root,
        providers=providers(FakePost({"width": 0.4, "height": 0.0, "depth": 0.0}), Broken()),
    )  # fmt: skip

    assert report.steps[0]["status"] == "failed" and "Tripo caído" in report.steps[0]["detail"]
    assert report.paid_actions == 1 and report.final_candidate == 1


def test_refine_missing_candidate_raises(tmp_path, piece):
    with pytest.raises(FileNotFoundError):
        refine_candidate(
            RUN, "p01", "B", 9, piece=piece, root=tmp_path, providers=providers(FakePost({}))
        )


# ----------------------------------------------------------------------------- Meshy retexture

FIX = Path(__file__).parent / "fixtures" / "meshy"
BASE = "https://api.meshy.ai/openapi/v1"
RETEX_ID = "0193bfc5-ee4f-73f8-8525-44b398884ce9"


def fixture(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text())


RETEX_GLB_URL = fixture("retexture_succeeded")["model_urls"]["glb"]


@pytest.fixture
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(meshy.time, "sleep", lambda _s: None)


def mock_retexture(httpx_mock: HTTPXMock, final: str = "retexture_succeeded") -> None:
    httpx_mock.add_response(
        method="POST", url=f"{BASE}/retexture", json=fixture("retexture_create")
    )
    httpx_mock.add_response(
        method="GET", url=f"{BASE}/retexture/{RETEX_ID}", json={"status": "IN_PROGRESS"}
    )
    httpx_mock.add_response(method="GET", url=f"{BASE}/retexture/{RETEX_ID}", json=fixture(final))
    if final == "retexture_succeeded":
        httpx_mock.add_response(method="GET", url=RETEX_GLB_URL, content=b"retex-glb")


@pytest.mark.usefixtures("_no_sleep")
def test_meshy_retexture_local_glb_with_image(httpx_mock: HTTPXMock, tmp_path):
    mock_retexture(httpx_mock)
    model = tmp_path / "model.glb"
    model.write_bytes(GLB)
    image = tmp_path / "ref.png"
    Image.new("RGB", (64, 64), (200, 180, 150)).save(image)
    dst = tmp_path / "out" / "retex.glb"

    outcome = MeshyClient("test-key", poll_interval_s=0.0).retexture(
        model, image_ref=image, text_prompt="roble macizo mate", dst_glb=dst
    )

    assert dst.read_bytes() == b"retex-glb" and outcome.glb_path == dst
    assert outcome.cost_usd == MESHY_USD_PER_RETEXTURE
    assert outcome.meta["task_id"] == RETEX_ID and outcome.meta["polls"] == 2
    assert outcome.meta["consumed_credits"] == 10 and outcome.meta["model_sent_as"] == "data_uri"
    create = httpx_mock.get_requests(method="POST")[0]
    assert create.headers["Authorization"] == "Bearer test-key"
    body = json.loads(create.content)
    prefix = "data:application/octet-stream;base64,"
    assert body["model_url"].startswith(prefix)
    assert base64.b64decode(body["model_url"].removeprefix(prefix)) == GLB
    assert body["image_style_url"].startswith("data:image/png;base64,")
    assert body["text_style_prompt"] == "roble macizo mate"
    assert body["enable_original_uv"] is True and body["target_formats"] == ["glb"]
    assert "Authorization" not in httpx_mock.get_requests(url=RETEX_GLB_URL)[0].headers


@pytest.mark.usefixtures("_no_sleep")
def test_meshy_retexture_remote_url_text_only(httpx_mock: HTTPXMock, tmp_path):
    mock_retexture(httpx_mock)
    url = "https://example.com/model.glb"
    outcome = MeshyClient("k", poll_interval_s=0.0).retexture(
        url, text_prompt="x" * 900, dst_glb=tmp_path / "r.glb"
    )
    body = json.loads(httpx_mock.get_requests(method="POST")[0].content)
    assert body["model_url"] == url and "image_style_url" not in body
    assert len(body["text_style_prompt"]) == 800
    assert outcome.meta["model_sent_as"] == "url"


@pytest.mark.usefixtures("_no_sleep")
def test_meshy_retexture_failure_raises(httpx_mock: HTTPXMock, tmp_path):
    mock_retexture(httpx_mock, final="retexture_failed")
    with pytest.raises(MeshyError, match="Invalid model file") as exc:
        MeshyClient("k", poll_interval_s=0.0).retexture(
            "https://example.com/m.glb", text_prompt="x", dst_glb=tmp_path / "r.glb"
        )
    assert exc.value.payload["status"] == "FAILED"
    assert not (tmp_path / "r.glb").exists()


def test_meshy_retexture_needs_a_style(tmp_path):
    with pytest.raises(ValueError, match="image_ref o text_prompt"):
        MeshyClient("k").retexture("https://example.com/m.glb", dst_glb=tmp_path / "r.glb")
