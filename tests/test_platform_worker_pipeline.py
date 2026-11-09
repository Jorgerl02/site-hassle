"""process_piece with in-memory DB/Storage, FakeProvider and Blender steps simulated."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image
from typer.testing import CliRunner

from harness.core.models import Candidate, GeometryMetrics, VariantResult
from harness.eval.geometry import GeometryResult
from harness.post.blender_post import PostResult
from harness.post.deliver import DeliverResult
from harness.prep import clean
from platform_worker import cli, pipeline
from platform_worker.providers import FakeProvider
from platform_worker.providers.base import GenerationOutcome

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_GLB = FIXTURES / "platform" / "sample.glb"
PIECE_ID = "22222222-2222-2222-2222-222222222222"
# Simulated geometric error per candidate folder (organic: cand_2 is the better one).
CAND_ERRORS = {"cand_1": 0.06, "cand_2": 0.01}


# ---------------------------------------------------------------- in-memory backends


class FakeDB:
    def __init__(self, pieces: list[dict[str, Any]] | None = None, photos=None) -> None:
        self.pieces = {p["id"]: dict(p) for p in pieces or []}
        self.queue = [p["id"] for p in pieces or []]
        self.photos = photos or {}
        self.models: list[dict[str, Any]] = []
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.requeue_calls: list[int] = []

    def claim_next(self):
        if not self.queue:
            return None
        piece = self.pieces[self.queue.pop(0)]
        piece["status"] = "generating"
        return dict(piece)

    def requeue_stale(self, minutes: int = 30) -> int:
        self.requeue_calls.append(minutes)
        return 0

    def update_piece(self, piece_id: str, **fields: Any) -> dict[str, Any]:
        self.updates.append((piece_id, fields))
        self.pieces.setdefault(piece_id, {"id": piece_id}).update(fields)
        return self.pieces[piece_id]

    def insert_model(self, row: dict[str, Any]) -> dict[str, Any]:
        json.dumps(row)  # what PostgREST receives must be JSON
        self.models.append(row)
        return {"id": f"m{len(self.models)}", **row}

    def list_photos(self, piece_id: str) -> list[dict[str, Any]]:
        return self.photos.get(piece_id, [])

    def get_piece(self, piece_id: str):
        return self.pieces.get(piece_id)


class FakeStorage:
    def __init__(self, objects: dict[tuple[str, str], Path]) -> None:
        self.objects = objects
        self.uploads: dict[tuple[str, str], bytes] = {}

    def download(self, bucket: str, path: str, dst: Path) -> Path:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.objects[(bucket, path)], dst)
        return dst

    def upload(self, bucket: str, path: str, src: Path, content_type: str | None = None) -> str:
        self.uploads[(bucket, path)] = Path(src).read_bytes()
        return path


# ---------------------------------------------------------------- harness simulation


def _fake_rembg(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"))
    alpha = np.where((rgb == 128).all(axis=-1), 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def _png(path: Path, color=(200, 200, 200), size=(64, 64)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def fake_postprocess(glb_in, glb_out, piece, **kwargs) -> PostResult:
    glb_out = Path(glb_out)
    glb_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(glb_in, glb_out)
    err = CAND_ERRORS.get(glb_out.parent.name, 0.0)
    meta = glb_out.parent / "post_meta.json"
    meta.write_text(json.dumps({"fit_box": kwargs.get("fit_box", False)}), encoding="utf-8")
    return PostResult(
        glb_path=glb_out,
        meta_path=meta,
        errors={"width": err, "height": 0.0, "depth": 0.0},
        tris_before=1000,
        tris_after=900,
        textures=[],
        seconds=0.1,
        fit_box_applied=bool(kwargs.get("fit_box")),
    )


def fake_measure(glb: Path, piece) -> GeometryResult:
    err = CAND_ERRORS.get(Path(glb).parent.name, 0.0)
    metrics = GeometryMetrics(
        width_cm=piece.width_cm * (1 + err),
        height_cm=piece.height_cm,
        depth_cm=piece.depth_cm,
        err_width=err,
        err_height=0.0,
        err_depth=0.0,
        watertight=True,
        n_components=1,
        n_faces=900,
    )
    return GeometryResult(metrics, "trimesh", None)


def fake_render_views(glb, out_dir, **kwargs) -> list[Path]:
    views = ("front", "side", "back", "three_quarter", "top")
    return [_png(Path(out_dir) / f"{v}.png", (40 * i, 80, 120)) for i, v in enumerate(views)]


def fake_deliver(cand_dir, piece, *, max_tris, max_tex, out_dir, **kwargs) -> DeliverResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    glb = out_dir / "model_web.glb"
    glb.write_bytes(f"glb tris={max_tris} tex={max_tex}".encode())
    usdz = out_dir / "model.usdz"
    usdz.write_bytes(b"usdz")
    return DeliverResult(
        out_dir=out_dir,
        glb_path=glb,
        usdz_path=usdz,
        viewer_path=out_dir / "viewer.html",
        meta_path=out_dir / "deliver_meta.json",
        glb_bytes=glb.stat().st_size,
        usdz_bytes=4,
        tris_before=900,
        tris_after=min(900, max_tris),
        max_tris=max_tris,
        max_tex=max_tex,
        textures=[],
    )


class FakeParametric:
    instances: list[FakeParametric] = []

    def __init__(self, blender_bin=None, overrides_path=None, kind_overrides=None) -> None:
        self.kind_overrides = kind_overrides
        FakeParametric.instances.append(self)

    def run(self, piece, workdir, candidates=1) -> VariantResult:
        cand = Path(workdir) / "cand_1"
        cand.mkdir(parents=True, exist_ok=True)
        glb = cand / "model.glb"
        shutil.copyfile(FIXTURES / "cube.glb", glb)
        return VariantResult(
            variant="E",
            piece_id=piece.id,
            candidates=[Candidate(index=1, glb_path=glb, meta={"kind": "box"})],
        )


class BrokenProvider:
    name = "broken"

    def generate(self, images, dst_glb, *, seed=None) -> GenerationOutcome:
        raise RuntimeError("proveedor caído")


@pytest.fixture(autouse=True)
def simulated_harness(monkeypatch) -> None:
    monkeypatch.setattr(clean, "_remove_background", _fake_rembg)
    monkeypatch.setattr(pipeline, "postprocess", fake_postprocess)
    monkeypatch.setattr(pipeline, "measure_candidate", fake_measure)
    monkeypatch.setattr(pipeline, "render_views", fake_render_views)
    monkeypatch.setattr(pipeline, "deliver", fake_deliver)
    monkeypatch.setattr(pipeline, "ParametricVariant", FakeParametric)
    monkeypatch.setattr(
        pipeline, "clean_image", lambda src, dst, size=1024: Path(shutil.copyfile(src, _dst(dst)))
    )
    FakeParametric.instances.clear()


def _dst(dst: Path) -> Path:
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    return Path(dst)


def good_photo(path: Path) -> Path:
    img = Image.new("RGB", (1600, 1200), (128, 128, 128))
    img.paste((150, 110, 80), (200, 300, 1400, 900))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def setup(tmp_path: Path, photo: Path | None = None, **row_overrides):
    row = {
        "id": PIECE_ID,
        "user_id": "u1",
        "name": "Cabecero de prueba",
        "kind": "cabecero",
        "width_cm": 165,
        "height_cm": 60,
        "depth_cm": 6,
        "rectilinear": None,
        "notes": "",
        "status": "queued",
        "attempt": 1,
    }
    row.update(row_overrides)
    photo = photo or good_photo(tmp_path / "src" / "1.jpg")
    storage_path = f"u1/{PIECE_ID}/1.jpg"
    db = FakeDB(
        [row], {PIECE_ID: [{"piece_id": PIECE_ID, "storage_path": storage_path, "position": 1}]}
    )
    storage = FakeStorage({("photos", storage_path): photo})
    return db, storage, db.claim_next()


def run(db, storage, row, tmp_path, provider=None) -> str:
    return pipeline.process_piece(
        db, storage, row, provider=provider, workdir=tmp_path / "runs", blender_bin=None
    )


# ---------------------------------------------------------------- tests


def test_rectilinear_piece_goes_through_e_to_review(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path)
    assert run(db, storage, row, tmp_path) == "review"

    assert db.pieces[PIECE_ID]["status"] == "review"
    assert db.pieces[PIECE_ID]["route"] == "E"
    assert FakeParametric.instances[0].kind_overrides == {PIECE_ID: "box"}
    assert len(db.models) == 1
    model = db.models[0]
    prefix = f"{PIECE_ID}/1"
    assert model["selected"] is True and model["provider"] == "parametric"
    assert model["glb_path"] == f"{prefix}/model_web.glb"
    assert model["usdz_path"] == f"{prefix}/model.usdz"
    assert model["preview_path"] == f"{prefix}/model_preview.glb"
    assert model["render_paths"] == {
        "front": f"{prefix}/front.png",
        "left": f"{prefix}/left.png",
        "back": f"{prefix}/back.png",
        "three_quarter": f"{prefix}/three_quarter.png",
        "contact": f"{prefix}/contact.jpg",
    }
    assert model["max_error"] == pytest.approx(0.06) and model["cost_usd"] == 0.0
    assert {"post", "geometry", "provider", "candidate"} <= set(model["meta"])

    uploads = storage.uploads
    assert uploads[("models", f"{prefix}/model_web.glb")] == b"glb tris=60000 tex=2048"
    assert uploads[("previews", f"{prefix}/model_preview.glb")] == b"glb tris=15000 tex=512"
    assert ("models", f"{prefix}/model.usdz") in uploads
    contact = tmp_path / "contact.jpg"
    contact.write_bytes(uploads[("renders", f"{prefix}/contact.jpg")])
    with Image.open(contact) as img:  # first photo + 4 renders in one row
        assert img.size == (5 * pipeline.CONTACT_TILE, pipeline.CONTACT_TILE)
    assert (tmp_path / "runs" / PIECE_ID / "1" / "photos" / "1.jpg").is_file()


def test_organic_piece_two_candidates_lowest_error_selected(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá", width_cm=200, depth_cm=90)
    assert run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB)) == "review"

    assert db.pieces[PIECE_ID]["route"] == "fake"
    assert [m["candidate"] for m in db.models] == [1, 2]
    selected = [m for m in db.models if m["selected"]]
    assert len(selected) == 1 and selected[0]["candidate"] == 2
    assert selected[0]["max_error"] == pytest.approx(0.01)
    other = db.models[0]
    assert other["glb_path"] is None and other["max_error"] == pytest.approx(0.06)
    assert all(m["meta"]["post"]["fit_box_applied"] for m in db.models)
    cand = tmp_path / "runs" / PIECE_ID / "1" / "fake" / "cand_1" / "model.glb"
    assert cand.read_bytes() == SAMPLE_GLB.read_bytes()


def test_invalid_photo_needs_photos_with_spanish_error(tmp_path: Path) -> None:
    pdf = tmp_path / "src" / "doc.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.7")
    db, storage, row = setup(tmp_path, photo=pdf)
    assert run(db, storage, row, tmp_path) == "needs_photos"
    piece = db.pieces[PIECE_ID]
    assert piece["status"] == "needs_photos"
    assert "no es una imagen" in piece["error"] and "Requisitos de la foto" in piece["error"]
    assert db.models == [] and storage.uploads == {}


def test_excluded_kind_needs_photos(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path, kind="lampara", name="Lámpara de pie")
    assert run(db, storage, row, tmp_path) == "needs_photos"
    assert "lámparas" in db.pieces[PIECE_ID]["error"]


def test_provider_exception_fails(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path, kind="jarron", name="Jarrón")
    assert run(db, storage, row, tmp_path, provider=BrokenProvider()) == "failed"
    error = db.pieces[PIECE_ID]["error"]
    assert error.startswith("No se pudo generar ningún modelo") and "proveedor caído" in error
    assert db.models == []


def test_organic_without_provider_fails_with_message(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path, kind="sillon", name="Sillón")
    assert run(db, storage, row, tmp_path, provider=None) == "failed"
    assert db.pieces[PIECE_ID]["error"] == pipeline.NO_PROVIDER_ERROR


def test_blender_crash_fails_and_logs(tmp_path: Path, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("Blender murió")

    monkeypatch.setattr(pipeline, "render_views", boom)
    db, storage, row = setup(tmp_path)
    assert run(db, storage, row, tmp_path) == "failed"
    assert "Blender murió" in db.pieces[PIECE_ID]["error"]
    assert (tmp_path / "runs" / PIECE_ID / "1" / "error.log").is_file()


def test_run_requeues_stale_pieces_first(tmp_path: Path) -> None:
    db = FakeDB()
    ctx = {"db": db, "storage": None, "provider": None, "blender_bin": None}
    assert cli.run_loop(ctx, once=True, poll_seconds=0, workdir=tmp_path) == 0
    assert db.requeue_calls == [30]


def test_run_once_processes_one_piece(tmp_path: Path) -> None:
    db, storage, _ = setup(tmp_path)
    db.queue = [PIECE_ID]  # setup() already claimed it; put it back
    ctx = {"db": db, "storage": storage, "provider": None, "blender_bin": None}
    assert cli.run_loop(ctx, once=True, poll_seconds=0, workdir=tmp_path / "runs") == 1
    assert db.pieces[PIECE_ID]["status"] == "review"
    assert db.requeue_calls == [30]


def test_cli_exits_2_without_service_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(cli, "ENV_FILE", tmp_path / "no.env")
    result = CliRunner().invoke(cli.app, ["run", "--once"])
    assert result.exit_code == 2
    assert "SUPABASE_SERVICE_ROLE_KEY" in result.output
