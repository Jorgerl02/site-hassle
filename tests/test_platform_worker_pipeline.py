"""process_piece with in-memory DB/Storage, FakeProvider and Blender steps simulated."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
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
from platform_worker import cli, config, pipeline
from platform_worker.interpret import Interpretation
from platform_worker.providers import FakeProvider
from platform_worker.providers.base import GenerationOutcome

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_GLB = FIXTURES / "platform" / "sample.glb"
PIECE_ID = "22222222-2222-2222-2222-222222222222"
# Simulated geometric error per candidate folder (organic: cand_2 is the better one).
CAND_ERRORS = {"cand_1": 0.06, "cand_2": 0.01}


WORKER_ENV_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "PROVIDER",
    "FAL_KEY",
    "FAL_MODEL",
    "TRIPO_API_KEY",
    "BLENDER_BIN",
    "WORKER_ENV_FILE",
    "AUTO_PUBLISH",
    "ANTHROPIC_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolated_worker_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Never read the repo's real ``.env`` nor worker keys from the shell."""
    for key in WORKER_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WORKER_ENV_FILE", str(tmp_path / "no-such-worker.env"))


# ---------------------------------------------------------------- in-memory backends


def _now_iso(delta: timedelta = timedelta(0)) -> str:
    return (datetime.now(UTC) + delta).isoformat()


class FakeDB:
    def __init__(self, pieces: list[dict[str, Any]] | None = None, photos=None) -> None:
        self.pieces = {p["id"]: dict(p) for p in pieces or []}
        self.photos = photos or {}
        self.models: list[dict[str, Any]] = []
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.requeue_calls: list[int] = []
        self.deleted: list[tuple[str, int]] = []
        self.spend_today = 0.0

    def _claimable(self, p: dict[str, Any]) -> bool:
        # claim_next_piece(): photos present (or older than 10 min) and not deferred.
        if p.get("status", "queued") != "queued":
            return False
        not_before = p.get("not_before")
        if not_before and datetime.fromisoformat(not_before) > datetime.now(UTC):
            return False
        created = p.get("created_at")
        old = bool(created) and datetime.fromisoformat(created) < datetime.now(UTC) - timedelta(
            minutes=10
        )
        photos = [
            r for r in self.photos.get(p["id"], []) if "/thumb." not in r.get("storage_path", "")
        ]
        return bool(photos) or old

    def claim_next(self):
        # Same as claim_next_piece() in SQL: oldest claimable → generating, claimed_at, error null.
        queued = [p for p in self.pieces.values() if self._claimable(p)]
        if not queued:
            return None
        piece = min(queued, key=lambda p: p.get("created_at") or "")
        piece.update(status="generating", claimed_at=_now_iso(), error=None)
        return dict(piece)

    def requeue_stale(self, minutes: int = 30) -> int:
        self.requeue_calls.append(minutes)
        return 0

    def provider_spend_today(self) -> float:
        return self.spend_today

    def update_piece(self, piece_id: str, **fields: Any) -> dict[str, Any]:
        self.updates.append((piece_id, fields))
        self.pieces.setdefault(piece_id, {"id": piece_id}).update(fields)
        return self.pieces[piece_id]

    def insert_model(self, row: dict[str, Any]) -> dict[str, Any]:
        json.dumps(row)  # what PostgREST receives must be JSON
        self.models.append(row)
        return {"id": f"m{len(self.models)}", **row}

    def delete_models(self, piece_id: str, attempt: int) -> None:
        self.deleted.append((piece_id, attempt))
        self.models = [
            m for m in self.models if (m["piece_id"], m["attempt"]) != (piece_id, attempt)
        ]

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


DELIVER_CALLS: list[dict[str, Any]] = []
DELIVER_WARNINGS: list[str] = []


