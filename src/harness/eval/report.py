"""Markdown report (Spanish) from ``scores.jsonl``.

Unit of the apt rate: the piece. A piece is apt for a variant if at least one of its
candidates is apt (the pipeline generates N candidates and keeps the best one).
Candidate-attributable failures (``generation_failed``, ``candidate_failed``: model missing,
unreadable or empty) count as non-apt pieces. Only pieces whose candidates were all skipped
for infrastructure reasons (``unscored``: no Blender, no API key, judge error) are left out
of the denominator and listed as "sin puntuar (infraestructura)".
Cost and seconds per piece = sum over that piece's candidates, averaged over pieces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.core.models import CATEGORIES

BASELINE = "A"
WIN_PCT = 60.0  # % aptos per category, strict
WIN_MIN_CATEGORIES = 2
WIN_DELTA_PP = 15.0  # points over the baseline, strict
AXES: tuple[str, ...] = ("parecido", "geometria", "materiales", "escala")
NOT_APT_STATUSES = frozenset({"generation_failed", "candidate_failed"})
DENOMINATOR_NOTE = (
    "Denominador: todas las piezas con algún candidato puntuado o con un fallo atribuible "
    "al candidato (generación fallida, modelo ausente, GLB ilegible o malla vacía), que "
    "cuentan como no aptas; solo se excluyen las piezas sin puntuar por infraestructura "
    "(sin Blender, sin clave de API o error del juez)."
)
NOISE_NOTE = (
    "Diferencias < 15 puntos sobre 30 piezas son ruido: con esta muestra no permiten "
    "afirmar que una variante sea mejor que otra."
)


@dataclass
class VariantSummary:
    variant: str
    apt_by_category: dict[str, tuple[int, int]] = field(default_factory=dict)  # (apt, n)
    apt_total: tuple[int, int] = (0, 0)
    unscored: int = 0
    axis_means: dict[str, float | None] = field(default_factory=dict)
    cost_per_piece: float | None = None
    seconds_per_piece: float | None = None
    delta_pp: float | None = None
    winner: bool = False

    def pct(self, category: str | None = None) -> float | None:
        apt, n = self.apt_total if category is None else self.apt_by_category.get(category, (0, 0))
        return 100.0 * apt / n if n else None

    def categories_over(self, threshold: float = WIN_PCT) -> list[str]:
        return [c for c in CATEGORIES if (p := self.pct(c)) is not None and p > threshold]


def read_scores(path: Path) -> list[dict[str, Any]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(records: list[dict[str, Any]]) -> dict[str, VariantSummary]:
    pieces: dict[tuple[str, str], dict[str, Any]] = {}
    axis_values: dict[str, dict[str, list[float]]] = {}
    for rec in records:
        variant = rec["variant"]
        piece = pieces.setdefault(
            (variant, rec["piece_id"]),
            {
                "category": rec.get("category"),
                "apt": None,
                "cost": 0.0,
                "seconds": 0.0,
                "has_cand": False,
            },
        )
        status = rec.get("status")
        if status in NOT_APT_STATUSES and piece["apt"] is None:
            piece["apt"] = False
        if status == "generation_failed":
            continue
        piece["has_cand"] = True
        piece["cost"] += float(rec.get("cost_usd") or 0.0)
        piece["seconds"] += float(rec.get("seconds") or 0.0)
        scores = rec.get("scores")
        if status == "scored" and scores:
            piece["apt"] = bool(piece["apt"]) or bool(scores["apt"])
            per_axis = axis_values.setdefault(variant, {a: [] for a in AXES})
            for axis in AXES:
                if scores.get(axis) is not None:  # escala is None without geometry
                    per_axis[axis].append(float(scores[axis]))

    summaries: dict[str, VariantSummary] = {}
    for (variant, _pid), piece in sorted(pieces.items()):
        s = summaries.setdefault(variant, VariantSummary(variant))
        if piece["apt"] is None:
            s.unscored += 1
        else:
            apt, n = s.apt_by_category.get(piece["category"], (0, 0))
            s.apt_by_category[piece["category"]] = (apt + int(piece["apt"]), n + 1)
            s.apt_total = (s.apt_total[0] + int(piece["apt"]), s.apt_total[1] + 1)
    for variant, s in summaries.items():
        own = [p for (v, _), p in pieces.items() if v == variant and p["has_cand"]]
        s.cost_per_piece = _mean([p["cost"] for p in own])
        s.seconds_per_piece = _mean([p["seconds"] for p in own])
        values = axis_values.get(variant, {})
        s.axis_means = {a: _mean(values.get(a, [])) for a in AXES}
    decide_winners(summaries)
    return summaries


def decide_winners(summaries: dict[str, VariantSummary]) -> None:
    """Spec rule: > 60 % aptos in >= 2 categories AND > 15 points over the baseline (A)."""
    base = summaries.get(BASELINE)
    base_pct = base.pct() if base else None
    for s in summaries.values():
        own = s.pct()
        s.delta_pp = None if base_pct is None or own is None else own - base_pct
        s.winner = (
            s.variant != BASELINE
            and s.delta_pp is not None
            and s.delta_pp > WIN_DELTA_PP
            and len(s.categories_over()) >= WIN_MIN_CATEGORIES
        )


def _num(value: float | None, decimals: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",") + suffix


def _pct_cell(s: VariantSummary, category: str | None) -> str:
    apt, n = s.apt_total if category is None else s.apt_by_category.get(category, (0, 0))
    return "—" if not n else f"{_num(s.pct(category), 1, ' %')} ({apt}/{n})"


def _delta_cell(s: VariantSummary) -> str:
    if s.variant == BASELINE:
        return "línea base"
    if s.delta_pp is None:
        return "—"
    sign = "+" if s.delta_pp > 0 else ("−" if s.delta_pp < 0 else "±")
    return f"{sign}{_num(abs(s.delta_pp))} pp"


def render_markdown(run_id: str, summaries: dict[str, VariantSummary]) -> str:
    order = sorted(summaries, key=lambda v: (v != BASELINE, v))
    out = [f"# Informe del bake-off · {run_id}", ""]
    out += [
        "Apto = ≥ 4 en los cuatro ejes (parecido, geometría, materiales, escala) sin retoque. "
        "Una pieza es apta si al menos uno de sus candidatos lo es.",
        "",
        DENOMINATOR_NOTE,
        "",
        "## Aptos por variante y categoría",
        "",
        "| Variante | " + " | ".join(CATEGORIES) + " | Total | Δ vs A | Ganadora |",
        "|---|" + "---|" * (len(CATEGORIES) + 3),
    ]
    for v in order:
        s = summaries[v]
        cells = [_pct_cell(s, c) for c in CATEGORIES]
        out.append(
            f"| {v} | "
            + " | ".join(cells)
            + f" | {_pct_cell(s, None)} | {_delta_cell(s)} | {'sí' if s.winner else 'no'} |"
        )
    out += [
        "",
        "## Medias por eje, coste y tiempo",
        "",
        "| Variante | Parecido | Geometría | Materiales | Escala | Coste medio por pieza "
        "| Segundos medios por pieza | Sin puntuar (infraestructura) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for v in order:
        s = summaries[v]
        means = " | ".join(_num(s.axis_means.get(a), 2) for a in AXES)
        out.append(
            f"| {v} | {means} | {_num(s.cost_per_piece, 2, ' USD')} "
            f"| {_num(s.seconds_per_piece, 1, ' s')} | {s.unscored} |"
        )
    winners = [v for v in order if summaries[v].winner]
    out += ["", "## Decisión", ""]
    if BASELINE not in summaries:
        out.append("No hay línea base (variante A) en esta ejecución: no se declara ganadora.")
    elif winners:
        out.append(f"Variantes ganadoras: {', '.join(winners)}.")
    else:
        out.append("Ninguna variante cumple la regla de la spec.")
    out += [
        "",
        f"Regla: > {_num(WIN_PCT, 0)} % de aptos en al menos {WIN_MIN_CATEGORIES} categorías "
        f"y > {_num(WIN_DELTA_PP, 0)} puntos sobre la línea base (A) en el total.",
        "",
        f"**Nota:** {NOISE_NOTE}",
        "",
    ]
    return "\n".join(out)
