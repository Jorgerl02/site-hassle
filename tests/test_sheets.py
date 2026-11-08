from __future__ import annotations

from pathlib import Path

import pytest

from harness.eval.blind_sheet import CandidateRef
from harness.eval.report import VariantSummary, render_markdown
from harness.eval.sheets import (
    AUTO_JUDGE,
    HumanScore,
    agreement,
    auto_labels,
    build_human_summary,
    cohen_kappa,
    load_sheets,
    merge,
    parse_apto,
    read_sheet,
    summarize_by_variant,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sheets"
KEY = FIXTURES / "blind_key.csv"
SHEETS = [FIXTURES / "ana.csv", FIXTURES / "luis.csv"]


def test_read_sheet_tolerates_empty_cells() -> None:
    sheet = read_sheet(FIXTURES / "ana.csv")
    assert set(sheet) == {"B001", "B002", "B003", "B004", "B005", "B006"}
    assert sheet["B001"] == HumanScore(4, 4, 5, 4, True, "bien")
    assert sheet["B002"].apto is False and sheet["B002"].materiales is None
    assert sheet["B003"] == HumanScore() and not sheet["B003"].judged
    assert sheet["B004"].parecido == 4.5 and sheet["B004"].apto is True  # "4,5" and "Si"
    assert sheet["B005"].comentario == "patas cortas"


def test_read_sheet_semicolon_and_bom() -> None:
    sheet = read_sheet(FIXTURES / "luis.csv")
    assert {b: s.apto for b, s in sheet.items()} == {
        "B001": True,
        "B002": False,
        "B004": True,
        "B005": True,
        "B006": False,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sí", True),
        ("Si", True),
        ("s", True),
        ("yes", True),
        ("1", True),
        ("No", False),
        ("0", False),
        ("", None),
        ("  ", None),
        (None, None),
    ],
)
def test_parse_apto(value: str | None, expected: bool | None) -> None:
    assert parse_apto(value) is expected


def test_read_sheet_rejects_unknown_apto(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("blind_id,apto\nB001,quizá\n", encoding="utf-8")
    with pytest.raises(ValueError, match="B001"):
        read_sheet(path)


def test_read_sheet_requires_blind_id_and_apto(tmp_path: Path) -> None:
    path = tmp_path / "ana.csv"
    path.write_text("blind_id,parecido,apta\nB001,4,sí\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"ana\.csv.*apto"):
        read_sheet(path)
    path.write_text("id;apto\nB001;sí\n", encoding="utf-8")
    with pytest.raises(ValueError, match="blind_id"):
        read_sheet(path)
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="apto, blind_id"):
        read_sheet(path)


def test_read_sheet_keeps_multiline_comment(tmp_path: Path) -> None:
    path = tmp_path / "ana.csv"
    path.write_text(
        'blind_id,apto,comentario\r\nB001,sí,"patas cortas\nbrillo raro"\r\nB002,no,\r\n',
        encoding="utf-8",
    )
    sheet = read_sheet(path)
    assert sheet["B001"].comentario == "patas cortas\nbrillo raro"
    assert sheet["B002"].apto is False


def test_read_sheet_rejects_duplicate_blind_id(tmp_path: Path) -> None:
    path = tmp_path / "ana.csv"
    path.write_text("blind_id,apto\nB001,sí\nB001,no\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"ana\.csv.*B001"):
        read_sheet(path)


def test_merge_joins_with_key_and_skips_unjudged() -> None:
    records = load_sheets(KEY, SHEETS)
    ana = {r.blind_id: r for r in records if r.judge == "ana"}
    assert set(ana) == {"B001", "B002", "B004", "B005"}
    assert (ana["B002"].piece_id, ana["B002"].variant, ana["B002"].candidate) == ("p01", "A", 2)
    assert {r.judge for r in records} == {"ana", "luis"}


def test_merge_rejects_blind_id_missing_from_key() -> None:
    key = {"B001": CandidateRef("p01", "A", 1)}
    with pytest.raises(ValueError, match="B009"):
        merge(key, {"ana": {"B009": HumanScore(apto=True)}})
    # an unjudged row outside the key is ignored
    assert merge(key, {"ana": {"B009": HumanScore()}}) == []


def test_cohen_kappa_known_cases() -> None:
    labels = [True, False, True, False, True, True]
    assert cohen_kappa(labels, labels) == pytest.approx(1.0)
    # independent labels: observed agreement equals chance agreement
    a = [True, True, False, False] * 25
    b = [True, False, True, False] * 25
    assert cohen_kappa(a, b) == pytest.approx(0.0)
    assert cohen_kappa([True, False], [False, True]) == pytest.approx(-1.0)
    assert cohen_kappa([], []) is None
    assert cohen_kappa([True, True], [True, True]) is None  # both constant: undefined


def test_agreement_between_judges_and_auto() -> None:
    records = load_sheets(KEY, SHEETS)
    stats = agreement(records)
    assert len(stats.pairs) == 1
    pair = stats.pairs[0]
    assert (pair.judge_a, pair.judge_b, pair.n) == ("ana", "luis", 4)
    assert pair.agree_pct == pytest.approx(75.0)
    assert pair.kappa == pytest.approx(0.5)

    auto = {"B001": True, "B002": False, "B004": True, "B005": False}
    pairs = {(p.judge_a, p.judge_b): p for p in agreement(records, auto).pairs}
    assert pairs[("ana", AUTO_JUDGE)].kappa == pytest.approx(1.0)
    assert pairs[("luis", AUTO_JUDGE)].n == 4


def test_auto_labels_from_scores() -> None:
    scores = [
        {"blind_id": "B001", "status": "scored", "scores": {"apt": True}},
        {"blind_id": "B002", "status": "scored", "scores": {"apt": False}},
        {"blind_id": "B003", "status": "unscored", "scores": None},
        {"blind_id": None, "status": "generation_failed", "scores": None},
    ]
    assert auto_labels(scores) == {"B001": True, "B002": False}


def test_summarize_by_variant_piece_level() -> None:
    by = summarize_by_variant(load_sheets(KEY, SHEETS))
    assert by["ana"] == {"A": (1, 1), "E": (1, 2)}
    assert by["luis"] == {"A": (1, 1), "E": (2, 3)}


def test_render_markdown_human_section() -> None:
    summaries = {"A": VariantSummary("A", apt_total=(1, 2))}
    plain = render_markdown("r1", summaries)
    assert "Jueces humanos" not in plain

    scores = [{"blind_id": "B001", "status": "scored", "scores": {"apt": True}}]
    human = build_human_summary(load_sheets(KEY, SHEETS), scores)
    md = render_markdown("r1", summaries, human=human)
    assert md.startswith(plain.rstrip("\n"))
    assert "## Jueces humanos" in md
    assert "| Juez | A | E |" in md
    assert "| ana | 100,0 % (1/1) | 50,0 % (1/2) |" in md
    assert "| luis | 100,0 % (1/1) | 66,7 % (2/3) |" in md
    assert "| ana | luis | 4 | 75,0 % | 0,50 |" in md
    assert f"| ana | {AUTO_JUDGE} | 1 |" in md


def test_render_markdown_human_without_auto_or_rows() -> None:
    summaries = {"A": VariantSummary("A")}
    one = build_human_summary(load_sheets(KEY, SHEETS[:1]))
    md = render_markdown("r1", summaries, human=one)
    assert "Hace falta más de un juez" in md
    assert "Sin etiquetas del juez automático" in md
    empty = render_markdown("r1", summaries, human=build_human_summary([]))
    assert "ninguna fila valorada" in empty