def fake_deliver(cand_dir, piece, *, max_tris, max_tex, out_dir, **kwargs) -> DeliverResult:
    DELIVER_CALLS.append({"cand_dir": Path(cand_dir), "max_tris": max_tris, **kwargs})
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    glb = out_dir / "model_web.glb"
    glb.write_bytes(f"glb tris={max_tris} tex={max_tex}".encode())
    usdz = out_dir / "model.usdz"
    usdz.write_bytes(b"usdz")
    preview = out_dir / "preview"
    preview.mkdir(exist_ok=True)
    preview_glb = preview / "model_preview.glb"
    preview_glb.write_bytes(
        f"glb tris={kwargs['preview_max_tris']} tex={kwargs['preview_max_tex']}".encode()
    )
    preview_usdz = preview / "model_preview.usdz"
    preview_usdz.write_bytes(b"preview usdz")
    return DeliverResult(
        preview_glb_path=preview_glb,
        preview_usdz_path=preview_usdz,
        preview_glb_bytes=preview_glb.stat().st_size,
        preview_usdz_bytes=12,
        preview_tris_after=min(900, kwargs["preview_max_tris"]),
        warnings=list(DELIVER_WARNINGS),
        optimize_error="gltf-transform no disponible" if DELIVER_WARNINGS else None,
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
        # What the pipeline forces: ``{"kind", **params}`` of the overrides file, or None.
        self.forced = (
            json.loads(Path(overrides_path).read_text(encoding="utf-8"))[PIECE_ID]
            if overrides_path is not None
            else None
        )
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


# What the stub interpreter "sees" in the photos (tests set it); default: no evidence.
NO_EVIDENCE = Interpretation(None, None, None, 0.0, ["no evidence"])
INTERPRETATION: list[Interpretation] = [NO_EVIDENCE]


class StubInterpreter:
    calls: list[dict[str, Any]] = []

    def interpret(self, photos, **kwargs) -> Interpretation:
        StubInterpreter.calls.append({"photos": list(photos), **kwargs})
        return INTERPRETATION[0]


def see(interpretation: Interpretation) -> None:
    INTERPRETATION[0] = interpretation


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
    monkeypatch.setattr(pipeline, "SilhouetteInterpreter", StubInterpreter)
    monkeypatch.setattr(pipeline, "photo_mean_color", lambda photo: (200, 180, 160))
    FakeParametric.instances.clear()
    StubInterpreter.calls.clear()
    INTERPRETATION[0] = NO_EVIDENCE
    DELIVER_CALLS.clear()
    DELIVER_WARNINGS.clear()


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
        "created_at": _now_iso(),
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
    assert FakeParametric.instances[0].forced == {"kind": "box"}
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
    assert uploads[("previews", f"{prefix}/model_preview.usdz")] == b"preview usdz"
    assert ("models", f"{prefix}/model.usdz") in uploads
    # deliver runs ONCE per candidate, non-strict, with the preview limits.
    assert len(DELIVER_CALLS) == 1
    assert DELIVER_CALLS[0]["strict"] is False and DELIVER_CALLS[0]["preview"] is True
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
    assert other["selected"] is False and other["max_error"] == pytest.approx(0.06)
    # Both candidates are delivered: the selected one at the canonical paths, the other
    # under cand_1/, so the admin can switch.
    prefix = f"{PIECE_ID}/1"
    assert selected[0]["glb_path"] == f"{prefix}/model_web.glb"
    assert selected[0]["preview_path"] == f"{prefix}/model_preview.glb"
    assert other["glb_path"] == f"{prefix}/cand_1/model_web.glb"
    assert other["usdz_path"] == f"{prefix}/cand_1/model.usdz"
    assert other["preview_path"] == f"{prefix}/cand_1/model_preview.glb"
    assert other["render_paths"]["contact"] == f"{prefix}/cand_1/contact.jpg"
    assert "deliver" in other["meta"] and "deliver" in selected[0]["meta"]
    for path in (other["glb_path"], selected[0]["glb_path"]):
        assert ("models", path) in storage.uploads
    for path in (other["preview_path"], selected[0]["preview_path"]):
        assert ("previews", path) in storage.uploads
    assert all(m["meta"]["post"]["fit_box_applied"] for m in db.models)
    cand = tmp_path / "runs" / PIECE_ID / "1" / "fake" / "cand_1" / "model.glb"
    assert cand.read_bytes() == SAMPLE_GLB.read_bytes()


def test_invalid_photo_needs_photos_with_english_error(tmp_path: Path) -> None:
    pdf = tmp_path / "src" / "doc.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.7")
    db, storage, row = setup(tmp_path, photo=pdf)
    assert run(db, storage, row, tmp_path) == "needs_photos"
    piece = db.pieces[PIECE_ID]
    assert piece["status"] == "needs_photos"
    assert "isn't an image" in piece["error"] and "What a good photo looks like" in piece["error"]
    assert db.models == [] and storage.uploads == {}


@pytest.mark.parametrize(
    ("overrides", "word"),
    [
        ({"kind": "lampara", "name": "Lámpara de pie"}, "lamps"),
        ({"kind": "mesa", "notes": "Mesa de acero cromado"}, "metal"),
        ({"kind": "mesita", "notes": "Sobre de vidrio templado"}, "glass"),
        ({"kind": "mesita", "notes": "Tempered glass top"}, "glass"),
    ],
)
def test_excluded_piece_is_rejected_with_reason(tmp_path: Path, overrides, word) -> None:
    db, storage, row = setup(tmp_path, **overrides)
    assert run(db, storage, row, tmp_path) == "rejected"
    piece = db.pieces[PIECE_ID]
    assert piece["status"] == "rejected" and word in piece["reject_reason"]
    assert piece["error"] is None and db.models == [] and storage.uploads == {}


def test_provider_exception_fails(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path, kind="jarron", name="Jarrón")
    assert run(db, storage, row, tmp_path, provider=BrokenProvider()) == "failed"
    error = db.pieces[PIECE_ID]["error"]
    assert error.startswith("No se pudo generar ningún modelo") and "proveedor caído" in error
    assert db.models == []


def test_organic_without_provider_fails_with_message(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path, kind="sillon", name="Sillón", rectilinear=False)
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
    assert db.requeue_calls == [90]


def test_run_once_processes_one_piece(tmp_path: Path) -> None:
    db, storage, _ = setup(tmp_path)
    db.pieces[PIECE_ID]["status"] = "queued"  # setup() already claimed it; put it back
    ctx = {"db": db, "storage": storage, "provider": None, "blender_bin": None}
    assert cli.run_loop(ctx, once=True, poll_seconds=0, workdir=tmp_path / "runs") == 1
    assert db.pieces[PIECE_ID]["status"] == "review"
    assert db.requeue_calls == [90]


def test_cli_exits_2_without_service_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    result = CliRunner().invoke(cli.app, ["run", "--once"])
    assert result.exit_code == 2
    assert "SUPABASE_SERVICE_ROLE_KEY" in result.output


