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
from harness.prep.clean import MIN_BBOX_FRACTION, MIN_LONG_SIDE_PX, validate_input

MAX_PHOTO_BYTES = 20 * 1024 * 1024  # same 20 MB limit as the upload form

# Form kinds (enum ``piece_kind``) that are boxes for the parametric route E.
RECTILINEAR_KINDS: frozenset[str] = frozenset(
    {"cabecero", "panel", "mesita", "aparador", "estanteria", "mesa"}
)
ORGANIC_KINDS: frozenset[str] = frozenset({"sofa", "sillon", "silla", "jarron", "otro"})
# Customer-facing (English): stored in ``pieces.reject_reason`` and shown on the piece page.
EXCLUDED_KINDS: dict[str, str] = {
    "lampara": (
        "We don't do lamps yet: they are usually metal, chrome or glass with thin tubes, "
        "and the 3D generators lose the reflections and warp the curves."
    ),
}
# Accent-free, lowercase keyword → reason (text of docs/promesa.md, «Categorías excluidas»).
_REFLECTION = "the 3D generators lose the reflections and warp the curves."
_TRANSPARENCY = "reflections and transparency don't come out right."
_METAL = f"We don't do metal pieces yet: {_REFLECTION}"
_CHROME = f"We don't do chrome pieces yet: {_REFLECTION}"
_GLASS = f"We don't do glass pieces yet: {_TRANSPARENCY}"
# Word-start stems (accent-free), Spanish and English, so «cromadas», «metálica»,
# «inoxidable», "chromed" or "glassware" are caught. Mirrors ``EXCLUDED_RE`` on the web.
EXCLUDED_STEMS: dict[str, str] = {
    "metal": _METAL,
    "acero": _METAL,
    "inox": _METAL,
    "steel": _METAL,
    "stainless": _METAL,
    "crom": _CHROME,
    "chrom": _CHROME,
    "vidri": _GLASS,
    "cristal": _GLASS,
    "acristal": _GLASS,
    "glass": _GLASS,
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
# «¿Cómo se apoya la pieza?» (``pieces.support``) → parametric kind of route E. ``caja`` is
# resolved in :func:`parametric_kind_override` (box, or box_legs with a base word in the
# notes); ``no_se``/null keep the heuristic.
SUPPORT_KINDS: dict[str, str] = {"patas": "table", "paneles": "panel_table"}
_BASE_WORDS = re.compile(r"\b(patas?|zocalo)\b")

Validator = Callable[[Path], list[str]]

# Customer-facing photo requirements (English); the harness keeps its Spanish list for the CLI.
PHOTO_REQUIREMENTS: list[str] = [
    "A front or three-quarter view of the piece.",
    "A light or plain background, with no other furniture or objects around it.",
    "The whole piece in the frame, not cropped at any edge.",
    f"At least {MIN_LONG_SIDE_PX:,} px on the long side.",
    f"The piece should fill at least {MIN_BBOX_FRACTION:.0%} of the photo's long side.",
]

_LOW_RES = re.compile(r"^Resolución insuficiente: lado mayor ([\d.]+) px")
_NO_OBJECT = re.compile(r"^Objeto no detectado")
_TOO_SMALL = re.compile(r"^Objeto demasiado pequeño")


def _english_issue(issue: str) -> str:
    """English customer copy for a Spanish ``validate_input`` issue (unknown ones pass through)."""
    if match := _LOW_RES.match(issue):
        long_side = int(match.group(1).replace(".", ""))
        return (
            f"The resolution is too low: {long_side:,} px on the long side "
            f"(we need at least {MIN_LONG_SIDE_PX:,} px)"
        )
    if _NO_OBJECT.match(issue):
        return "We couldn't find the piece in the photo (background removal found nothing)"
    if _TOO_SMALL.match(issue):
        return (
            "The piece is too small in the photo: its longest side should fill at least "
            f"{MIN_BBOX_FRACTION:.0%} of the photo's long side"
        )
    return issue


def validate_photo(path: Path) -> list[str]:
    """``harness.prep.clean.validate_input`` with its issues in English for the customer."""
    return [_english_issue(issue) for issue in validate_input(path)]


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
        return ["We couldn't download the photo"]
    size = path.stat().st_size
    if size > MAX_PHOTO_BYTES:
        mb = f"{size / 1024 / 1024:.1f}"
        return [f"The photo is {mb} MB (20 MB max)"]
    try:
        with Image.open(path) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        return ["The file isn't an image we can read (use JPG, PNG or WebP)"]
    return list(validator(path))


def check(
    piece_row: dict[str, Any],
    photo_paths: Sequence[Path],
    *,
    validator: Validator = validate_photo,
) -> list[str]:
    """Problems that send the piece to ``needs_photos`` (English, empty when it can run).

    Excluded categories first (no photo check is worth it then), then each photo: present,
    ≤ 20 MB, a readable image and ``validate_input``. Problems of photo ``n`` are prefixed
    "Photo n:"."""
    reasons = excluded_reasons(piece_row)
    if reasons:
        return reasons
    if not photo_paths:
        return ["The piece has no photos"]
    problems: list[str] = []
    for n, path in enumerate(photo_paths, start=1):
        problems += [f"Photo {n}: {p}" for p in _photo_problems(path, validator)]
    return problems


def explain(problems: Sequence[str]) -> str:
    """English message stored in ``pieces.error`` for ``needs_photos`` (shown to the customer)."""
    if not problems:
        return ""
    if any(p.startswith("Photo ") or p.startswith("The piece has no photos") for p in problems):
        lines = ["We can't use these photos yet:"]
        lines += [f"· {p}" for p in problems]
        lines += ["", "What a good photo looks like:"]
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
    """Parametric kind forced for route E, or None for the heuristic.

    The customer's support answer wins: ``patas`` → ``table``, ``paneles`` → ``panel_table``
    (side panels, the default layout), ``caja`` → ``box`` or ``box_legs`` when the notes say
    «patas»/«zócalo». Without an answer (``no_se``/null), headboards and panels are a plain
    ``box`` (a slab-like box, never a table) and everything else is classified."""
    support = piece_row.get("support")
    if support in SUPPORT_KINDS:
        return SUPPORT_KINDS[support]
    if support == "caja":
        notes = _normalise(piece_row.get("notes") or "")
        return "box_legs" if _BASE_WORDS.search(notes) else "box"
    return "box" if (piece_row.get("kind") or "") in BOX_KINDS else None
