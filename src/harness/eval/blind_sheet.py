"""Blind sheet for human judges and its separate key.

Render paths of a candidate live under ``runs/<run>/<piece>/<variant>/...`` and therefore
contain the variant name, so renders are copied to ``eval/blind/<blind_id>/<view>.png`` and
the sheet references those copies (paths relative to the eval directory).
"""

from __future__ import annotations

import csv
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from harness.eval.render import VIEWS

DEFAULT_SEED = 20261108
SCORE_COLUMNS: tuple[str, ...] = (
    "parecido",
    "geometria",
    "materiales",
    "escala",
    "apto",
    "comentario",
)
SHEET_COLUMNS: tuple[str, ...] = (
    "blind_id",
    "fotos",
    *(f"render_{view}" for view in VIEWS),
    *SCORE_COLUMNS,
)
KEY_COLUMNS: tuple[str, ...] = ("blind_id", "piece_id", "variant", "candidate")


@dataclass(frozen=True)
class CandidateRef:
    piece_id: str
    variant: str
    candidate: int


def assign_blind_ids(
    refs: list[CandidateRef], seed: int = DEFAULT_SEED
) -> list[tuple[str, CandidateRef]]:
    """Seeded shuffle (independent of input order) and ids ``B001``, ``B002``…"""
    ordered = sorted(refs, key=lambda r: (r.piece_id, r.variant, r.candidate))
    random.Random(seed).shuffle(ordered)
    return [(f"B{i:03d}", ref) for i, ref in enumerate(ordered, start=1)]


def copy_blind_renders(renders: list[Path], eval_dir: Path, blind_id: str) -> list[Path]:
    """Copy the view PNGs to ``eval_dir/blind/<blind_id>/``; returns the copies."""
    target = Path(eval_dir) / "blind" / blind_id
    target.mkdir(parents=True, exist_ok=True)
    copies = []
    for src in renders:
        dst = target / Path(src).name
        shutil.copyfile(src, dst)
        copies.append(dst)
    return copies


def write_blind_sheet(
    sheet_path: Path,
    key_path: Path,
    entries: list[tuple[str, CandidateRef, list[Path], list[Path]]],
) -> None:
    """``entries`` = (blind_id, ref, photos, blind render copies), already in blind order."""
    base = Path(sheet_path).parent
    with Path(sheet_path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for blind_id, _ref, photos, renders in entries:
            row = {col: "" for col in SHEET_COLUMNS}
            row["blind_id"] = blind_id
            row["fotos"] = ";".join(str(p) for p in photos)
            by_view = {Path(r).stem: r for r in renders}
            for view in VIEWS:
                if view in by_view:
                    row[f"render_{view}"] = _relative(by_view[view], base)
            writer.writerow(row)
    with Path(key_path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=KEY_COLUMNS)
        writer.writeheader()
        for blind_id, ref, _photos, _renders in entries:
            writer.writerow(
                {
                    "blind_id": blind_id,
                    "piece_id": ref.piece_id,
                    "variant": ref.variant,
                    "candidate": ref.candidate,
                }
            )


def read_blind_key(key_path: Path) -> dict[str, CandidateRef]:
    with Path(key_path).open(newline="", encoding="utf-8") as fh:
        return {
            row["blind_id"]: CandidateRef(row["piece_id"], row["variant"], int(row["candidate"]))
            for row in csv.DictReader(fh)
        }


def _relative(path: Path, base: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)