def test_cli_ignores_real_env_file_when_redirected(tmp_path: Path, monkeypatch) -> None:
    """With the redirected env file absent, a key in some other .env is never read."""
    real = tmp_path / ".env"
    real.write_text("SUPABASE_URL=https://x.supabase.co\nSUPABASE_SERVICE_ROLE_KEY=k\n")
    monkeypatch.chdir(tmp_path)  # a .env in the working directory must not leak either
    result = CliRunner().invoke(cli.app, ["run", "--once"])
    assert result.exit_code == 2


def test_load_settings_reads_worker_env_file(tmp_path: Path, monkeypatch) -> None:
    env = tmp_path / "worker.env"
    env.write_text("SUPABASE_URL=https://x.supabase.co\nPROVIDER=fake\nFAL_KEY=\n")
    monkeypatch.setenv("WORKER_ENV_FILE", str(env))
    monkeypatch.setenv("PROVIDER", "tripo")  # the process environment wins
    settings = config.load_settings()
    assert settings["SUPABASE_URL"] == "https://x.supabase.co"
    assert settings["PROVIDER"] == "tripo"
    assert settings["FAL_KEY"] is None


def test_load_settings_follows_harness_redirection(tmp_path: Path, monkeypatch) -> None:
    from harness.core import config as harness_config

    env = tmp_path / "harness.env"
    env.write_text("SUPABASE_SERVICE_ROLE_KEY=k\n")
    monkeypatch.delenv("WORKER_ENV_FILE")
    monkeypatch.setattr(harness_config, "DEFAULT_ENV_FILE", env)
    assert config.env_file_path() == env
    assert config.load_settings()["SUPABASE_SERVICE_ROLE_KEY"] == "k"


# ---------------------------------------------------------------- fix round 1


def _claim_without_photos(tmp_path: Path, created_ago: timedelta):
    db, storage, _ = setup(tmp_path, created_at=_now_iso(-created_ago))
    db.pieces[PIECE_ID]["status"] = "queued"  # setup() claimed it; go through claim_next
    db.photos = {}  # claimed before its piece_photos rows exist
    return db, storage


def test_recent_piece_without_photos_is_not_claimed(tmp_path: Path) -> None:
    """I-4: a photo-less piece younger than 10 min never holds the queue."""
    db, storage = _claim_without_photos(tmp_path, timedelta(minutes=1))
    assert db.claim_next() is None
    # Reached anyway (``piece <id>``): it goes back to the queue, never a counter.
    row = dict(db.pieces[PIECE_ID], status="generating")
    for _ in range(3):
        assert run(db, storage, row, tmp_path) == "queued"
    piece = db.pieces[PIECE_ID]
    assert piece["status"] == "queued" and piece["claimed_at"] is None
    assert piece["error"] == pipeline.WAITING_PHOTOS_MESSAGE


def test_photo_less_piece_does_not_starve_the_next_one(tmp_path: Path) -> None:
    db, storage = _claim_without_photos(tmp_path, timedelta(minutes=1))
    other = "33333333-3333-3333-3333-333333333333"
    db.pieces[other] = dict(db.pieces[PIECE_ID], id=other, created_at=_now_iso())
    db.photos = {other: [{"piece_id": other, "storage_path": f"u1/{other}/1.jpg", "position": 1}]}
    assert db.claim_next()["id"] == other


def test_old_piece_without_photos_needs_photos(tmp_path: Path) -> None:
    db, storage = _claim_without_photos(tmp_path, timedelta(minutes=11))
    assert run(db, storage, db.claim_next(), tmp_path) == "needs_photos"
    assert db.pieces[PIECE_ID]["status"] == "needs_photos"
    assert db.pieces[PIECE_ID]["error"] == pipeline.NO_PHOTOS_ERROR
    assert db.claim_next() is None and db.models == []


def test_piece_without_created_at_is_not_requeued(tmp_path: Path) -> None:
    db, storage = _claim_without_photos(tmp_path, timedelta(0))
    db.pieces[PIECE_ID]["created_at"] = None
    assert db.claim_next() is None  # no photos and no age: claim_next_piece skips it
    assert run(db, storage, dict(db.pieces[PIECE_ID]), tmp_path) == "needs_photos"


def test_photos_arriving_after_a_requeue_reach_review(tmp_path: Path) -> None:
    db, storage = _claim_without_photos(tmp_path, timedelta(minutes=1))
    photos = {
        PIECE_ID: [{"piece_id": PIECE_ID, "storage_path": f"u1/{PIECE_ID}/1.jpg", "position": 1}]
    }
    assert run(db, storage, dict(db.pieces[PIECE_ID]), tmp_path) == "queued"
    assert db.claim_next() is None
    db.photos = photos
    assert run(db, storage, db.claim_next(), tmp_path) == "review"
    assert db.pieces[PIECE_ID]["error"] is None


