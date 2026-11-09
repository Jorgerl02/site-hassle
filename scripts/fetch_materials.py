"""Download the CC0 PBR library (ambientCG 1K-JPG) into ``data/materials/<id>/``.

    uv run python scripts/fetch_materials.py [--force] [--only travertine oak] [--dest DIR]
                                             [--update-hashes]

Reads ``src/harness/post/materials.json``. For each material it downloads the zip over
HTTPS from ``ambientcg.com`` (redirects are followed only to ambientCG's own download CDN),
extracts ONLY the ``<Asset>_1K-JPG_{Color,NormalGL,Roughness}.jpg`` members (by exact
name, never by path, each capped at ``MAX_MAP_BYTES`` uncompressed) into a temporary folder
next to the destination, checks each is a decodable JPEG whose sha256 equals the one
pinned in the manifest, and only then swaps the folder into place (rename), so a failed
download never leaves a half-written material. ``source.json`` records asset, URL, final
URL, licence and hashes.

Pinned hashes: a mismatch is refused unless ``--update-hashes``, which accepts the new
files and rewrites the ``sha256`` block of ``materials.json`` (review the diff before
committing it). Idempotent: a material whose maps already verify is skipped unless
``--force``. ``data/materials/`` is gitignored.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

from harness.post.materials import (
    DEFAULT_MATERIALS_DIR,
    MANIFEST_PATH,
    MAP_NAMES,
    Material,
    load_manifest,
)

USER_AGENT = "site-hassle-estudio/fetch_materials (+https://ambientcg.com CC0)"
TIMEOUT_S = 120
MAX_ZIP_BYTES = 80_000_000
MAX_MAP_BYTES = 20_000_000  # a 1K JPEG map is ~1 MB; anything near this is not one
SOURCE_FILENAME = "source.json"
REQUEST_HOSTS = frozenset({"ambientcg.com"})
# ambientCG's /get endpoint answers with a redirect to its download CDN (seen 2026-11-09:
# https://acg-download.struffelproductions.com/file/ambientCG-Web/download/…).
DOWNLOAD_HOSTS = REQUEST_HOSTS | {"acg-download.struffelproductions.com"}


class FetchError(RuntimeError):
    """A download, archive or verification problem."""


class HashMismatch(FetchError):
    """A map's sha256 differs from the one pinned in the manifest."""


