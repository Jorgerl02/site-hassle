"""Markdown report (Spanish) from ``scores.jsonl``.

Unit of the apt rate: the piece. A piece is apt for a variant if at least one of its
candidates is apt (the pipeline generates N candidates and keeps the best one).
Candidate-attributable failures (``generation_failed``: the provider task failed or no GLB
came back, run-meta errors with ``kind="candidate"``; ``candidate_failed``: model missing,
unreadable or empty, or a candidate ``meta.json`` with ``error`` and ``error_kind`` other
than ``"infra"``) count as non-apt pieces. A candidate ``meta.json`` with
``error_kind="infra"`` is ``unscored``. Pieces whose candidates were all skipped for
infrastructure reasons (``unscored``: no Blender, no API key, network error — run-meta
errors with ``kind="infra"`` —, judge error) are left out of the denominator and listed as
"sin puntuar (infraestructura)". Pieces where the variant does not apply
(``not_applicable``: E on an organic piece) are left out of that variant's denominator and
reported as "N/M piezas aplicables".
Cost and seconds per piece = sum over that piece's candidates, averaged over pieces; the cost
includes refinement spend (``refine_cost_usd``: the extra generations billed by a regeneration
and retextures), also shown apart in the «Refinado» column with the number of refined
candidates (``refined``).
"Escala antes del ajuste" = mean over measured candidates of max |error| after the uniform
scale only (``errors_before_fit``; the measured error when no fit-to-box ran), so a fitted
model — whose "Escala" is computed on the fitted geometry — never hides its pre-fit error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness.core.models import CATEGORIES

if TYPE_CHECKING:
    from harness.eval.sheets import HumanSummary

BASELINE = "A"
WIN_PCT = 60.0  # % aptos per category, strict
WIN_MIN_CATEGORIES = 2
WIN_DELTA_PP = 15.0  # points over the baseline, strict
AXES: tuple[str, ...] = ("parecido", "geometria", "materiales", "escala")
NOT_APT_STATUSES = frozenset({"generation_failed", "candidate_failed"})
DENOMINATOR_NOTE = (
    "Denominador: todas las piezas con algún candidato puntuado o con un fallo atribuible "
    "al candidato (tarea del proveedor fallida, sin GLB, modelo ausente, GLB ilegible o "
    "malla vacía), que cuentan como no aptas; se excluyen las piezas sin puntuar por "
    "infraestructura (sin Blender, sin clave de API, error de red o del juez) y, para cada "
    "variante, las piezas en las que no es aplicable (E solo se ejecuta en piezas "
    "rectilíneas)."
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
    not_applicable: int = 0
    n_pieces: int = 0
    axis_means: dict[str, float | None] = field(default_factory=dict)
    cost_per_piece: float | None = None
    seconds_per_piece: float | None = None
    delta_pp: float | None = None
    winner: bool = False
    watertight_pct: float | None = None  # over candidates measured by trimesh
    components_mean: float | None = None
    generation_cost: float = 0.0  # includes the router share of F
    router_cost: float = 0.0
    judge_cost: float = 0.0
    refine_cost: float = 0.0  # refinement spend (regeneration extras, retextures)
    refined_candidates: int = 0
    pre_fit_error_mean: float | None = None  # mean max |error| before fit-to-box
    fit_applied: int = 0  # measured candidates with fit-to-box applied
    fit_measured: int = 0  # measured candidates (denominator of fit_applied)

    @property
    def applicable(self) -> int:
        return self.n_pieces - self.not_applicable

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


def pre_fit_max_error(rec: dict[str, Any]) -> float | None:
    """max |error| after the uniform scale only (before any fit-to-box) of a record."""
    before = rec.get("errors_before_fit")
    if isinstance(before, dict) and before:
        return max(abs(float(v)) for v in before.values())
    geometry = rec.get("geometry") or {}
    value = geometry.get("max_error")
    return float(value) if value is not None else None


def summarize(records: list[dict[str, Any]]) -> dict[str, VariantSummary]:
    pieces: dict[tuple[str, str], dict[str, Any]] = {}
    pre_fit: dict[str, list[float]] = {}
    fit_counts: dict[str, list[int]] = {}  # variant → [applied, measured]
    axis_values: dict[str, dict[str, list[float]]] = {}
    topology: dict[str, list[tuple[bool, int]]] = {}
    costs: dict[str, dict[str, float]] = {}
    for rec in records:
        variant = rec["variant"]
        piece = pieces.setdefault(
            (variant, rec["piece_id"]),
            {
                "category": rec.get("category"),
                "apt": None,
                "na": False,
                "cost": 0.0,
                "seconds": 0.0,
                "has_cand": False,
            },
        )
        status = rec.get("status")
        c = costs.setdefault(
            variant, {"generation": 0.0, "router": 0.0, "judge": 0.0, "refine": 0.0, "refined": 0}
        )
        refine_cost = float(rec.get("refine_cost_usd") or 0.0)
        c["generation"] += float(rec.get("cost_usd") or 0.0)
        c["router"] += float(rec.get("router_cost_usd") or 0.0)
        c["judge"] += float(rec.get("judge_cost_usd") or 0.0)
        c["refine"] += refine_cost
        c["refined"] += int(bool(rec.get("refined")))
        if status == "not_applicable":
            piece["na"] = True
        if status in NOT_APT_STATUSES and piece["apt"] is None:
            piece["apt"] = False
        if status == "generation_failed" or rec.get("from_run_meta"):
            continue
        if rec.get("generation_error"):
            # Failed candidate: its spend (e.g. C's Gemini share) counts for the piece, but it
            # does not make the piece "measured" for the per-piece averages on its own.
            piece["cost"] += float(rec.get("cost_usd") or 0.0) + refine_cost
            piece["seconds"] += float(rec.get("seconds") or 0.0)
            continue
        geometry = rec.get("geometry")
        if geometry and geometry.get("source") == "trimesh":
            topology.setdefault(variant, []).append(
                (bool(geometry.get("watertight")), int(geometry.get("n_components") or 0))
            )
        if geometry:
            counts = fit_counts.setdefault(variant, [0, 0])
            counts[0] += int(bool(rec.get("fit_box_applied")))
            counts[1] += 1
            if (value := pre_fit_max_error(rec)) is not None:
                pre_fit.setdefault(variant, []).append(value)
        piece["has_cand"] = True
        piece["cost"] += float(rec.get("cost_usd") or 0.0) + refine_cost
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
        s.n_pieces += 1
        if piece["apt"] is None and piece["na"]:
            s.not_applicable += 1
        elif piece["apt"] is None:
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
        topo = topology.get(variant, [])
        s.watertight_pct = 100.0 * _mean([float(w) for w, _ in topo]) if topo else None
        s.components_mean = _mean([float(n) for _, n in topo])
        c = costs.get(variant, {})
        s.generation_cost = c.get("generation", 0.0)
        s.router_cost = c.get("router", 0.0)
        s.judge_cost = c.get("judge", 0.0)
        s.refine_cost = c.get("refine", 0.0)
        s.refined_candidates = int(c.get("refined", 0))
        s.pre_fit_error_mean = _mean(pre_fit.get(variant, []))
        s.fit_applied, s.fit_measured = fit_counts.get(variant, [0, 0])
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


def _seconds_cell(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    return f"{_num(seconds, 1, ' s')} ({_num(seconds / 60, 1, ' min')})"


def _pct_cell(s: VariantSummary, category: str | None) -> str:
    apt, n = s.apt_total if category is None else s.apt_by_category.get(category, (0, 0))
    return "—" if not n else f"{_num(s.pct(category), 1, ' %')} ({apt}/{n})"


def _refined_cell(s: VariantSummary) -> str:
    n = s.refined_candidates
    noun = "candidato" if n == 1 else "candidatos"
    return f"{n} {noun} de refinado · {_num(s.refine_cost, 2, ' USD')}"


def _delta_cell(s: VariantSummary) -> str:
    if s.variant == BASELINE:
        return "línea base"
    if s.delta_pp is None:
        return "—"
    sign = "+" if s.delta_pp > 0 else ("−" if s.delta_pp < 0 else "±")
    return f"{sign}{_num(abs(s.delta_pp))} pp"


def format_tolerance(tolerance: float) -> str:
    """Spanish percentage: 0.03 → "3 %", 0.035 → "3,5 %"."""
    return f"{round(tolerance * 100, 2):g} %".replace(".", ",")


def _tolerance_line(tolerances: list[float] | None) -> str | None:
    if tolerances is None:
        return None
    if not tolerances:
        return "Tolerancia de escala: no registrada (scores.jsonl anterior a la opción)."
    if len(tolerances) == 1:
        return f"Tolerancia de escala: {format_tolerance(tolerances[0])}."
    mixed = ", ".join(format_tolerance(t) for t in tolerances)
    return f"Tolerancia de escala: mezcla de {mixed}; vuelve a ejecutar `bakeoff eval`."


def render_markdown(
    run_id: str,
    summaries: dict[str, VariantSummary],
    human: HumanSummary | None = None,
    scale_tolerances: list[float] | None = None,
) -> str:
    """``scale_tolerances``: distinct tolerances found in ``scores.jsonl`` (None → no line)."""
    order = sorted(summaries, key=lambda v: (v != BASELINE, v))
    out = [f"# Informe del bake-off · {run_id}", ""]
    tolerance_line = _tolerance_line(scale_tolerances)
    if tolerance_line:
        out += [tolerance_line, ""]
    out += [
        "Apto = ≥ 4 en los cuatro ejes (parecido, geometría, materiales, escala) sin retoque. "
        "Una pieza es apta si al menos uno de sus candidatos lo es.",
        "",
        DENOMINATOR_NOTE,
        "",
    ]
    partial = [summaries[v] for v in order if summaries[v].not_applicable]
    for s in partial:
        out.append(
            f"- {s.variant}: {s.applicable}/{s.n_pieces} piezas aplicables; sus tasas se "
            "calculan sobre ese subconjunto."
        )
    if partial:
        out.append("")
    out += [
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
        "| Variante | Parecido | Geometría | Materiales | Escala | Escala antes del ajuste "
        "| Coste medio por pieza | Tiempo medio por pieza | % mallas cerradas "
        "| Media de componentes | Sin puntuar (infraestructura) | Refinado |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for v in order:
        s = summaries[v]
        means = " | ".join(_num(s.axis_means.get(a), 2) for a in AXES)
        pre_fit = None if s.pre_fit_error_mean is None else 100.0 * s.pre_fit_error_mean
        out.append(
            f"| {v} | {means} | {_num(pre_fit, 1, ' %')} | {_num(s.cost_per_piece, 2, ' USD')} "
            f"| {_seconds_cell(s.seconds_per_piece)} | {_num(s.watertight_pct, 0, ' %')} "
            f"| {_num(s.components_mean, 1)} | {s.unscored} | {_refined_cell(s)} |"
        )
    generation = sum(s.generation_cost for s in summaries.values())
    router = sum(s.router_cost for s in summaries.values())
    judge = sum(s.judge_cost for s in summaries.values())
    refine = sum(s.refine_cost for s in summaries.values())
    fit_applied = sum(s.fit_applied for s in summaries.values())
    fit_measured = sum(s.fit_measured for s in summaries.values())
    out += [
        "",
        f"**Coste total:** {_num(generation + refine + judge, 2, ' USD')} = generación "
        f"{_num(generation - router, 2, ' USD')} + enrutado VLM (F) {_num(router, 2, ' USD')} "
        f"+ refinado {_num(refine, 2, ' USD')} + juez VLM {_num(judge, 2, ' USD')}.",
        "",
        "«Refinado»: candidatos regenerados o refinados con `bakeoff refine` y su gasto "
        "extra (generaciones adicionales de la regeneración y retexturizados), incluido en "
        "el coste medio por pieza.",
        "",
        "Mallas cerradas y componentes: solo candidatos medidos con trimesh (GLB legible).",
        "",
        f"**Ajuste a la caja del catálogo:** aplicado en {fit_applied} de {fit_measured} "
        "candidatos medidos. «Escala» se puntúa sobre el modelo final (ajustado, si procede); "
        "«Escala antes del ajuste» es la media del error máximo |relativo| tras la escala "
        "uniforme, antes de cualquier ajuste por eje.",
    ]
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
    if human is not None:
        out += _human_section(human)
    return "\n".join(out)


def _human_section(human: HumanSummary) -> list[str]:
    """«Jueces humanos»: apt rate per judge and variant, and agreement between judges."""
    out = ["## Jueces humanos", ""]
    if not human.judges:
        return [*out, "Las hojas de los jueces no tienen ninguna fila valorada.", ""]
    variants = sorted(
        {v for per_judge in human.by_variant.values() for v in per_judge},
        key=lambda v: (v != BASELINE, v),
    )
    out += [
        "Unidad: la pieza; una pieza es apta para un juez si marcó «apto» en al menos uno "
        "de sus candidatos. Solo cuentan las filas con la columna «apto» rellena.",
        "",
        "| Juez | " + " | ".join(variants) + " |",
        "|---|" + "---|" * len(variants),
    ]
    for judge in human.judges:
        per_variant = human.by_variant.get(judge, {})
        cells = []
        for v in variants:
            apt, n = per_variant.get(v, (0, 0))
            cells.append("—" if not n else f"{_num(100.0 * apt / n, 1, ' %')} ({apt}/{n})")
        out.append(f"| {judge} | " + " | ".join(cells) + " |")
    out += [
        "",
        "### Acuerdo entre jueces",
        "",
        "Sobre los candidatos valorados por ambos jueces: porcentaje de etiquetas «apto» "
        "iguales y kappa de Cohen (1 = acuerdo total, ≈ 0 = el esperable por azar; «—» si "
        "no hay candidatos en común o ambos jueces ponen siempre la misma etiqueta).",
        "",
    ]
    if not human.agreement.pairs:
        out.append("Hace falta más de un juez para medir el acuerdo.")
    else:
        out += ["| Juez | Juez | Candidatos en común | Acuerdo | Kappa |", "|---|---|---|---|---|"]
        for p in human.agreement.pairs:
            out.append(
                f"| {p.judge_a} | {p.judge_b} | {p.n} | {_num(p.agree_pct, 1, ' %')} "
                f"| {_num(p.kappa, 2)} |"
            )
    if not human.has_auto:
        out += ["", "Sin etiquetas del juez automático: no se mide el acuerdo con él."]
    out.append("")
    return out
