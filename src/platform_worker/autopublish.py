"""Automatic publishing: decide whether a finished piece goes straight to the customer
(``ready``) or to manual review (``review``).

Owner ruling (2026-11-09): publish automatically, and keep manual review only for the pieces
an AI model cannot approve with guarantees.

1. Hard requirements: the selected candidate is deliverable (preview + GLB + USDZ, no
   error) and its ``max_error`` is under the scale tolerance (``resolve_scale_tolerance``).
2. Conflicts between the customer's answers and a confident photo, ``check_dimensions``
   warnings and any other warning (parametric spec, delivery, material) → manual.
3. With a vision judge (``ANTHROPIC_API_KEY``): ``judge_candidate`` with the customer photos
   and the renders; auto only when ``parecido``, ``geometria`` and ``materiales`` are all
   ≥ 4 and ``apt``. Any judge error → manual.
4. Without a judge: auto only on route E (exact scale by construction) when every answer
   that decides the shape comes from the customer or from the photo reading with
   confidence ≥ ``RULES_MIN_CONFIDENCE``.
5. ``AUTO_PUBLISH`` (default on); off → always manual.

The result is stored in ``piece_models.meta.auto_review`` (reasons in Spanish: the admin
reads them).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from harness.eval.judge import VLM_AXES

RULES_MIN_CONFIDENCE = 0.8
JUDGE_MIN_SCORE = 4
DECISION_AUTO = "auto"
DECISION_MANUAL = "manual"
GATE_VLM = "vlm"
GATE_RULES = "rules"
# Values of ``AUTO_PUBLISH`` that turn it off (anything else, or unset, keeps it on).
_OFF = frozenset({"0", "false", "no", "off"})

Judge = Callable[[], dict[str, Any]]


@dataclass
class AutoReview:
    decision: str
    gate: str
    reasons: list[str] = field(default_factory=list)
    scores: dict[str, Any] | None = None

    @property
    def auto(self) -> bool:
        return self.decision == DECISION_AUTO

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"decision": self.decision, "gate": self.gate}
        if self.scores is not None:
            out["scores"] = self.scores
        out["reasons"] = list(self.reasons)
        return out


def auto_publish_enabled(settings: Mapping[str, str | None]) -> bool:
    """``AUTO_PUBLISH`` flag: on unless set to 0/false/no/off."""
    raw = settings.get("AUTO_PUBLISH")
    return raw is None or raw.strip().lower() not in _OFF


def _pct(value: float) -> str:
    return f"{value * 100:.1f}".replace(".", ",") + " %"


def shape_sources(routing: Any, interpretation: Any) -> list[tuple[str, bool, str]]:
    """``(field, trusted, why)`` for each answer that decides the parametric shape: the
    rectilinear decision and whatever picked the parametric kind (support, central
    pedestal, or the kind for headboards/panels). Trusted = the customer's explicit answer,
    or the photo reading with confidence ≥ ``RULES_MIN_CONFIDENCE``."""
    effective = routing.effective
    source = effective.get("source") or {}
    out: list[tuple[str, bool, str]] = []

    def check(name: str, src: str | None, confidence: float) -> None:
        if src == "customer":
            out.append((name, True, f"{name}: respuesta del cliente"))
        elif src == "inferred":
            ok = confidence >= RULES_MIN_CONFIDENCE
            out.append((name, ok, f"{name}: foto con confianza {_pct(confidence)}"))
        else:
            out.append((name, False, f"{name}: sin respuesta ni lectura fiable de la foto"))

    check("recta", source.get("rectilinear"), interpretation.confidence)
    if routing.kind is None:
        out.append(("tipo", False, "tipo: lo deduce la clasificación de E, sin confirmar"))
    elif routing.kind == "pedestal":
        if routing.photo_overrides_support:
            out.append(("apoyo", False, "apoyo: contradice la respuesta del cliente"))
        else:
            check("apoyo (pie central)", "inferred", interpretation.support_confidence)
    elif source.get("support") in ("customer", "inferred"):
        check("apoyo", source.get("support"), interpretation.support_confidence)
    else:  # headboard/panel → box from the kind
        check("tipo", source.get("kind"), interpretation.confidence)
    return out


def decide(
    *,
    enabled: bool,
    route: str,
    deliverable: bool,
    max_error: float | None,
    tolerance: float,
    routing: Any,
    interpretation: Any,
    conflicts: list[dict[str, Any]],
    warnings: list[str],
    judge: Judge | None,
) -> AutoReview:
    """The decision for the selected candidate (see the module docstring).

    ``warnings`` are every warning of the piece (dimensions, spec, delivery, material);
    ``judge`` runs the VLM judge and returns ``Scores.model_dump()`` (None: no judge)."""
    gate = GATE_VLM if judge is not None else GATE_RULES
    if not enabled:
        return AutoReview(DECISION_MANUAL, gate, ["Publicación automática desactivada"])
    reasons: list[str] = []
    if not deliverable:
        reasons.append("El candidato elegido no tiene vista previa, GLB y USDZ")
    if max_error is None or not max_error < tolerance:
        shown = "sin medir" if max_error is None else _pct(max_error)
        reasons.append(f"Error de escala {shown} (tolerancia {_pct(tolerance)})")
    for conflict in conflicts:
        reasons.append(
            f"Conflicto en «{conflict.get('field')}»: cliente «{conflict.get('customer')}», "
            f"foto «{conflict.get('inferred')}» ({_pct(float(conflict.get('confidence') or 0))})"
        )
    reasons += [f"Aviso: {w}" for w in warnings]
    if reasons:
        return AutoReview(DECISION_MANUAL, gate, reasons)

    if judge is not None:
        try:
            scores = judge()
        except Exception as exc:  # any judge failure means "cannot guarantee"
            return AutoReview(
                DECISION_MANUAL, gate, [f"El juez visual falló: {type(exc).__name__}: {exc}"]
            )
        low = [axis for axis in VLM_AXES if int(scores.get(axis) or 0) < JUDGE_MIN_SCORE]
        summary = ", ".join(f"{axis} {scores.get(axis)}" for axis in VLM_AXES)
        if low or not scores.get("apt"):
            reasons = [f"Juez visual: {summary} (hace falta ≥ {JUDGE_MIN_SCORE} en todo)"]
            if scores.get("comentario"):
                reasons.append(f"Comentario del juez: {scores['comentario']}")
            return AutoReview(DECISION_MANUAL, gate, reasons, scores)
        return AutoReview(DECISION_AUTO, gate, [f"Juez visual: {summary}"], scores)

    if route != "E":
        return AutoReview(
            DECISION_MANUAL,
            gate,
            ["Pieza orgánica sin juez visual (ANTHROPIC_API_KEY): revisión manual"],
        )
    sources = shape_sources(routing, interpretation)
    untrusted = [why for _, ok, why in sources if not ok]
    if untrusted:
        return AutoReview(DECISION_MANUAL, gate, ["Forma sin confirmar: " + "; ".join(untrusted)])
    return AutoReview(
        DECISION_AUTO,
        gate,
        [
            "Ruta E con escala exacta (error " + _pct(max_error or 0.0) + ")",
            *[why for _, _, why in sources],
        ],
    )
