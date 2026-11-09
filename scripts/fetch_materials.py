"""Download the CC0 PBR library (ambientCG 1K-JPG) into ``data/materials/<id>/``.

    uv run python scripts/fetch_materials.py [--force] [--only travertine oak] [--dest DIR]

Reads ``src/harness/post/materials.json``. For each material it downloads the zip, extracts
ONLY the ``<Asset>_1K-JPG_{Color,NormalGL,Roughness}.jpg`` members (by name, never by path,
so a hostile zip cannot write elsewhere) as ``Color.jpg``, ``NormalGL.jpg`` and
``Roughness.jpg``, checks each is a decodable JPEG and records ``source.json`` (asset, URL,
licence, sha256 of every map). Idempotent: a material whose maps already verify is skipped
unless ``--force``. ``data/materials/`` is gitignored.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

from harness.post.materials import DEFAULT_MATERIALS_DIR, MAP_NAMES, Material, load_manifest

USER_AGENT = "site-hassle-estudio/fetch_materials (+https://ambientcg.com CC0)"
TIMEOUT_S = 120
MAX_ZIP_BYTES = 80_000_000
SOURCE_FILENAME = "source.json"


def verify_jpeg(path: Path) -> tuple[int, int]:
    """(width, height) of a decodable JPEG; raises ValueError otherwise."""
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8\xff"):
        raise ValueError(f"{path} no es un JPEG")
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        return img.size


def is_complete(material: Material, dest: Path) -> bool:
    folder = dest / material.id
    if not (folder / SOURCE_FILENAME).is_file():
        return False
    try:
        for name in MAP_NAMES:
            verify_jpeg(folder / f"{name}.jpg")
    except (OSError, ValueError):
        return False
    return True


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 — https
        data = response.read(MAX_ZIP_BYTES + 1)
    if len(data) > MAX_ZIP_BYTES:
        raise ValueError(f"{url}: el zip supera {MAX_ZIP_BYTES} bytes")
    return data


def extract_maps(material: Material, archive: bytes, dest: Path) -> dict[str, dict]:
    folder = dest / material.id
    folder.mkdir(parents=True, exist_ok=True)
    maps: dict[str, dict] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        names = set(zf.namelist())
        for map_name in MAP_NAMES:
            member = f"{material.asset}_1K-JPG_{map_name}.jpg"
            if member not in names:
                raise ValueError(f"{material.asset}: el zip no trae {member}")
            data = zf.read(member)
            target = folder / f"{map_name}.jpg"
            target.write_bytes(data)
            width, height = verify_jpeg(target)
            maps[map_name] = {
                "file": target.name,
                "member": member,
                "size": [width, height],
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
    return maps


def fetch(material: Material, dest: Path, *, force: bool = False) -> str:
    if not force and is_complete(material, dest):
        return "ya estaba"
    maps = extract_maps(material, download(material.url), dest)
    source = {
        "id": material.id,
        "asset": material.asset,
        "url": material.url,
        "license": material.license,
        "maps": maps,
    }
    (dest / material.id / SOURCE_FILENAME).write_text(
        json.dumps(source, indent=2) + "\n", encoding="utf-8"
    )
    return "descargado"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dest", type=Path, default=DEFAULT_MATERIALS_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", nargs="*", default=None, help="ids del manifiesto")
    args = parser.parse_args(argv)
    manifest = load_manifest()
    ids = args.only or list(manifest)
    unknown = [i for i in ids if i not in manifest]
    if unknown:
        parser.error(f"ids desconocidos: {', '.join(unknown)}")
    failures = 0
    for material_id in ids:
        material = manifest[material_id]
        try:
            status = fetch(material, args.dest, force=args.force)
            print(f"{material.id:14} {material.asset:14} {status}")
        except Exception as exc:  # noqa: BLE001 — report every material, fail at the end
            failures += 1
            print(f"{material.id:14} {material.asset:14} ERROR {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
