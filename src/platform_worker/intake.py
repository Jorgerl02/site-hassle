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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from harness.core.models import Piece
from harness.prep.clean import MIN_BBOX_FRACTION, MIN_LONG_SIDE_PX, validate_input
from platform_worker.interpret import Interpretation, merge_answers

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

Validator = Callable[[Path], list[str]]

# Customer-facing photo requirements (English); the harness keeps its Spanish list for the CLI.
PHOTO_REQUIREMENTS: list[str] = [
    "A front or three-quarter view of the piece.",
    "A light or plain background, with no other furniture or objects around it.",
    "The whole piece in the frame, not cropped at any edge.",
    f"At least {MIN_LONG_SIDE_PX:,} px on the long side.",
    f"The piece should fill at least {MIN_BBOX_FRACTION:.0%} of the photo's long side.",
]

# Customer copy for a photo where background removal finds nothing (no technical detail).
NO_OBJECT_MESSAGE = (
    "We couldn't find the piece in the photo. Use a photo where the whole piece is visible "
    "on a plain background."
)

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
        return NO_OBJECT_MESSAGE
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


def build_piece(
    piece_row: dict[str, Any], photo_paths: Sequence[Path], routing: Routing | None = None
) -> Piece:
    """Harness ``Piece`` for a ``pieces`` row (``rectilinear`` resolved, never None).

    With ``routing`` the effective kind (customer or photo) feeds the description and
    ``rectilinear`` is the route's (True only on E); without it, the row's own answers."""
    kind = piece_row.get("kind") or "otro"
    if routing is not None:
        kind = str(routing.effective.get("kind") or kind)
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
        rectilinear=routing.rectilinear if routing is not None else is_rectilinear(piece_row),
    )


# --------------------------------------------------------------------------- routing

ROUTE_E = "E"
ROUTE_ORGANIC = "organic"
# Organic piece and no provider, while the photo reading is not sure it is organic: the admin
# fixes the shape answers and regenerates (instead of a ``failed`` piece).
ROUTE_MANUAL = "manual"


@dataclass
class Routing:
    """Where a piece goes, from its effective answers (``interpret.merge_answers``).

    ``route``: ``E`` (parametric, ``kind`` + ``params`` forced, or E's own classification
    when ``kind`` is None), ``organic`` (provider) or ``manual`` (no model: admin review
    with ``reasons``). ``effective`` is the merge result (JSON-ready); ``reasons`` are
    Spanish sentences for the admin."""

    route: str
    kind: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    effective: dict[str, Any] = field(default_factory=dict)
    # A support conflict with a confident central pedestal: built as the photo shows.
    photo_overrides_support: bool = False

    @property
    def rectilinear(self) -> bool:
        """``Piece.rectilinear`` for the harness: True on route E, else False."""
        return self.route == ROUTE_E


def customer_answers(piece_row: dict[str, Any]) -> dict[str, Any]:
    """What ``merge_answers`` needs from a ``pieces`` row (answers + notes + dimensions)."""
    return {
        "kind": piece_row.get("kind"),
        "rectilinear": piece_row.get("rectilinear"),
        "support": piece_row.get("support"),
        "notes": piece_row.get("notes") or "",
        "width_cm": piece_row.get("width_cm"),
        "depth_cm": piece_row.get("depth_cm"),
    }


def _pedestal_params(effective: dict[str, Any]) -> dict[str, Any]:
    params = dict(effective.get("pedestal_params") or {})
    return {k: v for k, v in params.items() if v is not None}


def decide_route(
    piece_row: dict[str, Any],
    interpretation: Interpretation,
    *,
    provider_available: bool,
) -> Routing:
    """Route of a piece from the customer's answers and the photo interpretation.

    - ``routing_kind`` set (table / panel_table / box / box_legs / pedestal) → E with that
      kind (and ``pedestal_params`` for a pedestal).
    - A support conflict where the photo shows a confident central pedestal (the form
      cannot say «pie central», so «patas» was the customer's closest answer) → E pedestal
      as the photo shows; the conflict still sends the piece to manual review.
    - The customer said explicitly «es recta» but no support is known → E with its own
      classification. «No sé»/default never forces E by itself.
    - Otherwise organic (provider). Without a provider: an organic piece the customer or a
      confident photo reading says is organic stays ``organic`` (the pipeline fails it
      with the «no provider» message); anything unsure goes to manual review."""
    customer = customer_answers(piece_row)
    effective = merge_answers(customer, interpretation)
    routing = Routing(route=ROUTE_ORGANIC, effective=effective)
    kind = effective.get("routing_kind")
    params: dict[str, Any] = {}
    if kind == "pedestal":
        params = _pedestal_params(effective)
    support_conflict = next(
        (c for c in effective.get("conflict") or [] if c.get("field") == "support"), None
    )
    if (
        support_conflict is not None
        and support_conflict.get("inferred") == "pie_central"
        and effective.get("rectilinear") is not False
    ):
        from_photo = merge_answers({**customer, "support": None}, interpretation)
        if from_photo.get("routing_kind") == "pedestal":
            kind, params = "pedestal", _pedestal_params(from_photo)
            routing.photo_overrides_support = True
            routing.reasons.append(
                "Conflicto de apoyo: el cliente dijo «"
                f"{support_conflict.get('customer')}» y la foto muestra un pie central "
                f"({support_conflict.get('confidence', 0):.0%}); se construye el pedestal de "
                "la foto"
            )

    source = effective.get("source") or {}
    if kind is not None:
        routing.route, routing.kind, routing.params = ROUTE_E, kind, params
        routing.reasons.append(f"Ruta E: tipo paramétrico «{kind}»")
        return routing
    if effective.get("rectilinear") is True and source.get("rectilinear") == "customer":
        routing.route = ROUTE_E
        routing.reasons.append(
            "Ruta E: el cliente dice que es recta (tipo por la clasificación de E)"
        )
        return routing

    organic_sure = effective.get("rectilinear") is False
    if provider_available or organic_sure:
        routing.reasons.append(
            "Ruta orgánica: "
            + (
                "pieza no recta"
                if organic_sure
                else "la foto no basta para construirla con piezas rectas"
            )
        )
        return routing

    routing.route = ROUTE_MANUAL
    if effective.get("rectilinear") is True:
        routing.reasons.append(
            "La foto parece de una pieza recta, pero no se sabe cómo se apoya y no hay "
            "proveedor orgánico: fija el apoyo (y el tipo) y regenera"
        )
    else:
        routing.reasons.append(
            "La interpretación de la foto no es fiable "
            f"(confianza {interpretation.confidence:.0%}) y no hay proveedor orgánico: "
            "fija la forma (tipo, recta, apoyo) y regenera"
        )
    return routing


# --------------------------------------------------------------------------- material

# The admin's «Aplicar material» travels in ``pieces.review_note`` as ``material:<id>``
# (``material:none`` turns the automatic detection off for the next attempt).
MATERIAL_NONE = "none"
_MATERIAL_NOTE = re.compile(r"(?:^|\s)material:([a-z_]+)\b")


def material_from_note(review_note: str | None) -> str | None:
    """``<id>`` of the last ``material:<id>`` token in the admin's note, or None."""
    found = _MATERIAL_NOTE.findall(review_note or "")
    return found[-1] if found else None
