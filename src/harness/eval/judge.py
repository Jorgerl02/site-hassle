"""VLM judge with the fixed rubric of the spec (``Paso previo``, point 3).

The VLM scores ``parecido``, ``geometria`` and ``materiales``; ``escala`` is computed from
the measured bounding-box error and never asked to the model. The judge only ever sees a
``blind_id``: no variant name reaches the prompt, the image list or any log.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from harness.core.config import resolve_scale_tolerance
from harness.core.models import GeometryMetrics, Scores
from harness.eval.render import VIEWS

APT_MIN = 4
VLM_AXES: tuple[str, ...] = ("parecido", "geometria", "materiales")
# ``escala`` = 3 below this multiple of the tolerance. 10/3 keeps the historical thresholds
# (3 % → 10 %) at the default tolerance, so earlier scores stay comparable.
ESCALA_MID_FACTOR = 10 / 3

RUBRIC_PROMPT = """\
Eres juez de calidad de modelos 3D de muebles generados a partir de fotos de catálogo.
Evalúas el candidato {blind_id}. No sabes ni debes intentar adivinar cómo se generó.

Imágenes recibidas, en este orden:
- {n_photos} foto(s) originales del producto (la referencia).
- {n_renders} renders del modelo 3D, en este orden de vista: {views}.

Los renders usan iluminación de estudio sin reflejos sobre fondo blanco: juzga brillo,
metal y vidrio por color, textura y forma, no por reflejos. Puntúa el modelo tal cual,
sin imaginar retoques.

Puntúa de 1 a 5 cada eje según estas definiciones:

parecido (parecido con la foto)
5 = es el mismo producto: forma, proporciones y detalles característicos coinciden.
4 = mismo producto con diferencias menores que un cliente no notaría a primera vista.
3 = mismo tipo y estilo, pero con diferencias visibles de forma o proporciones.
2 = mueble del mismo tipo, pero claramente otro modelo.
1 = no se parece o no es identificable.

geometria (malla, patas, trasera)
5 = sin agujeros, patas completas y separadas, trasera y partes ocultas creíbles, nada inventado.
4 = solo irregularidades menores visibles de cerca; sin agujeros ni patas fundidas.
3 = un defecto claro: pata fundida, deformada o ausente, agujero, trasera poco creíble
    o pieza inventada.
2 = varios defectos graves.
1 = geometría rota o irreconocible.

materiales (color, textura, acabado)
5 = color, textura y acabado (mate, brillo, tela, metal, vidrio) fieles a la foto.
4 = fieles con diferencias leves de tono o acabado.
3 = material reconocible, pero tono o acabado claramente distinto, o textura borrosa o manchada.
2 = material equivocado (p. ej. madera en lugar de metal) o textura con artefactos graves.
1 = sin textura o completamente erróneo.

No puntúes la escala: se mide aparte.
En "comentario" explica en una o dos frases, en español, el defecto principal.
"""

SCHEMA_HINT = (
    '{"parecido": int (1-5), "geometria": int (1-5), "materiales": int (1-5), "comentario": str}'
)


class JSONAsker(Protocol):
    def ask_json(self, prompt: str, images: list[Path], schema_hint: str) -> dict[str, Any]: ...


class JudgeError(ValueError):
    """The VLM answer does not follow the rubric schema."""


def escala_thresholds(tolerance: float | None = None) -> tuple[float, float]:
    """``(tol, mid)``: 5 below ``tol``, 3 below ``mid`` (= tol · 10/3), else 1."""
    tol = resolve_scale_tolerance(tolerance)
    return tol, round(tol * ESCALA_MID_FACTOR, 6)


def escala_from_error(max_error: float, *, tolerance: float | None = None) -> int:
    """5 if < tolerance, 3 if < tolerance · 10/3, else 1 (3 % → 3 %/10 % by default).

    ``tolerance`` None → the configured ``Settings.scale_tolerance``."""
    tol, mid = escala_thresholds(tolerance)
    if max_error < tol:
        return 5
    if max_error < mid:
        return 3
    return 1


def build_prompt(blind_id: str, n_photos: int, n_renders: int) -> str:
    return RUBRIC_PROMPT.format(
        blind_id=blind_id, n_photos=n_photos, n_renders=n_renders, views=", ".join(VIEWS)
    )


def _axis(answer: dict[str, Any], key: str) -> int:
    value = answer.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or value != int(value):
        raise JudgeError(f"'{key}' debe ser un entero 1–5; recibido {value!r}")
    if not 1 <= int(value) <= 5:
        raise JudgeError(f"'{key}' fuera de rango 1–5: {value!r}")
    return int(value)


def visual_axes(answer: dict[str, Any]) -> dict[str, Any]:
    """Validated ``parecido``/``geometria``/``materiales`` plus ``comentario``."""
    axes: dict[str, Any] = {key: _axis(answer, key) for key in VLM_AXES}
    comentario = answer.get("comentario", "")
    axes["comentario"] = str(comentario) if comentario is not None else ""
    return axes


def scores_from_answer(answer: dict[str, Any], escala: int) -> Scores:
    visual = visual_axes(answer)
    return Scores(
        **visual,
        escala=escala,
        apt=all(visual[k] >= APT_MIN for k in VLM_AXES) and escala >= APT_MIN,
    )


def judge_candidate(
    vlm: JSONAsker,
    *,
    blind_id: str,
    photos: list[Path],
    renders: list[Path],
    geometry: GeometryMetrics | None,
    tolerance: float | None = None,
) -> dict[str, Any]:
    """Ask the VLM for the three visual axes and combine them with the computed ``escala``.

    Returns ``Scores.model_dump()``. Without geometry the visual axes are still recorded,
    with ``escala=None`` and ``apt=False`` (``Scores`` cannot hold a missing axis).
    ``tolerance`` None → the configured ``Settings.scale_tolerance``.
    """
    prompt = build_prompt(blind_id, len(photos), len(renders))
    answer = vlm.ask_json(prompt, [*photos, *renders], SCHEMA_HINT)
    if geometry is None:
        return {**visual_axes(answer), "escala": None, "apt": False}
    escala = escala_from_error(geometry.max_error, tolerance=tolerance)
    return scores_from_answer(answer, escala).model_dump()