def test_candidate_1_wins_selected_row_is_inserted_last(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(CAND_ERRORS, "cand_1", 0.005)
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá", width_cm=200, depth_cm=90)
    db.models.append({"piece_id": PIECE_ID, "attempt": 1, "candidate": 9, "selected": True})
    assert run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB)) == "review"
    assert db.deleted == [(PIECE_ID, 1)]
    assert [m["candidate"] for m in db.models] == [2, 1]
    assert db.models[-1]["selected"] is True and db.models[-1]["candidate"] == 1
    assert db.models[-1]["glb_path"] == f"{PIECE_ID}/1/model_web.glb"
    assert db.models[0]["glb_path"] == f"{PIECE_ID}/1/cand_2/model_web.glb"
    assert sum(m["selected"] for m in db.models) == 1


class FlakyDB(FakeDB):
    """``insert_model`` fails (Supabase down after the uploads)."""

    def insert_model(self, row):
        raise ConnectionError("Supabase no responde")


def test_insert_failure_marks_failed_and_loop_survives(tmp_path: Path) -> None:
    db, storage, _ = setup(tmp_path)
    flaky = FlakyDB([dict(db.pieces[PIECE_ID], status="queued")], db.photos)
    sleeps: list[float] = []
    ctx = {"db": flaky, "storage": storage, "provider": None, "blender_bin": None}
    cli.run_loop(
        ctx, once=False, poll_seconds=1, workdir=tmp_path / "runs",
        sleep=sleeps.append, max_cycles=3,
    )  # fmt: skip
    assert flaky.pieces[PIECE_ID]["status"] == "failed"
    assert "Supabase no responde" in flaky.pieces[PIECE_ID]["error"]


class DeadDB(FakeDB):
    """Every write fails: the piece cannot even be marked failed."""

    def insert_model(self, row):
        raise ConnectionError("Supabase no responde")

    def update_piece(self, piece_id, **fields):
        if fields.get("status") in ("failed", "review"):
            raise ConnectionError("Supabase no responde")
        return super().update_piece(piece_id, **fields)


def test_fail_never_raises_and_loop_keeps_running(tmp_path: Path) -> None:
    db, storage, _ = setup(tmp_path)
    dead = DeadDB([dict(db.pieces[PIECE_ID], status="queued")], db.photos)
    ctx = {"db": dead, "storage": storage, "provider": None, "blender_bin": None}
    processed = cli.run_loop(
        ctx, once=False, poll_seconds=0, workdir=tmp_path / "runs",
        sleep=lambda _s: None, max_cycles=4,
    )  # fmt: skip
    assert processed == 1
    # Left in ``generating``: the periodic stale sweep requeues it.
    assert dead.pieces[PIECE_ID]["status"] == "generating"


def test_requeue_stale_runs_every_10_cycles(tmp_path: Path) -> None:
    db = FakeDB()
    ctx = {"db": db, "storage": None, "provider": None, "blender_bin": None}
    cli.run_loop(
        ctx, once=False, poll_seconds=0, workdir=tmp_path, sleep=lambda _s: None, max_cycles=21
    )
    assert db.requeue_calls == [90, 90, 90]  # cycles 0, 10 and 20


def _cli_env(monkeypatch, tmp_path: Path, blender: str | None) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    if blender is not None:
        monkeypatch.setenv("BLENDER_BIN", blender)


@pytest.mark.parametrize("blender", [None, "/no/such/blender"])
def test_run_exits_2_without_blender(tmp_path: Path, monkeypatch, blender) -> None:
    _cli_env(monkeypatch, tmp_path, blender)
    result = CliRunner().invoke(cli.app, ["run", "--once"])
    assert result.exit_code == 2
    assert "BLENDER_BIN" in result.output


@pytest.mark.parametrize("status", ["review", "ready", "approved", "generating"])
def test_piece_command_refuses_finished_attempts(tmp_path: Path, monkeypatch, status) -> None:
    blender = tmp_path / "blender"
    blender.write_text("#!/bin/sh\n")
    blender.chmod(0o755)
    _cli_env(monkeypatch, tmp_path, str(blender))
    db = FakeDB([{"id": PIECE_ID, "status": status, "attempt": 1}])
    monkeypatch.setattr(cli, "WorkerDB", lambda url, key: db)
    result = CliRunner().invoke(cli.app, ["piece", PIECE_ID])
    assert result.exit_code == 1
    assert (f"«{status}»" if status != "generating" else "--force") in result.output
    assert db.updates == []


def test_piece_command_force_reprocesses_generating(tmp_path: Path, monkeypatch) -> None:
    blender = tmp_path / "blender"
    blender.write_text("#!/bin/sh\n")
    blender.chmod(0o755)
    _cli_env(monkeypatch, tmp_path, str(blender))
    db = FakeDB([{"id": PIECE_ID, "status": "generating", "attempt": 1}])
    monkeypatch.setattr(cli, "WorkerDB", lambda url, key: db)
    seen: list[str] = []
    monkeypatch.setattr(cli, "_process", lambda ctx, row, workdir: seen.append(row["id"]))
    result = CliRunner().invoke(cli.app, ["piece", PIECE_ID, "--force"])
    assert result.exit_code == 0, result.output
    assert seen == [PIECE_ID] and db.updates[0][1]["status"] == "generating"


def test_exif_rotated_photo_is_upright(tmp_path: Path) -> None:
    src = tmp_path / "rot.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° CW on display
    Image.new("RGB", (400, 200), (10, 20, 30)).save(src, exif=exif)
    upright = pipeline.oriented_copy(src, tmp_path / "oriented")
    with Image.open(upright) as img:
        assert img.size == (200, 400)
    plain = _png(tmp_path / "plain.png")
    assert pipeline.oriented_copy(plain, tmp_path / "oriented") == plain


