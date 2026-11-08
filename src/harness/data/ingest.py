"""Download the sample's source images to ``data/images/<id>/<n>.jpg``.

Reads ``image_urls`` (``;``-separated) from the sample CSV; never edits the CSV. Images
already on disk are skipped. Every failure is recorded in ``ingest_report.json`` instead of
aborting the run. Usage: ``uv run python -m harness.data.ingest [--csv data/sample.csv]``.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

from harness.core.models import DEFAULT_SAMPLE_CSV

DEFAULT_IMAGES_ROOT = Path("data/images")
REPORT_FILENAME = "ingest_report.json"
MAX_RETRIES = 2  # retries after the first attempt
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass
class ImageRecord:
    piece_id: str
    index: int
    url: str
    path: str
    error: str = ""


@dataclass
class IngestReport:
    csv_path: str
    images_root: str
    started_at: str
    downloaded: list[ImageRecord] = field(default_factory=list)
    skipped: list[ImageRecord] = field(default_factory=list)
    failures: list[ImageRecord] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict:
        data = asdict(self)
        data["summary"] = {
            "downloaded": len(self.downloaded),
            "skipped": len(self.skipped),
            "failed": len(self.failures),
        }
        return data


class _DownloadError(RuntimeError):
    pass


def image_targets(csv_path: Path, images_root: Path) -> list[tuple[str, int, str, Path]]:
    """(piece_id, n, url, destination) for every ``image_urls`` entry, n starting at 1."""
    targets: list[tuple[str, int, str, Path]] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if "image_urls" not in (reader.fieldnames or []):
            raise ValueError(f"{csv_path}: falta la columna image_urls")
        for row in reader:
            piece_id = row["id"].strip()
            urls = [u.strip() for u in (row["image_urls"] or "").split(";") if u.strip()]
            for n, url in enumerate(urls, start=1):
                targets.append((piece_id, n, url, images_root / piece_id / f"{n}.jpg"))
    return targets


def _to_jpeg(content: bytes) -> bytes:
    """Return JPEG bytes; re-encode anything that is not already a JPEG."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.load()
            if img.format == "JPEG":
                return content
            if img.mode in ("RGBA", "LA", "P"):
                rgba = img.convert("RGBA")
                flat = Image.new("RGB", rgba.size, (255, 255, 255))
                flat.paste(rgba, mask=rgba.split()[-1])
            else:
                flat = img.convert("RGB")
    except Exception as exc:  # Pillow raises several types for undecodable data
        raise _DownloadError(f"la respuesta no es una imagen válida: {exc}") from exc
    buf = io.BytesIO()
    flat.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _fetch(
    client: httpx.Client, url: str, max_retries: int, backoff_s: float, sleep: Callable
) -> bytes:
    last_error = ""
    for attempt in range(max_retries + 1):
        if attempt:
            sleep(backoff_s * attempt)
        try:
            response = client.get(url)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        if response.status_code == 200:
            return response.content
        last_error = f"HTTP {response.status_code}"
        if response.status_code not in _RETRY_STATUS:
            break  # client errors (404, 403…) will not fix themselves
    raise _DownloadError(last_error)


def ingest(
    csv_path: Path = DEFAULT_SAMPLE_CSV,
    images_root: Path = DEFAULT_IMAGES_ROOT,
    timeout_s: float = 30,
    *,
    client: httpx.Client | None = None,
    max_retries: int = MAX_RETRIES,
    backoff_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> IngestReport:
    """Download every image listed in ``image_urls``; write ``<images_root>/ingest_report.json``."""
    images_root = Path(images_root)
    report = IngestReport(
        csv_path=str(csv_path),
        images_root=str(images_root),
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    targets = image_targets(Path(csv_path), images_root)
    own_client = client is None
    if client is None:
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"},
            follow_redirects=True,
            timeout=timeout_s,
        )
    try:
        for piece_id, n, url, dst in targets:
            record = ImageRecord(piece_id=piece_id, index=n, url=url, path=str(dst))
            if dst.exists() and dst.stat().st_size > 0:
                report.skipped.append(record)
                continue
            try:
                data = _to_jpeg(_fetch(client, url, max_retries, backoff_s, sleep))
            except _DownloadError as exc:
                record.error = str(exc)
                report.failures.append(record)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(dst)
            report.downloaded.append(record)
    finally:
        if own_client:
            client.close()

    images_root.mkdir(parents=True, exist_ok=True)
    (images_root / REPORT_FILENAME).write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m harness.data.ingest",
        description="Descarga las imágenes de la muestra a data/images/<id>/<n>.jpg.",
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_SAMPLE_CSV, help="CSV de la muestra")
    parser.add_argument(
        "--images-root", type=Path, default=DEFAULT_IMAGES_ROOT, help="carpeta de destino"
    )
    parser.add_argument("--timeout", type=float, default=30, help="timeout por petición (s)")
    args = parser.parse_args(argv)

    report = ingest(args.csv, args.images_root, args.timeout)
    print(
        f"Descargadas: {len(report.downloaded)} · ya existían: {len(report.skipped)} · "
        f"fallidas: {len(report.failures)}"
    )
    for f in report.failures:
        print(f"  ✗ {f.piece_id}/{f.index}: {f.error} ({f.url})")
    print(f"Informe: {Path(args.images_root) / REPORT_FILENAME}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
