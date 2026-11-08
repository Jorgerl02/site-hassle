from __future__ import annotations

import csv
import io
import json
from collections import Counter
from pathlib import Path

import pytest
from PIL import Image
from pytest_httpx import HTTPXMock

from harness.core.models import CATEGORIES, CSV_COLUMNS, load_pieces
from harness.data.ingest import REPORT_FILENAME, image_targets, ingest, main

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "data" / "sample.csv"


def _rows() -> list[dict[str, str]]:
    with SAMPLE.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _image_bytes(fmt: str = "JPEG", mode: str = "RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (8, 8), "white").save(buf, format=fmt)
    return buf.getvalue()


def _write_sample(path: Path, rows: list[tuple[str, list[str]]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[*CSV_COLUMNS, "image_urls"])
        writer.writeheader()
        for piece_id, urls in rows:
            writer.writerow(
                {
                    "id": piece_id,
                    "name": "Mesa",
                    "store": "Tienda",
                    "source_url": "https://shop.test/mesa",
                    "category": "macizo_mate",
                    "images": ";".join(
                        f"data/images/{piece_id}/{n}.jpg" for n in range(1, len(urls) + 1)
                    ),
                    "width_cm": "50",
                    "height_cm": "40",
                    "depth_cm": "50",
                    "description": "Mesa",
                    "rectilinear": "true",
                    "image_urls": ";".join(urls),
                }
            )
    return path


# --- the frozen sample -------------------------------------------------------------------


def test_sample_loads_through_core_loader() -> None:
    # load_pieces does not require the image files to exist yet.
    pieces = load_pieces(SAMPLE, root=REPO)
    assert len(pieces) == 30
    assert len({p.id for p in pieces}) == 30
    assert [p.id for p in pieces] == [f"p{i:02d}" for i in range(1, 31)]


def test_sample_header_has_image_urls_last() -> None:
    with SAMPLE.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert header == [*CSV_COLUMNS, "image_urls"]


def test_sample_categories_balanced() -> None:
    counts = Counter(r["category"] for r in _rows())
    assert set(counts) == set(CATEGORIES)
    assert all(7 <= c <= 8 for c in counts.values()), counts


def test_sample_mixes_shapes_within_each_category() -> None:
    for cat in CATEGORIES:
        values = {r["rectilinear"] for r in _rows() if r["category"] == cat}
        assert values == {"true", "false"}, cat


def test_sample_measurements_positive() -> None:
    for r in _rows():
        for col in ("width_cm", "height_cm", "depth_cm"):
            assert float(r[col]) > 0, (r["id"], col)


def test_sample_image_columns_consistent() -> None:
    for r in _rows():
        urls = [u for u in r["image_urls"].split(";") if u]
        paths = [p for p in r["images"].split(";") if p]
        assert 1 <= len(urls) <= 4, r["id"]
        assert all(u.startswith("https://") for u in urls), r["id"]
        assert paths == [f"data/images/{r['id']}/{n}.jpg" for n in range(1, len(urls) + 1)]
        assert r["source_url"].startswith("https://"), r["id"]


def test_image_targets_match_images_column(tmp_path: Path) -> None:
    targets = image_targets(SAMPLE, Path("data/images"))
    expected = [p for r in _rows() for p in r["images"].split(";")]
    assert [str(t[3]) for t in targets] == expected


# --- ingest ------------------------------------------------------------------------------


def test_ingest_downloads_and_writes_report(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    csv_path = _write_sample(
        tmp_path / "s.csv",
        [
            ("p01", ["https://img.test/a.jpg", "https://img.test/b.png"]),
            ("p02", ["https://img.test/c.jpg"]),
        ],
    )
    httpx_mock.add_response(url="https://img.test/a.jpg", content=_image_bytes())
    httpx_mock.add_response(url="https://img.test/b.png", content=_image_bytes("PNG", "RGBA"))
    httpx_mock.add_response(url="https://img.test/c.jpg", content=_image_bytes())
    root = tmp_path / "images"

    report = ingest(csv_path, root, timeout_s=5)

    assert report.ok and len(report.downloaded) == 3
    for rel in ("p01/1.jpg", "p01/2.jpg", "p02/1.jpg"):
        with Image.open(root / rel) as img:
            assert img.format == "JPEG"
    data = json.loads((root / REPORT_FILENAME).read_text(encoding="utf-8"))
    assert data["summary"] == {"downloaded": 3, "skipped": 0, "failed": 0}
    request = httpx_mock.get_requests()[0]
    assert "Mozilla" in request.headers["User-Agent"]


def test_ingest_records_404_without_retrying(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    csv_path = _write_sample(
        tmp_path / "s.csv", [("p01", ["https://img.test/missing.jpg", "https://img.test/ok.jpg"])]
    )
    httpx_mock.add_response(url="https://img.test/missing.jpg", status_code=404)
    httpx_mock.add_response(url="https://img.test/ok.jpg", content=_image_bytes())
    root = tmp_path / "images"

    report = ingest(csv_path, root, sleep=lambda s: None)

    assert not report.ok
    assert [(f.piece_id, f.index, f.error) for f in report.failures] == [("p01", 1, "HTTP 404")]
    assert not (root / "p01" / "1.jpg").exists()
    assert (root / "p01" / "2.jpg").exists()
    assert len(httpx_mock.get_requests(url="https://img.test/missing.jpg")) == 1
    data = json.loads((root / REPORT_FILENAME).read_text(encoding="utf-8"))
    assert data["failures"][0]["url"] == "https://img.test/missing.jpg"


def test_ingest_retries_server_errors_at_most_twice(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    csv_path = _write_sample(tmp_path / "s.csv", [("p01", ["https://img.test/flaky.jpg"])])
    httpx_mock.add_response(url="https://img.test/flaky.jpg", status_code=503, is_reusable=True)
    sleeps: list[float] = []

    report = ingest(csv_path, tmp_path / "images", sleep=sleeps.append)

    assert len(httpx_mock.get_requests()) == 3  # 1 attempt + 2 retries
    assert len(sleeps) == 2
    assert report.failures[0].error == "HTTP 503"


def test_ingest_recovers_after_transient_error(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    csv_path = _write_sample(tmp_path / "s.csv", [("p01", ["https://img.test/x.jpg"])])
    httpx_mock.add_response(url="https://img.test/x.jpg", status_code=500)
    httpx_mock.add_response(url="https://img.test/x.jpg", content=_image_bytes())

    report = ingest(csv_path, tmp_path / "images", sleep=lambda s: None)

    assert report.ok and len(report.downloaded) == 1


def test_ingest_records_non_image_body(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    csv_path = _write_sample(tmp_path / "s.csv", [("p01", ["https://img.test/page.jpg"])])
    httpx_mock.add_response(url="https://img.test/page.jpg", html="<html>captcha</html>")

    report = ingest(csv_path, tmp_path / "images")

    assert len(report.failures) == 1 and "imagen" in report.failures[0].error


def test_ingest_skips_existing_files(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    csv_path = _write_sample(
        tmp_path / "s.csv", [("p01", ["https://img.test/a.jpg", "https://img.test/b.jpg"])]
    )
    root = tmp_path / "images"
    (root / "p01").mkdir(parents=True)
    (root / "p01" / "1.jpg").write_bytes(_image_bytes())
    httpx_mock.add_response(url="https://img.test/b.jpg", content=_image_bytes())

    report = ingest(csv_path, root)

    assert [r.index for r in report.skipped] == [1]
    assert [r.index for r in report.downloaded] == [2]
    assert len(httpx_mock.get_requests()) == 1


def test_ingest_does_not_touch_csv(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    csv_path = _write_sample(tmp_path / "s.csv", [("p01", ["https://img.test/a.jpg"])])
    before = csv_path.read_bytes()
    httpx_mock.add_response(url="https://img.test/a.jpg", content=_image_bytes())

    ingest(csv_path, tmp_path / "images")

    assert csv_path.read_bytes() == before


def test_cli_exit_code_reflects_failures(
    tmp_path: Path, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = _write_sample(tmp_path / "s.csv", [("p01", ["https://img.test/gone.jpg"])])
    httpx_mock.add_response(url="https://img.test/gone.jpg", status_code=404)

    code = main(["--csv", str(csv_path), "--images-root", str(tmp_path / "images")])

    assert code == 1
    assert "fallidas: 1" in capsys.readouterr().out