def test_raw_photo_fallback_is_downscaled_jpeg(tmp_path: Path, monkeypatch) -> None:
    def no_object(src, dst, size=1024):
        raise ValueError("sin objeto")

    monkeypatch.setattr(pipeline, "clean_image", no_object)
    big = _png(tmp_path / "big.png", size=(4000, 3000))
    [out] = pipeline._organic_images([big], tmp_path / "work")
    with Image.open(out) as img:
        assert img.format == "JPEG" and max(img.size) == pipeline.PROVIDER_MAX_PX


def test_review_sends_the_notice_once(tmp_path: Path, monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pipeline, "notify_status", lambda pid, status, **kw: sent.append((pid, status))
    )
    db, storage, row = setup(tmp_path)
    assert run(db, storage, row, tmp_path) == "review"
    assert sent == [(PIECE_ID, "review")]


def test_needs_photos_sends_no_notice(tmp_path: Path, monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pipeline, "notify_status", lambda pid, status, **kw: sent.append((pid, status))
    )
    db, storage, row = setup(tmp_path, kind="lampara")
    assert run(db, storage, row, tmp_path) == "rejected"
    assert sent == []


# ---------------------------------------------------------------- final review fixes


def _photo_rows(paths: list[str]) -> list[dict[str, Any]]:
    return [
        {"piece_id": PIECE_ID, "storage_path": p, "position": i} for i, p in enumerate(paths, 1)
    ]


@pytest.mark.parametrize(
    "bad",
    [
        f"u1/{PIECE_ID}/../../u2/other/1.jpg",
        f"u2/{PIECE_ID}/1.jpg",
        "u1/other-piece/1.jpg",
        f"u1/{PIECE_ID}/sub/1.jpg",
    ],
)
def test_photo_path_outside_the_piece_folder_fails(tmp_path: Path, bad: str) -> None:
    db, storage, row = setup(tmp_path)
    db.photos[PIECE_ID] = _photo_rows([bad])
    storage.objects[("photos", bad)] = tmp_path / "src" / "1.jpg"
    assert run(db, storage, row, tmp_path) == "failed"
    assert "Ruta de foto no válida" in db.pieces[PIECE_ID]["error"]
    assert not (tmp_path / "runs" / PIECE_ID / "1" / "photos").exists()


def test_only_the_first_four_photos_by_position_are_used(tmp_path: Path) -> None:
    db, storage, _ = setup(tmp_path)
    paths = [f"u1/{PIECE_ID}/{n}.jpg" for n in range(1, 7)] + [f"u1/{PIECE_ID}/thumb.jpg"]
    rows = _photo_rows(paths)
    rows.reverse()  # PostgREST order must not matter
    db.photos[PIECE_ID] = rows
    src = tmp_path / "src" / "1.jpg"
    storage.objects = {("photos", p): src for p in paths}
    seen: list[str] = []
    original = storage.download

    def download(bucket, path, dst):
        seen.append(path)
        return original(bucket, path, dst)

    storage.download = download
    photos = pipeline.download_photos(db, storage, PIECE_ID, tmp_path / "w", user_id="u1")
    assert len(photos) == 4
    assert seen == [f"u1/{PIECE_ID}/{n}.jpg" for n in range(1, 5)]


def test_failed_piece_notifies_the_admin(tmp_path: Path, monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pipeline, "notify_status", lambda pid, status, **kw: sent.append((pid, status)) or True
    )
    db, storage, row = setup(tmp_path, kind="jarron", name="Jarrón")
    assert run(db, storage, row, tmp_path, provider=BrokenProvider()) == "failed"
    assert sent == [(PIECE_ID, "failed")]


class CostlyBrokenProvider(FakeProvider):
    """Charges for the GLB, then the post-processing of every candidate fails."""

    def generate(self, images, dst_glb, *, seed=None):
        outcome = super().generate(images, dst_glb, seed=seed)
        outcome.cost_usd = 0.25
        return outcome


def test_failed_attempt_records_provider_cost(tmp_path: Path, monkeypatch) -> None:
    def broken_post(*args, **kwargs):
        raise RuntimeError("malla rota")

    monkeypatch.setattr(pipeline, "postprocess", broken_post)
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá", provider_cost_usd=0.1)
    assert run(db, storage, row, tmp_path, provider=CostlyBrokenProvider(SAMPLE_GLB)) == "failed"
    assert db.pieces[PIECE_ID]["provider_cost_usd"] == pytest.approx(0.6)


def test_budget_spent_defers_organic_piece_and_notifies_once(tmp_path: Path, monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pipeline, "notify_status", lambda pid, status, **kw: sent.append((pid, status)) or True
    )
    monkeypatch.setattr(pipeline, "_budget_notice_day", None)
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá")
    db.spend_today = 20.0
    calls: list[int] = []

    class CountingProvider(FakeProvider):
        def generate(self, images, dst_glb, *, seed=None):
            calls.append(seed)
            return super().generate(images, dst_glb, seed=seed)

    provider = CountingProvider(SAMPLE_GLB)
    assert run(db, storage, row, tmp_path, provider=provider) == "queued"
    piece = db.pieces[PIECE_ID]
    assert piece["status"] == "queued" and piece["error"] == pipeline.BUDGET_MESSAGE
    assert piece["claimed_at"] is None
    assert datetime.fromisoformat(piece["not_before"]) > datetime.now(UTC)
    assert calls == [] and db.models == []
    assert db.claim_next() is None  # deferred until tomorrow
    # A second piece the same day: still deferred, no second notice.
    assert run(db, storage, dict(piece, status="generating"), tmp_path, provider=provider) == (
        "queued"
    )
    assert sent == [(PIECE_ID, "budget")]


