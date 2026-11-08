"""Human judge sheets: reading, joining with the blind key, agreement and per-variant rates.

A human sheet is a copy of ``blind_sheet.csv`` filled in by one judge (the judge name is
the file stem unless given explicitly). Empty cells mean "not judged": a row only counts
for the apt rate and for agreement when its ``apto`` cell is filled in.

Unit of the apt rate: the piece, as in the automatic report. For a judge and a variant, a
piece counts if the judge marked ``apto`` on at least one of its candidates, and it is apt
if at least one of those candidates is apt.

Agreement is computed per pair of judges over the ``blind_id`` both judged: percentage of
equal ``apto`` labels and Cohen's kappa over the binary label. The automatic VLM judge
(``scores.jsonl``) takes part as one more judge when its labels are given. ``auto_labels``
only takes ``status == "scored"`` records, so it leaves out ``candidate_failed`` candidates
(the VLM never judged them), whereas the automatic report counts those as not apt.
"""

from __future__ import annotations

import csv
import io
import itertools
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.eval.blind_sheet import CandidateRef, read_blind_key, read_key_eval_id

AUTO_JUDGE = "juez automático"
AXES: tuple[str, ...] = ("parecido", "geometria", "materiales", "escala")
REQUIRED_COLUMNS = frozenset({"blind_id", "apto"})
_YES = frozenset({"si", "s", "yes", "y", "1", "true", "apto"})
_NO = frozenset({"no", "n", "0", "false", "no apto"})


@dataclass(frozen=True)
class HumanScore:
    parecido: float | None = None
    geometria: float | None = None
    materiales: float | None = None
    escala: float | None = None
    apto: bool | None = None
    comentario: str = ""

    @property
    def judged(self) -> bool:
        return self.apto is not None or any(getattr(self, a) is not None for a in AXES)


@dataclass(frozen=True)
class JudgedRecord:
    judge: str
    blind_id: str
    piece_id: str
    variant: str
    candidate: int
    score: HumanScore


@dataclass(frozen=True)
class PairAgreement:
    judge_a: str
    judge_b: str
    n: int  # blind_id with an apt label from both judges
    agree_pct: float | None
    kappa: float | None  # None when undefined (no overlap, or both labels constant)


@dataclass
class AgreementStats:
    pairs: list[PairAgreement] = field(default_factory=list)


@dataclass
class HumanSummary:
    """What ``report.render_markdown(..., human=...)`` renders."""

    judges: list[str]
    by_variant: dict[str, dict[str, tuple[int, int]]]  # judge → variant → (apt, n) pieces
    agreement: AgreementStats
    has_auto: bool = False


def parse_apto(value: str | None) -> bool | None:
    """``sí``/``si``/``s``/``yes``/``1`` → True, ``no``/``n``/``0`` → False, empty → None."""
    text = _normalize(value)
    if not text:
        return None
    if text in _YES:
        return True
    if text in _NO:
        return False
    raise ValueError(f"valor de «apto» no reconocido: {value!r} (usa «sí» o «no»)")


def _sheet_reader(path: Path) -> csv.DictReader:
    text = Path(path).read_text(encoding="utf-8-sig")
    header = text.splitlines()[0] if text else ""
    delimiter = ";" if header.count(";") > header.count(",") else ","
    return csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)


def read_sheet_eval_id(path: Path) -> str | None:
    """The sheet's ``eval_id`` stamp; ``None`` for sheets written before the stamp existed.

    Raises ``ValueError`` when the sheet mixes rows of different evaluations."""
    reader = _sheet_reader(path)
    if "eval_id" not in (reader.fieldnames or ()):
        return None
    stamps = sorted({(row.get("eval_id") or "").strip() for row in reader} - {""})
    if len(stamps) > 1:
        raise ValueError(
            f"{Path(path).name}: mezcla filas de varias evaluaciones (eval_id {', '.join(stamps)})"
        )
    return stamps[0] if stamps else None


def read_sheet(path: Path) -> dict[str, HumanScore]:
    """Read a filled-in blind sheet; empty cells become ``None``. Accepts ``,`` or ``;``."""
    name = Path(path).name
    reader = _sheet_reader(path)
    missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames or ()))
    if missing:
        raise ValueError(f"{name}: faltan columnas obligatorias: {', '.join(missing)}")
    scores: dict[str, HumanScore] = {}
    for row in reader:
        blind_id = (row.get("blind_id") or "").strip()
        if not blind_id:
            continue
        if blind_id in scores:
            raise ValueError(f"{name}: blind_id repetido en la hoja: {blind_id}")
        try:
            apto = parse_apto(row.get("apto"))
        except ValueError as exc:
            raise ValueError(f"{name}, {blind_id}: {exc}") from None
        scores[blind_id] = HumanScore(
            **{axis: _rating(row.get(axis)) for axis in AXES},
            apto=apto,
            comentario=(row.get("comentario") or "").strip(),
        )
    return scores


