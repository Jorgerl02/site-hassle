"""Evaluate the automatic photo interpretation on the 30 pilot pieces.

Runs :class:`platform_worker.interpret.SilhouetteInterpreter` with real rembg on the first
photo of every piece in ``data/sample.csv`` and compares it with
``tests/fixtures/platform/interpret_labels.csv``: a per-piece table, then the accuracy of
``rectilinear`` (all pieces), ``support`` (pieces labelled rectilinear) and ``kind``. Both
with the piece names/descriptions and name-blind (photo + dimensions only).

    HARNESS_INTERPRET_EVAL=1 uv run python scripts/eval_interpret.py [--mode both|names|blind]
        [--mask-cache DIR]

``--mask-cache`` stores the rembg masks as PNG so re-runs skip background removal.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from platform_worker.interpret import Interpretation, SilhouetteInterpreter, rembg_mask

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "data" / "sample.csv"
LABELS_CSV = ROOT / "tests" / "fixtures" / "platform" / "interpret_labels.csv"

# Targets of the task brief.
TARGET_RECTILINEAR_NAMES = 0.85
TARGET_RECTILINEAR_BLIND = 0.75
TARGET_SUPPORT = 0.70
REQUIRED_SUPPORT_IDS = ("p03", "p07", "p08")


@dataclass(frozen=True)
class Row:
    id: str
    truth: dict[str, object]
    pred: Interpretation


@dataclass(frozen=True)
class Scores:
    rectilinear: float
    support: float
    kind: float
    rows: list[Row]

    def support_ok(self, piece_id: str) -> bool:
        row = next(r for r in self.rows if r.id == piece_id)
        return row.pred.support == row.truth["support"]


def load_labels(path: Path = LABELS_CSV) -> dict[str, dict[str, object]]:
    with path.open(encoding="utf-8") as fh:
        return {
            row["id"]: {
                "rectilinear": row["rectilinear"].strip().lower() == "true",
                "support": row["support"].strip() or None,
                "kind": row["kind"].strip() or None,
            }
            for row in csv.DictReader(fh)
        }


def load_pieces(path: Path = SAMPLE_CSV) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cached_masker(cache: Path | None) -> Callable[[Path], np.ndarray]:
    """rembg masks, memoised in memory and (optionally) as PNG files under ``cache``."""
    memo: dict[Path, np.ndarray] = {}

    def masker(path: Path) -> np.ndarray:
        if path in memo:
            return memo[path]
        file = cache / f"{path.parent.name}_{path.stem}.png" if cache else None
        if file is not None and file.is_file():
            mask = np.asarray(Image.open(file)) > 0
        else:
            mask = rembg_mask(path)
            if file is not None:
                file.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(mask.astype(np.uint8) * 255).save(file)
        memo[path] = mask
        return mask

    return masker


def evaluate(
    pieces: list[dict[str, str]],
    labels: dict[str, dict[str, object]],
    masker: Callable[[Path], np.ndarray],
    *,
    use_names: bool,
) -> Scores:
    interpreter = SilhouetteInterpreter(masker=masker)
    rows: list[Row] = []
    for piece in pieces:
        first = ROOT / piece["images"].split(";")[0]
        pred = interpreter.interpret(
            [first],
            width_cm=float(piece["width_cm"]),
            height_cm=float(piece["height_cm"]),
            depth_cm=float(piece["depth_cm"]),
            name=piece["name"] if use_names else "",
            notes=piece["description"] if use_names else "",
        )
        rows.append(Row(piece["id"], labels[piece["id"]], pred))
    rect_ok = [r.pred.rectilinear == r.truth["rectilinear"] for r in rows]
    sup_ok = [r.pred.support == r.truth["support"] for r in rows if r.truth["rectilinear"]]
    kind_ok = [r.pred.kind == r.truth["kind"] for r in rows]
    return Scores(
        rectilinear=sum(rect_ok) / len(rect_ok),
        support=sum(sup_ok) / len(sup_ok) if sup_ok else 0.0,
        kind=sum(kind_ok) / len(kind_ok),
        rows=rows,
    )


def _mark(ok: bool) -> str:
    return " " if ok else "✗"


def print_report(title: str, scores: Scores) -> None:
    print(f"\n== {title} ==")
    print(f"{'id':4} {'rect':>11}  {'support':>16}  {'kind':>22}  conf  reasons")
    for r in scores.rows:
        t, p = r.truth, r.pred
        rect = f"{p.rectilinear!s:>5}/{t['rectilinear']!s:<5}"
        sup = f"{p.support!s:>7}/{t['support']!s:<7}"
        kind = f"{p.kind!s:>10}/{t['kind']!s:<10}"
        sup_ok = p.support == t["support"] or not t["rectilinear"]
        print(
            f"{r.id:4} {rect}{_mark(p.rectilinear == t['rectilinear'])} "
            f"{sup}{_mark(sup_ok)} {kind}{_mark(p.kind == t['kind'])} "
            f"{p.confidence:4.2f}  {' | '.join(p.reasons)}"
        )
    n_rect = sum(1 for r in scores.rows if r.truth["rectilinear"])
    print(
        f"rectilinear {scores.rectilinear:.0%} ({round(scores.rectilinear * len(scores.rows))}"
        f"/{len(scores.rows)})  support on rectilinear {scores.support:.0%} "
        f"({round(scores.support * n_rect)}/{n_rect})  kind {scores.kind:.0%}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("both", "names", "blind"), default="both")
    parser.add_argument("--mask-cache", type=Path, default=None)
    args = parser.parse_args(argv)
    pieces, labels = load_pieces(), load_labels()
    masker = cached_masker(args.mask_cache)
    if args.mode in ("both", "names"):
        print_report("with name + notes", evaluate(pieces, labels, masker, use_names=True))
    if args.mode in ("both", "blind"):
        print_report("name-blind", evaluate(pieces, labels, masker, use_names=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
