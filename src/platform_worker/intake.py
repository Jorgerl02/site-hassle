"""Input checks of a queued piece (excluded categories and photo requirements) and the
mapping from a ``pieces`` row to the harness ``Piece``.

Excluded categories come from ``docs/promesa.md``: metal/chrome, glass and thin legs; the
form's ``lampara`` kind is excluded outright. Photo checks reuse
``harness.prep.clean.validate_input`` and ``harness.prep.requirements.explain``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from harness.core.models import Piece
from harness.prep.clean import validate_input
from harness.prep.requirements import PHOTO_REQUIREMENTS

MAX_PHOTO_BYTES = 20 * 1024 * 1024  # same 20 MB limit as the upload form

# Form kinds (enum ``piece_kind``) that are boxes for the parametric route E.
RECTILINEAR_KINDS: frozenset[str] = frozenset(
    {"cabecero", "panel", "mesita", "aparador", "estanteria", "mesa"}
)
ORGANIC_KINDS: frozenset[str] = frozenset({"sofa", "sillon", "silla", "jarron", "otro"})
EXCLUDED_KINDS: dict[str, str] = {
    "lampara": (
        "No trabajamos lámparas: suelen ser de metal, cromo o vidrio y tener tubos finos, "
        "y los generadores pierden el reflejo y deforman los arcos."
    ),
}
# Accent-free, lowercase keyword → reason (text of docs/promesa.md, «Categorías excluidas»).
_REFLECTION = "los generadores pierden el reflejo y deforman los arcos."
_TRANSPARENCY = "el reflejo y la transparencia no se reproducen bien."
# Word-start stems (accent-free), so «cromadas», «metálica» or «inoxidable» are caught.
EXCLUDED_STEMS: dict[str, str] = {
    "metal": f"No trabajamos piezas de metal: {_REFLECTION}",
    "acero": f"No trabajamos piezas de metal: {_REFLECTION}",
    "inox": f"No trabajamos piezas de metal: {_REFLECTION}",
    "crom": f"No trabajamos piezas cromadas: {_REFLECTION}",
    "vidri": f"No trabajamos piezas de vidrio: {_TRANSPARENCY}",
    "cristal": f"No trabajamos piezas de cristal: {_TRANSPARENCY}",
    "acristal": f"No trabajamos piezas de cristal: {_TRANSPARENCY}",
}

# Harness category (only used for bookkeeping in the harness: rubric reports, file names).
KIND_CATEGORY: dict[str, str] = {
    "sofa": "tapizado",
    "sillon": "tapizado",
    "silla": "tapizado",
    "cabecero": "tapizado",
}
# Words fed to the parametric classifier (``parametric_spec.classify_with_params``) so the
# form's kind picks the right box layout. Cabecero and panel are forced to a plain box.
KIND_TEXT: dict[str, str] = {
    "mesa": "mesa",
    "mesita": "mesita",
    "aparador": "aparador",
    "estanteria": "estantería",
}
BOX_KINDS: frozenset[str] = frozenset({"cabecero", "panel"})

Validator = Callable[[Path], list[str]]


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def excluded_reasons(piece_row: dict[str, Any]) -> list[str]:
    """Reasons why the piece belongs to an excluded category (empty when accepted)."""
    reasons: list[str] = []
    kind = piece_row.get("kind") or ""
    if kind in EXCLUDED_KINDS:
        reasons.append(EXCLUDED_KINDS[kind])
    text = _normalise(f"{piece_row.get('notes') or ''} {piece_row.get('name') or ''}")
    for stem, reason in EXCLUDED_STEMS.items():
        if re.search(rf"\b{stem}", text) and reason not in reasons:
            reasons.append(reason)
    return reasons


def _photo_problems(path: Path, validator: Validator) -> list[str]:
    path = Path(path)
    if not path.is_file():
        return ["No se pudo descargar la foto"]
    size = path.stat().st_size
    if size > MAX_PHOTO_BYTES:
        mb = f"{size / 1024 / 1024:.1f}".replace(".", ",")
        return [f"La foto pesa {mb} MB (máximo 20 MB)"]
    try:
        with Image.open(path) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        return ["El archivo no es una imagen que podamos leer (usa JPG, PNG o WEBP)"]
    return list(validator(path))


def check(
    piece_row: dict[str, Any],
    photo_paths: Sequence[Path],
    *,
    validator: Validator = validate_input,
) -> list[str]:
    """Problems that send the piece to ``needs_photos`` (Spanish, empty when it can run).

    Excluded categories first (no photo check is worth it then), then each photo: present,
    ≤ 20 MB, a readable image and ``validate_input``. Problems of photo ``n`` are prefixed
    «Foto n:»."""
    reasons = excluded_reasons(piece_row)
    if reasons:
        return reasons
    if not photo_paths:
        return ["La pieza no tiene ninguna foto"]
    problems: list[str] = []
    for n, path in enumerate(photo_paths, start=1):
        problems += [f"Foto {n}: {p}" for p in _photo_problems(path, validator)]
    return problems


def explain(problems: Sequence[str]) -> str:
    """Spanish message stored in ``pieces.error`` for ``needs_photos``."""
    if not problems:
        return ""
    if any(p.startswith("Foto ") or p.startswith("La pieza no tiene") for p in problems):
        lines = ["Las fotos no se pueden usar todavía:"]
        lines += [f"· {p}" for p in problems]
        lines += ["", "Requisitos de la foto:"]
        lines += [f"· {req}" for req in PHOTO_REQUIREMENTS]
        return "\n".join(lines)
    return "\n".join(problems)


def is_rectilinear(piece_row: dict[str, Any]) -> bool:
    """Explicit ``rectilinear`` wins; when null, the form's kind decides."""
    value = piece_row.get("rectilinear")
    if value is not None:
        return bool(value)
    return (piece_row.get("kind") or "") in RECTILINEAR_KINDS


def build_piece(piece_row: dict[str, Any], photo_paths: Sequence[Path]) -> Piece:
    """Harness ``Piece`` for a ``pieces`` row (``rectilinear`` resolved, never None)."""
    kind = piece_row.get("kind") or "otro"
    notes = (piece_row.get("notes") or "").strip()
    kind_text = KIND_TEXT.get(kind, "")
    # Notes first: a "mesa auxiliar de travertino" still becomes a panel table.
    description = " · ".join(part for part in (notes, kind_text) if part)
    return Piece(
        id=str(piece_row["id"]),
        name=(piece_row.get("name") or kind).strip() or kind,
        store="plataforma",
        source_url="",
        category=KIND_CATEGORY.get(kind, "macizo_mate"),
        images=[Path(p) for p in photo_paths],
        width_cm=float(piece_row["width_cm"]),
        height_cm=float(piece_row["height_cm"]),
        depth_cm=float(piece_row["depth_cm"]),
        description=description,
        rectilinear=is_rectilinear(piece_row),
    )


def parametric_kind_override(piece_row: dict[str, Any]) -> str | None:
    """``"box"`` for headboards and panels (a slab-like box, never a table)."""
    return "box" if (piece_row.get("kind") or "") in BOX_KINDS else None
