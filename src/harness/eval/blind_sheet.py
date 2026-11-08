"""Blind sheet for human judges and its separate key.

Render paths of a candidate live under ``runs/<run>/<piece>/<variant>/...`` and therefore
contain the variant name, so renders are copied to ``eval/blind/<blind_id>/<view>.png`` and
the sheet references those copies (paths relative to the eval directory).

Blind ids are stable across re-evaluations: when ``blind_key.csv`` already exists, every
``(piece, variant, candidate) → blind_id`` it holds is kept (even for candidates no longer
present, so an id is never reused) and only new candidates get fresh ids, after the highest
existing one. The key and the sheet carry an ``eval_id`` column: a short hash fixed when the
key is first created and kept while it is extended, so a judge's sheet can be matched to the
key it was dealt from (``report --sheets`` rejects a sheet with another ``eval_id``).
"""

from __future__ import annotations

import csv
import hashlib
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
    "eval_id",
    "fotos",
    *(f"render_{view}" for view in VIEWS),
    *SCORE_COLUMNS,
)
KEY_COLUMNS: tuple[str, ...] = ("blind_id", "piece_id", "variant", "candidate", "eval_id")
EVAL_ID_LENGTH = 12


@dataclass(frozen=True)
class CandidateRef:
    piece_id: str
    variant: str
    candidate: int


def _ref_order(ref: CandidateRef) -> tuple[str, str, int]:
    return (ref.piece_id, ref.variant, ref.candidate)


def _id_number(blind_id: str) -> int:
    digits = blind_id.removeprefix("B")
    return int(digits) if digits.isdigit() else 0


def assign_blind_ids(
    refs: list[CandidateRef],
    seed: int = DEFAULT_SEED,
    *,
    existing: dict[str, CandidateRef] | None = None,
) -> list[tuple[str, CandidateRef]]:
    """Seeded shuffle (independent of input order) and ids ``B001``, ``B002``…

    ``existing`` (a previous ``blind_key.csv``): its assignments are kept; only refs not in
    it get new ids, numbered after the highest existing id and shuffled among themselves.
    Returns the pairs for ``refs`` only, sorted by blind id.
    """
    previous = {ref: blind_id for blind_id, ref in (existing or {}).items()}
    kept = [(previous[ref], ref) for ref in refs if ref in previous]
    new = sorted({ref for ref in refs if ref not in previous}, key=_ref_order)
    random.Random(seed).shuffle(new)
    start = max((_id_number(b) for b in previous.values()), default=0) + 1
    fresh = [(f"B{i:03d}", ref) for i, ref in enumerate(new, start=start)]
    return sorted(kept + fresh, key=lambda pair: (_id_number(pair[0]), pair[0]))


def compute_eval_id(key: dict[str, CandidateRef], salt: str = "") -> str:
    """Short hash of the sorted key rows (``salt``, e.g. the run id, makes it run-specific)."""
    rows = sorted(f"{b},{r.piece_id},{r.variant},{r.candidate}" for b, r in key.items())
    digest = hashlib.sha256("\n".join([salt, *rows]).encode("utf-8")).hexdigest()
    return digest[:EVAL_ID_LENGTH]


def copy_blind_renders(renders: list[Path], eval_dir: Path, blind_id: str) -> list[Path]:
    """Copy the view PNGs to ``eval_dir/blind/<blind_id>/``; returns the copies."""
    target = Path(eval_dir) / "blind" / blind_id
    if target.exists():
        shutil.rmtree(target)  # stale renders of a previous evaluation
    target.mkdir(parents=True)
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
    *,
    eval_id: str | None = None,
    retired: dict[str, CandidateRef] | None = None,
) -> str:
    """``entries`` = (blind_id, ref, photos, blind render copies), already in blind order.

    ``retired``: key rows of earlier evaluations whose candidate is gone; kept in the key
    (not in the sheet) so their ids are never dealt again. ``eval_id`` None → computed from
    the key rows. Returns the ``eval_id`` written to both files.
    """
    key_rows = {blind_id: ref for blind_id, ref, _photos, _renders in entries}
    for blind_id, ref in (retired or {}).items():
        key_rows.setdefault(blind_id, ref)
    eval_id = eval_id or compute_eval_id(key_rows)
    base = Path(sheet_path).parent
    with Path(sheet_path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for blind_id, _ref, photos, renders in entries:
            row = {col: "" for col in SHEET_COLUMNS}
            row["blind_id"] = blind_id
            row["eval_id"] = eval_id
            row["fotos"] = ";".join(str(p) for p in photos)
            by_view = {Path(r).stem: r for r in renders}
            for view in VIEWS:
                if view in by_view:
                    row[f"render_{view}"] = _relative(by_view[view], base)
            writer.writerow(row)
    with Path(key_path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=KEY_COLUMNS)
        writer.writeheader()
        for blind_id, ref in sorted(key_rows.items(), key=lambda kv: (_id_number(kv[0]), kv[0])):
            writer.writerow(
                {
                    "blind_id": blind_id,
                    "piece_id": ref.piece_id,
                    "variant": ref.variant,
                    "candidate": ref.candidate,
                    "eval_id": eval_id,
                }
            )
    return eval_id


def read_blind_key(key_path: Path) -> dict[str, CandidateRef]:
    with Path(key_path).open(newline="", encoding="utf-8") as fh:
        return {
            row["blind_id"]: CandidateRef(row["piece_id"], row["variant"], int(row["candidate"]))
            for row in csv.DictReader(fh)
        }


def read_key_eval_id(key_path: Path) -> str:
    """The key's ``eval_id``: its stamp, or (keys written before the stamp) the hash of
    its rows."""
    with Path(key_path).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    stamps = {(row.get("eval_id") or "").strip() for row in rows} - {""}
    if len(stamps) == 1:
        return stamps.pop()
    return compute_eval_id(
        {
            r["blind_id"]: CandidateRef(r["piece_id"], r["variant"], int(r["candidate"]))
            for r in rows
        }
    )


def _relative(path: Path, base: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)