def test_budget_reached_after_first_candidate_keeps_one(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá")

    class Costly(FakeProvider):
        def generate(self, images, dst_glb, *, seed=None):
            outcome = super().generate(images, dst_glb, seed=seed)
            outcome.cost_usd = 1.0
            return outcome

    db.spend_today = 19.5  # 19,5 + 1 of candidate 1 ≥ 20: no second call
    status = pipeline.process_piece(
        db, storage, row, provider=Costly(SAMPLE_GLB), workdir=tmp_path / "runs",
        blender_bin=None, budget_usd=20.0,
    )  # fmt: skip
    assert status == "review"
    assert [m["candidate"] for m in db.models] == [1]


def test_rectilinear_piece_ignores_the_budget(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path)
    db.spend_today = 1000.0
    assert run(db, storage, row, tmp_path) == "review"


def test_daily_budget_from_settings() -> None:
    assert pipeline.daily_budget_usd({}) == 20.0
    assert pipeline.daily_budget_usd({"WORKER_DAILY_BUDGET_USD": "7,5"}) == 7.5
    assert pipeline.daily_budget_usd({"WORKER_DAILY_BUDGET_USD": "x"}) == 20.0


def test_next_madrid_midnight() -> None:
    now = datetime(2026, 11, 9, 22, 30, tzinfo=UTC)  # 23:30 in Madrid
    nxt = pipeline.next_madrid_midnight(now)
    assert nxt.astimezone(pipeline.MADRID).hour == 0
    assert nxt - now == timedelta(minutes=30)


def test_heartbeat_refreshes_claimed_at_between_candidates(tmp_path: Path) -> None:
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá", width_cm=200, depth_cm=90)
    assert run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB)) == "review"
    beats = [f for _, f in db.updates if set(f) == {"claimed_at"}]
    assert len(beats) >= 4  # before each of 2 provider calls and each of 2 deliveries


@pytest.mark.parametrize(
    ("support", "notes", "expected"),
    [
        ("patas", "", "table"),
        ("paneles", "", "panel_table"),
        ("caja", "", "box"),
        ("caja", "Con zócalo de madera", "box_legs"),
        ("caja", "Lleva patas cortas", "box_legs"),
    ],
)
def test_support_answer_picks_the_parametric_kind(tmp_path, support, notes, expected) -> None:
    db, storage, row = setup(tmp_path, kind="aparador", support=support, notes=notes)
    assert run(db, storage, row, tmp_path) == "review"
    assert FakeParametric.instances[0].forced == {"kind": expected}


# ---------------------------------------------------------------- wiring (interpretation,
# materials, single delivery, automatic publishing)

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
TRAVERTINE_ROW = {
    "name": "Mesa Travertino",
    "kind": "otro",
    "support": "no_se",
    "width_cm": 60,
    "height_cm": 45,
    "depth_cm": 60,
}


def _notices(monkeypatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pipeline, "notify_status", lambda pid, status, **kw: sent.append((pid, status)) or True
    )
    return sent


def _selected(db: FakeDB) -> dict[str, Any]:
    [model] = [m for m in db.models if m["selected"]]
    return model


