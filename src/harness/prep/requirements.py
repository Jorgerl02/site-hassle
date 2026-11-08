"""Photo requirements shown to the user, and a plain-Spanish explanation of validation issues."""

from __future__ import annotations

from collections.abc import Sequence

from harness.prep.clean import MIN_BBOX_FRACTION, MIN_LONG_SIDE_PX, format_int, format_pct

PHOTO_REQUIREMENTS: list[str] = [
    "Vista frontal o de tres cuartos de la pieza.",
    "Fondo claro o uniforme, sin otros muebles ni objetos alrededor.",
    "Pieza completa en el encuadre, sin recortes en ningún borde.",
    f"Resolución mínima de {format_int(MIN_LONG_SIDE_PX)} px en el lado mayor.",
    f"La pieza debe ocupar, en su dimensión más larga, al menos un {format_pct(MIN_BBOX_FRACTION)} "
    "del lado mayor de la foto.",
    "Medidas reales de la pieza en centímetros (ancho, alto y fondo).",
]


def explain(issues: Sequence[str]) -> str:
    """Turn ``validate_input`` issues into a short Spanish message for the user."""
    if not issues:
        return "La foto cumple los requisitos."
    lines = ["La foto no se puede usar todavía:"]
    lines += [f"  · {issue}" for issue in issues]
    lines.append("")
    lines.append("Requisitos de la foto:")
    lines += [f"  · {req}" for req in PHOTO_REQUIREMENTS]
    return "\n".join(lines)