def check_url(url: str, hosts: frozenset[str] | set[str]) -> None:
    """Refuse anything but ``https://<allowed host>/…``."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in hosts:
        raise FetchError(f"URL no permitida: {url} (solo https a {', '.join(sorted(hosts))})")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to an allowed HTTPS host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        check_url(newurl, DOWNLOAD_HOSTS)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify_jpeg(path: Path) -> tuple[int, int]:
    """(width, height) of a decodable JPEG; raises ValueError otherwise."""
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8\xff"):
        raise ValueError(f"{path} no es un JPEG")
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        return img.size


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_complete(material: Material, dest: Path) -> bool:
    """Every map present, decodable and (when pinned) with the pinned hash."""
    folder = dest / material.id
    if not (folder / SOURCE_FILENAME).is_file():
        return False
    try:
        for name in MAP_NAMES:
            path = folder / f"{name}.jpg"
            verify_jpeg(path)
            pinned = material.sha256.get(name)
            if pinned and sha256_file(path) != pinned:
                return False
    except (OSError, ValueError):
        return False
    return True


def download(url: str) -> tuple[bytes, str]:
    """``(body, final URL)``; the request and every redirect must stay on allowed hosts."""
    check_url(url, REQUEST_HOSTS)
    opener = urllib.request.build_opener(_CheckedRedirects)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=TIMEOUT_S) as response:
        final_url = response.geturl()
        check_url(final_url, DOWNLOAD_HOSTS)
        data = response.read(MAX_ZIP_BYTES + 1)
    if len(data) > MAX_ZIP_BYTES:
        raise FetchError(f"{url}: el zip supera {MAX_ZIP_BYTES} bytes")
    return data, final_url


def _read_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > MAX_MAP_BYTES:
        raise FetchError(
            f"{info.filename}: {info.file_size} bytes descomprimidos (> {MAX_MAP_BYTES})"
        )
    with zf.open(info) as fh:
        data = fh.read(MAX_MAP_BYTES + 1)  # the header can lie: cap the real stream too
    if len(data) > MAX_MAP_BYTES:
        raise FetchError(f"{info.filename}: supera {MAX_MAP_BYTES} bytes descomprimidos")
    return data


def extract_maps(
    material: Material, archive: bytes, folder: Path, *, update_hashes: bool = False
) -> dict[str, dict]:
    """Write the three maps into ``folder`` (a fresh temporary folder) and verify them."""
    maps: dict[str, dict] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        infos = {info.filename: info for info in zf.infolist()}
        for map_name in MAP_NAMES:
            member = f"{material.asset}_1K-JPG_{map_name}.jpg"
            if member not in infos:
                raise FetchError(f"{material.asset}: el zip no trae {member}")
            data = _read_member(zf, infos[member])
            target = folder / f"{map_name}.jpg"
            target.write_bytes(data)
            try:
                width, height = verify_jpeg(target)
            except (OSError, ValueError) as exc:
                raise FetchError(f"{member}: JPEG inválido ({exc})") from exc
            digest = hashlib.sha256(data).hexdigest()
            pinned = material.sha256.get(map_name)
            if pinned and digest != pinned and not update_hashes:
                raise HashMismatch(
                    f"{member}: sha256 {digest} ≠ fijado {pinned} "
                    "(usa --update-hashes si el cambio es legítimo)"
                )
            maps[map_name] = {
                "file": target.name,
                "member": member,
                "size": [width, height],
                "bytes": len(data),
                "sha256": digest,
            }
    return maps


def _swap_into_place(staging: Path, folder: Path) -> None:
    """Replace ``folder`` with ``staging`` by renames (same filesystem)."""
    backup = None
    if folder.exists():
        backup = folder.with_name(f".{folder.name}.old")
        shutil.rmtree(backup, ignore_errors=True)
        folder.rename(backup)
    staging.rename(folder)
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


def fetch(
    material: Material, dest: Path, *, force: bool = False, update_hashes: bool = False
) -> tuple[str, dict[str, str]]:
    """``(status, {map: sha256})`` for one material."""
    folder = dest / material.id
    if not force and not update_hashes and is_complete(material, dest):
        return "ya estaba", {n: sha256_file(folder / f"{n}.jpg") for n in MAP_NAMES}
    archive, final_url = download(material.url)
    dest.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{material.id}-", dir=dest))
    try:
        maps = extract_maps(material, archive, staging, update_hashes=update_hashes)
        source = {
            "id": material.id,
            "asset": material.asset,
            "url": material.url,
            "final_url": final_url,
            "license": material.license,
            "maps": maps,
        }
        (staging / SOURCE_FILENAME).write_text(json.dumps(source, indent=2) + "\n", "utf-8")
        _swap_into_place(staging, folder)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return "descargado", {name: info["sha256"] for name, info in maps.items()}


def write_pinned_hashes(hashes: dict[str, dict[str, str]], manifest: Path = MANIFEST_PATH) -> None:
    """Rewrite the ``sha256`` block of the given materials in ``materials.json``."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for entry in data["materials"]:
        if entry["id"] in hashes:
            entry["sha256"] = {name: hashes[entry["id"]][name] for name in MAP_NAMES}
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dest", type=Path, default=DEFAULT_MATERIALS_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--update-hashes",
        action="store_true",
        help="acepta hashes distintos de los fijados y reescribe materials.json",
    )
    parser.add_argument("--only", nargs="*", default=None, help="ids del manifiesto")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    ids = args.only or list(manifest)
    unknown = [i for i in ids if i not in manifest]
    if unknown:
        parser.error(f"ids desconocidos: {', '.join(unknown)}")
    failures = 0
    updated: dict[str, dict[str, str]] = {}
    for material_id in ids:
        material = manifest[material_id]
        try:
            status, hashes = fetch(
                material, args.dest, force=args.force, update_hashes=args.update_hashes
            )
            if args.update_hashes and hashes != material.sha256:
                updated[material_id] = hashes
                status += " (hashes actualizados)"
            print(f"{material.id:14} {material.asset:14} {status}")
        except Exception as exc:  # noqa: BLE001 — report every material, fail at the end
            failures += 1
            print(f"{material.id:14} {material.asset:14} ERROR {exc}", file=sys.stderr)
    if updated:
        write_pinned_hashes(updated, args.manifest)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