def test_travertine_default_answers_auto_publish_as_e_pedestal(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(CAND_ERRORS, "cand_1", 0.001)
    sent = _notices(monkeypatch)
    see(TRAVERTINE)
    db, storage, row = setup(tmp_path, **TRAVERTINE_ROW)
    assert run(db, storage, row, tmp_path) == "ready"

    forced = FakeParametric.instances[0].forced
    assert forced["kind"] == "pedestal" and forced["top_shape"] == "round"
    assert forced["base_diameter_ratio"] == pytest.approx(0.5, abs=0.02)
    piece = db.pieces[PIECE_ID]
    assert piece["status"] == "ready" and piece["route"] == "E" and piece["error"] is None
    assert all("support" not in fields for _, fields in db.updates)  # never pie_central
    assert sent == [(PIECE_ID, "ready")]
    meta = _selected(db)["meta"]
    assert meta["auto_review"]["decision"] == "auto" and meta["auto_review"]["gate"] == "rules"
    interp = meta["interpretation"]
    assert interp["support"] == "pie_central" and interp["confidence"] == 0.82
    assert interp["effective"]["routing_kind"] == "pedestal"
    assert interp["effective"]["support"] == "no_se"
    assert interp["source"]["rectilinear"] == "inferred" and interp["conflict"] == []
    assert meta["routing"]["kind"] == "pedestal" and meta["dimension_warnings"] == []
    assert meta["material"] == {"id": None, "source": None}  # E keeps the photo texture
    assert StubInterpreter.calls[0]["width_cm"] == 60.0
    assert StubInterpreter.calls[0]["name"] == "Mesa Travertino"


def test_travertine_support_conflict_goes_to_manual_review(tmp_path, monkeypatch) -> None:
    """The owner's case: «mesa» + «patas», photo = one central column."""
    monkeypatch.setitem(CAND_ERRORS, "cand_1", 0.001)
    sent = _notices(monkeypatch)
    see(TRAVERTINE)
    db, storage, row = setup(tmp_path, **{**TRAVERTINE_ROW, "kind": "mesa", "support": "patas"})
    assert run(db, storage, row, tmp_path) == "review"

    forced = FakeParametric.instances[0].forced
    assert forced["kind"] == "pedestal"
    assert forced["base_diameter_ratio"] == pytest.approx(0.5, abs=0.02)
    assert sent == [(PIECE_ID, "review")]
    meta = _selected(db)["meta"]
    assert meta["auto_review"]["decision"] == "manual"
    assert "Conflicto en «support»" in meta["auto_review"]["reasons"][0]
    [conflict] = meta["interpretation"]["conflict"]
    assert conflict == {
        "field": "support",
        "customer": "patas",
        "inferred": "pie_central",
        "confidence": 0.9,
    }
    assert meta["routing"]["photo_overrides_support"] is True


def test_dimension_warnings_are_stored_and_block_publishing(tmp_path, monkeypatch) -> None:
    """The original travertine inputs: 60 × 30 × 25 contradict the photo."""
    monkeypatch.setitem(CAND_ERRORS, "cand_1", 0.001)
    see(TRAVERTINE)
    db, storage, row = setup(tmp_path, **{**TRAVERTINE_ROW, "height_cm": 30, "depth_cm": 25})
    assert run(db, storage, row, tmp_path) == "review"
    meta = _selected(db)["meta"]
    assert len(meta["dimension_warnings"]) == 2
    assert meta["dimension_warnings"][0].startswith("From the photo, the height")
    assert meta["warnings"][:2] == meta["dimension_warnings"]
    assert meta["auto_review"]["reasons"][0].startswith("Aviso: From the photo")


def test_unsure_piece_without_provider_waits_for_the_admin(tmp_path, monkeypatch) -> None:
    sent = _notices(monkeypatch)
    see(Interpretation(True, None, None, 0.55, ["silhouette: …"]))
    db, storage, row = setup(tmp_path, name="Pieza", kind="otro", support="no_se")
    assert run(db, storage, row, tmp_path, provider=None) == "review"
    assert FakeParametric.instances == [] and storage.uploads == {}
    piece = db.pieces[PIECE_ID]
    assert piece["status"] == "review" and piece["route"] == "sin proveedor"
    [model] = db.models
    assert model["candidate"] == 0 and model["selected"] is False
    assert model.get("glb_path") is None
    assert model["meta"]["error"].startswith("Sin modelo: La interpretación de la foto no es")
    assert model["meta"]["interpretation"]["confidence"] == 0.55
    assert model["meta"]["auto_review"]["decision"] == "manual"
    assert sent == [(PIECE_ID, "review")]


def test_organic_route_by_default_answers_uses_the_provider(tmp_path) -> None:
    see(Interpretation(False, None, "sofa", 0.9, ["text: sofá"]))
    db, storage, row = setup(tmp_path, name="Sofá", kind="otro", support="no_se", depth_cm=90)
    assert run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB)) == "review"
    assert db.pieces[PIECE_ID]["route"] == "fake" and FakeParametric.instances == []
    meta = _selected(db)["meta"]
    assert meta["auto_review"]["reasons"][0].startswith("Pieza orgánica sin juez visual")


MATERIAL_CALLS: list[dict[str, Any]] = []


@pytest.fixture
def fake_material(monkeypatch) -> list[dict[str, Any]]:
    MATERIAL_CALLS.clear()

    def apply(glb_in, glb_out, *, material_id, target_rgb, real_size_cm, blender_bin):
        MATERIAL_CALLS.append({"in": Path(glb_in), "id": material_id, "rgb": target_rgb,
                               "size": real_size_cm})  # fmt: skip
        Path(glb_out).write_bytes(b"material " + material_id.encode())
        return {"warnings": [], "uv": "box"}

    monkeypatch.setattr(pipeline, "apply_material", apply)
    return MATERIAL_CALLS


def test_material_is_applied_to_provider_meshes(tmp_path, fake_material) -> None:
    db, storage, row = setup(
        tmp_path, kind="sofa", name="Sofá de lino", width_cm=200, depth_cm=90, rectilinear=False
    )
    assert run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB)) == "review"
    assert [c["id"] for c in fake_material] == ["linen", "linen"]
    assert fake_material[0]["rgb"] == (200, 180, 160)
    assert fake_material[0]["size"] == (200.0, 60.0, 90.0)
    cand = tmp_path / "runs" / PIECE_ID / "1" / "fake" / "cand_1"
    assert (cand / "model_post.glb").read_bytes() == b"material linen"  # renders + deliver
    assert (cand / "model_post_raw.glb").is_file()
    material = _selected(db)["meta"]["material"]
    assert material["id"] == "linen" and material["source"] == "detected"
    assert material["applied"] is True and material["target_rgb"] == [200, 180, 160]


def test_material_is_never_auto_applied_to_e_pieces(tmp_path, fake_material) -> None:
    see(TRAVERTINE)
    db, storage, row = setup(tmp_path, **{**TRAVERTINE_ROW, "notes": "Travertino macizo"})
    run(db, storage, row, tmp_path)
    assert fake_material == []