def merge(
    key: dict[str, CandidateRef], sheets: dict[str, dict[str, HumanScore]]
) -> list[JudgedRecord]:
    """Join each judge's judged rows with the blind key; unknown ``blind_id`` is an error."""
    records: list[JudgedRecord] = []
    for judge, sheet in sheets.items():
        unknown = sorted(b for b, s in sheet.items() if s.judged and b not in key)
        if unknown:
            raise ValueError(
                f"hoja de {judge}: blind_id sin entrada en la clave: {', '.join(unknown)}"
            )
        for blind_id, score in sorted(sheet.items()):
            if not score.judged:
                continue
            ref = key[blind_id]
            records.append(
                JudgedRecord(judge, blind_id, ref.piece_id, ref.variant, ref.candidate, score)
            )
    return records


def check_eval_ids(
    key_path: Path, sheet_paths: list[Path], warnings: list[str] | None = None
) -> None:
    """Reject (``ValueError``) a sheet stamped with another ``eval_id`` than the key's;
    unstamped (older) sheets are accepted with a warning appended to ``warnings``."""
    current = read_key_eval_id(key_path)
    for path in sheet_paths:
        stamp = read_sheet_eval_id(path)
        if stamp is None:
            if warnings is not None:
                warnings.append(
                    f"{Path(path).name}: hoja sin eval_id (anterior a la marca); no se puede "
                    f"comprobar que corresponda a la clave actual (eval_id {current})"
                )
        elif stamp != current:
            raise ValueError(
                f"{Path(path).name}: la hoja es de otra evaluación (eval_id {stamp}) y la "
                f"clave actual tiene eval_id {current}; sus blind_id no corresponden a los "
                "candidatos actuales"
            )


def load_sheets(
    key_path: Path, sheet_paths: list[Path], *, warnings: list[str] | None = None
) -> list[JudgedRecord]:
    """Read the key and every sheet (judge name = file stem) and join them.

    Each sheet's ``eval_id`` is checked against the key first (see :func:`check_eval_ids`).
    """
    names = [Path(p).stem for p in sheet_paths]
    if len(set(names)) != len(names):
        raise ValueError("dos hojas con el mismo nombre de juez (nombre del archivo)")
    check_eval_ids(key_path, sheet_paths, warnings)
    sheets = {name: read_sheet(p) for name, p in zip(names, sheet_paths, strict=True)}
    return merge(read_blind_key(key_path), sheets)


def auto_labels(scores: list[dict[str, Any]]) -> dict[str, bool]:
    """``blind_id`` → apt label of the automatic judge, from ``scores.jsonl`` records."""
    labels: dict[str, bool] = {}
    for rec in scores:
        blind_id = rec.get("blind_id")
        rec_scores = rec.get("scores")
        if blind_id and rec.get("status") == "scored" and rec_scores:
            labels[str(blind_id)] = bool(rec_scores["apt"])
    return labels


def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    """Cohen's kappa for two binary label lists; None when undefined (empty or p_e = 1)."""
    if len(a) != len(b):
        raise ValueError("listas de etiquetas de distinta longitud")
    n = len(a)
    if not n:
        return None
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected >= 1.0:
        return None
    return (observed - expected) / (1 - expected)


def agreement(records: list[JudgedRecord], auto: dict[str, bool] | None = None) -> AgreementStats:
    """Agreement on ``apto`` for every pair of judges (plus the automatic one, if given)."""
    labels: dict[str, dict[str, bool]] = {}
    for rec in records:
        if rec.score.apto is not None:
            labels.setdefault(rec.judge, {})[rec.blind_id] = rec.score.apto
    judges = sorted(labels)
    if auto:
        labels[AUTO_JUDGE] = dict(auto)
        judges.append(AUTO_JUDGE)
    stats = AgreementStats()
    for ja, jb in itertools.combinations(judges, 2):
        common = sorted(set(labels[ja]) & set(labels[jb]))
        a = [labels[ja][b] for b in common]
        b = [labels[jb][b] for b in common]
        agree = (
            100.0 * sum(x == y for x, y in zip(a, b, strict=True)) / len(common) if common else None
        )
        stats.pairs.append(PairAgreement(ja, jb, len(common), agree, cohen_kappa(a, b)))
    return stats


def summarize_by_variant(records: list[JudgedRecord]) -> dict[str, dict[str, tuple[int, int]]]:
    """judge → variant → (apt pieces, judged pieces); piece apt if any candidate is apt."""
    pieces: dict[tuple[str, str, str], bool] = {}
    for rec in records:
        if rec.score.apto is None:
            continue
        key = (rec.judge, rec.variant, rec.piece_id)
        pieces[key] = pieces.get(key, False) or rec.score.apto
    out: dict[str, dict[str, tuple[int, int]]] = {}
    for (judge, variant, _pid), apt in sorted(pieces.items()):
        n_apt, n = out.setdefault(judge, {}).get(variant, (0, 0))
        out[judge][variant] = (n_apt + int(apt), n + 1)
    return out


def build_human_summary(
    records: list[JudgedRecord], scores: list[dict[str, Any]] | None = None
) -> HumanSummary:
    """Everything the report needs; ``scores`` (``scores.jsonl``) adds the automatic judge."""
    auto = auto_labels(scores) if scores else {}
    return HumanSummary(
        judges=sorted({r.judge for r in records}),
        by_variant=summarize_by_variant(records),
        agreement=agreement(records, auto or None),
        has_auto=bool(auto),
    )


def _normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _rating(value: str | None) -> float | None:
    text = (value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
