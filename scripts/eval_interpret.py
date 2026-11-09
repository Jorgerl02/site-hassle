"""Evaluate the automatic photo interpretation on the 30 pilot pieces.

Runs :class:`platform_worker.interpret.SilhouetteInterpreter` with real rembg on the first
photo of every piece in ``data/sample.csv`` and compares it with
``tests/fixtures/platform/interpret_labels.csv``: a per-piece table, then the accuracy of
``rectilinear`` (all pieces), ``support`` (pieces labelled rectilinear) and ``kind``. Both
with the piece names/descriptions and name-blind (photo + dimensions only).

``rectilinear`` in the labels means "buildable by the parametric route E": it is
``data/sample.csv``'s column except p06 and p22, a round/oval top on one central column,
which became buildable with E's ``pedestal`` kind (2026-11-09). The accuracy against the
original column is printed too.

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

from platform_worker.interpret import (
    Interpretation,
    SilhouetteInterpreter,
    check_dimensions,
    merge_answers,
    rembg_mask,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "data" / "sample.csv"
LABELS_CSV = ROOT / "tests" / "fixtures" / "platform" / "interpret_labels.csv"
# The owner's real failure (2026-11-09): a round travertine top on one cylindrical pedestal,
# entered as kind=mesa, rectilinear=null, support=patas, 60 × 30 × 25 cm (W × H × D).
PEDESTAL_PHOTO = ROOT / "tests" / "fixtures" / "platform" / "travertine_pedestal.png"
PEDESTAL_CUSTOMER = {"kind": "mesa", "rectilinear": None, "support": "patas"}
PEDESTAL_DIMS = {"width_cm": 60.0, "height_cm": 30.0, "depth_cm": 25.0}

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
    warnings: list[str]


@dataclass(frozen=True)
class Scores:
    rectilinear: float
    rectilinear_csv: float  # against data/sample.csv's original column
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
        dims = {k: float(piece[k]) for k in ("width_cm", "height_cm", "depth_cm")}
        pred = interpreter.interpret(
            [first],
            **dims,
            name=piece["name"] if use_names else "",
            notes=piece["description"] if use_names else "",
        )
        rows.append(Row(piece["id"], labels[piece["id"]], pred, check_dimensions(pred, **dims)))
    rect_ok = [r.pred.rectilinear == r.truth["rectilinear"] for r in rows]
    csv_ok = [
        r.pred.rectilinear == (piece["rectilinear"] == "true")
        for r, piece in zip(rows, pieces, strict=True)
    ]
    sup_ok = [r.pred.support == r.truth["support"] for r in rows if r.truth["rectilinear"]]
    kind_ok = [r.pred.kind == r.truth["kind"] for r in rows]
    return Scores(
        rectilinear=sum(rect_ok) / len(rect_ok),
        rectilinear_csv=sum(csv_ok) / len(csv_ok),
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
    warned = [f"{r.id} ({len(r.warnings)})" for r in scores.rows if r.warnings]
    print(f"dimension warnings (false positives on catalogue data): {', '.join(warned) or '-'}")
    n_rect = sum(1 for r in scores.rows if r.truth["rectilinear"])
    print(
        f"rectilinear {scores.rectilinear:.0%} ({round(scores.rectilinear * len(scores.rows))}"
        f"/{len(scores.rows)}; {scores.rectilinear_csv:.0%} against sample.csv)  "
        f"support on rectilinear {scores.support:.0%} "
        f"({round(scores.support * n_rect)}/{n_rect})  kind {scores.kind:.0%}"
    )


@dataclass(frozen=True)
class PedestalCase:
    pred: Interpretation
    warnings: list[str]
    merged: dict[str, object]


def evaluate_pedestal(masker: Callable[[Path], np.ndarray]) -> PedestalCase:
    """The owner's travertine pedestal table with the customer's real answers."""
    pred = SilhouetteInterpreter(masker=masker).interpret([PEDESTAL_PHOTO], **PEDESTAL_DIMS)
    return PedestalCase(
        pred, check_dimensions(pred, **PEDESTAL_DIMS), merge_answers(PEDESTAL_CUSTOMER, pred)
    )


def print_pedestal(case: PedestalCase) -> None:
    p = case.pred
    print("\n== travertine_pedestal.png (customer: mesa, rectilinear null, patas, 60×30×25) ==")
    print(
        f"rectilinear={p.rectilinear} ({p.confidence:.2f}) support={p.support} "
        f"({p.support_confidence:.2f}) top_shape={p.top_shape} base_ratio={p.base_ratio} "
        f"photo_aspect={p.photo_aspect}"
    )
    print(f"reasons: {' | '.join(p.reasons)}")
    for warning in case.warnings:
        print(f"warning: {warning}")
    print(f"merge_answers: {case.merged}")


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
    print_pedestal(evaluate_pedestal(masker))
    return 0


if __name__ == "__main__":
    sys.exit(main())
