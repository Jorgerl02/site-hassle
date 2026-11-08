"""Refinement rules: what is wrong with a candidate (``diagnose``) and what to do (``plan``).

Pure functions over the candidate ``meta.json`` (its ``post`` block, as written by the CLI
post step) and, optionally, its row of ``eval/scores.jsonl``. No I/O here.

Issues:
- ``scale``: the uniform-scale residual is between the tolerance (3 %) and the fit guard
  (10 %) and the fit-to-box was not applied → fixable for free with ``fit_box``.
- ``geometry``: residual above the guard, fit rejected by the guard, or a mesh shattered into
  more than ``MAX_COMPONENTS`` connected components → only a new generation helps.
  With no ``post`` block (or a failed one) and no evaluation row it reports ``geometry``
  "sin postprocesado", planned as a free re-post (``fit_box``).
- ``material``: the judge scored ``materiales`` ≤ ``MAX_BAD_MATERIAL_SCORE`` → retexture.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

from harness.core.models import SCALE_TOLERANCE
from harness.post.bpy_post import DEFAULT_FIT_GUARD

IssueKind = Literal["scale", "geometry", "material"]
ActionKind = Literal["fit_box", "regenerate", "retexture"]

MAX_COMPONENTS = 5_000
MAX_BAD_MATERIAL_SCORE = 3
MAX_EXTRA_CANDIDATES = 2  # regenerate asks the variant for at most two more candidates
PAID_ACTIONS: frozenset[str] = frozenset({"regenerate", "retexture"})
# Fixed application order: free scale fix first, then geometry, then material.
ACTION_ORDER: tuple[str, ...] = ("fit_box", "regenerate", "retexture")
DEFAULT_ACTION: dict[str, ActionKind] = {
    "scale": "fit_box",
    "geometry": "regenerate",
    "material": "retexture",
}
NO_POST_DETAIL = "sin postprocesado"


@dataclass(frozen=True)
class Issue:
    kind: IssueKind
    detail: str  # Spanish, shown in refine.json / reports
    value: float | None = None
    # Overrides the default action for ``kind`` (e.g. a missing post → re-post, not regenerate).
    action: ActionKind | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    reason: str  # Spanish

    @property
    def paid(self) -> bool:
        return self.kind in PAID_ACTIONS

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "reason": self.reason, "paid": self.paid}


def _pct(value: float) -> str:
    return f"{value * 100:.1f} %".replace(".", ",")


def _max_abs(errors: Mapping[str, Any] | None) -> float | None:
    if not errors:
        return None
    values = [abs(float(v)) for v in errors.values() if v is not None]
    return max(values) if values else None


def _scale_error(post: Mapping[str, Any], row: Mapping[str, Any] | None) -> float | None:
    """Uniform-scale residual: pre-fit errors from post, else the evaluation's max_error."""
    if post.get("ok"):
        err = _max_abs(post.get("errors_before_fit"))
        if err is None:
            err = _max_abs(post.get("errors"))
        if err is not None:
            return err
    geometry = (row or {}).get("geometry") or {}
    value = _as_number(geometry.get("max_error"))
    return abs(value) if value is not None else None


def _as_number(value: Any) -> float | None:
    """``float(value)`` or ``None`` for missing / non-numeric values (treated as no data)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rejected_by_guard(post: Mapping[str, Any]) -> bool:
    if post.get("fit_skip_reason"):
        return True
    return bool(post.get("fit_box_requested")) and not post.get("fit_box_applied")


def diagnose(
    candidate_meta: Mapping[str, Any],
    scores: Mapping[str, Any] | None = None,
    *,
    tolerance: float = SCALE_TOLERANCE,
    guard: float = DEFAULT_FIT_GUARD,
) -> list[Issue]:
    """Issues of one candidate, in ``scale``/``geometry``/``material`` order.

    ``scores`` is the candidate's row of ``scores.jsonl`` (``scores`` and ``geometry`` keys)
    or ``None`` when it was not evaluated (no material issue can be detected then).
    """
    post = candidate_meta.get("post") or {}
    if not isinstance(post, Mapping):
        post = {}
    issues: list[Issue] = []
    if not post.get("ok") and scores is None:
        # Nothing measured (e.g. a re-post failed after a regeneration): not a clean result.
        # The fix is a free re-post (fit_box), never a paid regeneration.
        return [Issue("geometry", NO_POST_DETAIL, None, action="fit_box")]
    err = _scale_error(post, scores)
    fit_applied = bool(post.get("fit_box_applied"))
    rejected = _rejected_by_guard(post)

    # A guard rejection means fit_box would be rejected again: that is a geometry issue.
    if err is not None and tolerance <= err <= guard and not fit_applied and not rejected:
        issues.append(
            Issue(
                "scale",
                f"error de escala {_pct(err)} entre la tolerancia ({_pct(tolerance)}) "
                f"y la guarda ({_pct(guard)}), sin ajuste a la caja",
                err,
            )
        )

    geometry_reasons: list[str] = []
    if err is not None and err > guard:
        geometry_reasons.append(f"error {_pct(err)} por encima de la guarda ({_pct(guard)})")
    elif rejected:
        why = post.get("fit_skip_reason") or "sin motivo"
        geometry_reasons.append(f"ajuste a la caja rechazado por la guarda ({why})")
    components = _as_number(((scores or {}).get("geometry") or {}).get("n_components"))
    if components is not None and components > MAX_COMPONENTS:
        geometry_reasons.append(f"{int(components)} componentes (máximo {MAX_COMPONENTS})")
    if geometry_reasons:
        issues.append(Issue("geometry", "; ".join(geometry_reasons), err))

    judged = (scores or {}).get("scores") or {}
    if not isinstance(judged, Mapping):
        judged = {}
    materiales = _as_number(judged.get("materiales"))
    if materiales is not None and materiales <= MAX_BAD_MATERIAL_SCORE:
        issues.append(
            Issue(
                "material",
                f"materiales {int(materiales)}/5 (≤ {MAX_BAD_MATERIAL_SCORE})",
                materiales,
            )
        )
    return issues


def plan(
    issues: list[Issue],
    *,
    regenerations_done: int = 0,
    max_regenerations: int = MAX_EXTRA_CANDIDATES,
    can_retexture: bool = False,
    paid_budget: int | None = None,
) -> list[Action]:
    """Actions for ``issues`` in application order (``fit_box``, ``regenerate``, ``retexture``).

    ``regenerate`` is dropped once ``regenerations_done`` reaches ``max_regenerations``;
    ``retexture`` needs a provider (``can_retexture``); paid actions beyond ``paid_budget``
    (``None`` = unlimited) are dropped.
    """
    by_action: dict[str, Issue] = {}
    for issue in issues:
        by_action.setdefault(issue.action or DEFAULT_ACTION[issue.kind], issue)
    actions: list[Action] = []
    paid = 0
    for kind in ACTION_ORDER:
        issue = by_action.get(kind)
        if issue is None:
            continue
        if kind == "regenerate" and regenerations_done >= max_regenerations:
            continue
        if kind == "retexture" and not can_retexture:
            continue
        if kind in PAID_ACTIONS:
            if paid_budget is not None and paid >= paid_budget:
                continue
            paid += 1
        actions.append(Action(kind, issue.detail))  # type: ignore[arg-type]
    return actions