def test_admin_material_note_applies_to_any_route(tmp_path, fake_material) -> None:
    see(TRAVERTINE)
    db, storage, row = setup(
        tmp_path, **TRAVERTINE_ROW, review_note="Más cálido.\nmaterial:travertine"
    )
    run(db, storage, row, tmp_path)
    assert [c["id"] for c in fake_material] == ["travertine"]
    assert _selected(db)["meta"]["material"]["source"] == "admin"


def test_admin_can_turn_material_detection_off(tmp_path, fake_material) -> None:
    db, storage, row = setup(
        tmp_path, kind="sofa", name="Sofá de lino", rectilinear=False, review_note="material:none"
    )
    run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB))
    assert fake_material == []
    assert _selected(db)["meta"]["material"] == {"id": None, "source": "admin_off"}


def test_material_failure_keeps_the_mesh_and_warns(tmp_path, monkeypatch) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("faltan los mapas")

    monkeypatch.setattr(pipeline, "apply_material", broken)
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá de piel", rectilinear=False)
    assert run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB)) == "review"
    meta = _selected(db)["meta"]
    assert meta["material"]["applied"] is False and "faltan los mapas" in meta["material"]["error"]
    assert any("No se pudo aplicar el material «leather»" in w for w in meta["warnings"])


def test_delivery_warnings_reach_the_admin_and_block_publishing(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(CAND_ERRORS, "cand_1", 0.001)
    DELIVER_WARNINGS.append("GLB sin optimizar: gltf-transform no disponible")
    see(TRAVERTINE)
    db, storage, row = setup(tmp_path, **TRAVERTINE_ROW)
    assert run(db, storage, row, tmp_path) == "review"
    meta = _selected(db)["meta"]
    assert meta["deliver"]["warnings"] == ["GLB sin optimizar: gltf-transform no disponible"]
    assert meta["deliver"]["optimize_error"] == "gltf-transform no disponible"
    assert meta["deliver"]["preview_usdz"] is True
    assert "GLB sin optimizar: gltf-transform no disponible" in meta["warnings"]
    assert meta["auto_review"]["decision"] == "manual"


def test_auto_publish_off_keeps_manual_review(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(CAND_ERRORS, "cand_1", 0.001)
    monkeypatch.setenv("AUTO_PUBLISH", "0")
    see(TRAVERTINE)
    db, storage, row = setup(tmp_path, **TRAVERTINE_ROW)
    assert run(db, storage, row, tmp_path) == "review"
    assert _selected(db)["meta"]["auto_review"]["reasons"] == ["Publicación automática desactivada"]


def test_failed_delivery_of_the_best_candidate_selects_the_other(tmp_path, monkeypatch) -> None:
    from harness.post.deliver import BlenderDeliverError

    def deliver(cand_dir, piece, **kwargs):
        if Path(cand_dir).name == "cand_2":
            raise BlenderDeliverError("Blender se cayó al exportar")
        return fake_deliver(cand_dir, piece, **kwargs)

    monkeypatch.setattr(pipeline, "deliver", deliver)
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá", rectilinear=False)
    assert run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB)) == "review"
    selected = _selected(db)
    assert selected["candidate"] == 1 and selected["glb_path"] == f"{PIECE_ID}/1/model_web.glb"
    other = next(m for m in db.models if m["candidate"] == 2)
    assert other["glb_path"] is None and "Blender se cayó" in other["meta"]["error"]


def test_budget_counts_the_next_call_cost(tmp_path) -> None:
    """Tripo's estimate (credit table: 60 credits = 0,60 $) must fit in the budget."""

    class Settings:
        def estimated_cost_usd(self) -> float:
            return 0.6

    class PricedProvider(FakeProvider):
        settings = Settings()

    assert pipeline.provider_call_cost(PricedProvider(SAMPLE_GLB)) == 0.6
    assert pipeline.provider_call_cost(FakeProvider(SAMPLE_GLB)) == 0.0
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá", rectilinear=False)
    db.spend_today = 19.5
    status = pipeline.process_piece(
        db, storage, row, provider=PricedProvider(SAMPLE_GLB), workdir=tmp_path / "runs",
        blender_bin=None, budget_usd=20.0,
    )  # fmt: skip
    assert status == "queued" and db.pieces[PIECE_ID]["error"] == pipeline.BUDGET_MESSAGE


def test_vlm_judge_runs_with_the_photos_and_renders(tmp_path, monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def judge(vlm, *, blind_id, photos, renders, geometry, tolerance):
        seen.update(blind_id=blind_id, photos=photos, renders=renders, tolerance=tolerance)
        return {"parecido": 5, "geometria": 4, "materiales": 4, "escala": 5, "apt": True}

    monkeypatch.setattr(pipeline, "judge_candidate", judge)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    db, storage, row = setup(tmp_path, kind="sofa", name="Sofá", rectilinear=False)
    assert run(db, storage, row, tmp_path, provider=FakeProvider(SAMPLE_GLB)) == "ready"
    assert [p.stem for p in seen["renders"]] == ["front", "side", "back", "three_quarter", "top"]
    assert len(seen["photos"]) == 1 and PIECE_ID not in seen["blind_id"]
    review = _selected(db)["meta"]["auto_review"]
    assert review["gate"] == "vlm" and review["scores"]["geometria"] == 4
