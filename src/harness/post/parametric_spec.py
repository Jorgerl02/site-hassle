"""Pure parametric description of rectilinear furniture as a list of boxes (variant E).

Coordinate frame (cm, Blender Z-up): X = width (centred on 0), Y = depth (centred on 0,
the front face of the piece looks towards -Y), Z = height (floor at 0). ``Box.size_cm`` is
``(x, y, z)`` = (width, depth, height) and ``Box.pos_cm`` is the box *centre*.

The JSON written by :func:`write_spec` is read inside Blender by ``bpy_parametric.py``,
which cannot import this package, so the format is plain JSON (see :meth:`Spec.to_dict`).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from harness.core.models import Piece

Kind = Literal["table", "shelf", "sideboard", "slab", "box"]
KINDS: tuple[str, ...] = ("table", "shelf", "sideboard", "slab", "box")
SPEC_VERSION = 1

# Default construction dimensions (cm).
TABLE_TOP_THICKNESS = 4.0
LEG_SIDE = 5.0
LEG_INSET = 5.0  # distance from the edge of the top / body to the outer face of a leg
SHELF_BOARDS = 4
SHELF_THICKNESS = 2.0  # sides and boards
SIDEBOARD_LEG_HEIGHT = 10.0
SIDEBOARD_DOOR_THICKNESS = 2.0
SIDEBOARD_DOOR_GAP = 0.5

# Spanish keywords (accent-free, lowercase). The earliest match in the text wins, so
# "mesa con tablero de travertino" is a table and "tablero para mesa" is a slab.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "table": ("mesa", "mesita", "escritorio", "consola"),
    "shelf": ("estanteria", "estante", "libreria", "librero", "balda"),
    "sideboard": ("aparador", "comoda", "credenza", "buffet", "cajonera", "mueble tv"),
    "slab": ("encimera", "losa", "tablero", "placa", "lamina"),
}

SLAB_MAX_HEIGHT_RATIO = 0.15  # height / max(width, depth) below this → slab
SHELF_MIN_HEIGHT_RATIO = 1.5  # height / width above this (and shallow) → shelf
SHELF_MAX_DEPTH = 50.0


@dataclass(frozen=True)
class Box:
    name: str
    size_cm: tuple[float, float, float]
    pos_cm: tuple[float, float, float]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "size_cm": list(self.size_cm), "pos_cm": list(self.pos_cm)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Box:
        size = tuple(float(v) for v in data["size_cm"])
        pos = tuple(float(v) for v in data["pos_cm"])
        if len(size) != 3 or len(pos) != 3:
            raise ValueError(f"Box {data.get('name')!r}: size_cm y pos_cm deben tener 3 valores")
        return cls(name=str(data["name"]), size_cm=size, pos_cm=pos)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Spec:
    kind: str
    boxes: list[Box]
    texture: str | None = None
    dims_cm: tuple[float, float, float] | None = None  # (width, depth, height)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SPEC_VERSION,
            "units": "cm",
            "kind": self.kind,
            "texture": self.texture,
            "dims_cm": list(self.dims_cm) if self.dims_cm else None,
            "boxes": [b.to_dict() for b in self.boxes],
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Spec:
        dims = data.get("dims_cm")
        return cls(
            kind=str(data["kind"]),
            boxes=[Box.from_dict(b) for b in data["boxes"]],
            texture=data.get("texture"),
            dims_cm=tuple(float(v) for v in dims) if dims else None,  # type: ignore[arg-type]
            extra=dict(data.get("extra") or {}),
        )


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def classify_text(text: str) -> str | None:
    """Kind whose keyword appears earliest in ``text`` (whole-word prefix match), or None."""
    norm = _normalise(text)
    best: tuple[int, str] | None = None
    for kind, words in KEYWORDS.items():
        for word in words:
            match = re.search(rf"\b{re.escape(word)}", norm)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), kind)
    return best[1] if best else None


def classify(piece: Piece) -> Kind:
    """Heuristic kind: description keywords first, then name, then proportions."""
    for text in (piece.description, piece.name):
        kind = classify_text(text or "")
        if kind is not None:
            return kind  # type: ignore[return-value]
    w, h, d = piece.width_cm, piece.height_cm, piece.depth_cm
    if h <= SLAB_MAX_HEIGHT_RATIO * max(w, d):
        return "slab"
    if h >= SHELF_MIN_HEIGHT_RATIO * w and d <= SHELF_MAX_DEPTH:
        return "shelf"
    return "box"


def _legs(
    w: float, d: float, leg_h: float, side: float = LEG_SIDE, inset: float = LEG_INSET
) -> list[Box]:
    # Clamp so legs never cross the centre on very small pieces.
    cx = max(w / 2 - inset - side / 2, side / 2)
    cy = max(d / 2 - inset - side / 2, side / 2)
    z = leg_h / 2
    corners = (("leg_fl", -cx, -cy), ("leg_fr", cx, -cy), ("leg_bl", -cx, cy), ("leg_br", cx, cy))
    return [Box(name, (side, side, leg_h), (x, y, z)) for name, x, y in corners]


def _table(w: float, d: float, h: float) -> list[Box]:
    top_t = min(TABLE_TOP_THICKNESS, h / 2)
    top = Box("top", (w, d, top_t), (0.0, 0.0, h - top_t / 2))
    return [top, *_legs(w, d, h - top_t)]


def _shelf(w: float, d: float, h: float) -> list[Box]:
    t = min(SHELF_THICKNESS, w / 4, h / (2 * SHELF_BOARDS))
    sides = [
        Box("side_l", (t, d, h), (-(w / 2 - t / 2), 0.0, h / 2)),
        Box("side_r", (t, d, h), (w / 2 - t / 2, 0.0, h / 2)),
    ]
    inner_w = w - 2 * t
    step = (h - t) / (SHELF_BOARDS - 1)
    boards = [
        Box(f"board_{i + 1}", (inner_w, d, t), (0.0, 0.0, t / 2 + i * step))
        for i in range(SHELF_BOARDS)
    ]
    return sides + boards


def _sideboard(w: float, d: float, h: float) -> list[Box]:
    leg_h = min(SIDEBOARD_LEG_HEIGHT, h * 0.25)
    body_h = h - leg_h
    door_t = min(SIDEBOARD_DOOR_THICKNESS, d / 4)
    body_d = d - door_t
    body = Box("body", (w, body_d, body_h), (0.0, door_t / 2, leg_h + body_h / 2))
    door_w = (w - SIDEBOARD_DOOR_GAP) / 2
    door_x = SIDEBOARD_DOOR_GAP / 2 + door_w / 2
    door_y = -d / 2 + door_t / 2
    door_z = leg_h + body_h / 2
    doors = [
        Box("door_l", (door_w, door_t, body_h), (-door_x, door_y, door_z)),
        Box("door_r", (door_w, door_t, body_h), (door_x, door_y, door_z)),
    ]
    return [body, *doors, *_legs(w, d, leg_h)]


def build_spec(piece: Piece, kind: str) -> list[Box]:
    """Boxes (cm) for ``piece`` built as ``kind``; their union bbox equals the piece's dims."""
    w, h, d = float(piece.width_cm), float(piece.height_cm), float(piece.depth_cm)
    if kind == "table":
        return _table(w, d, h)
    if kind == "shelf":
        return _shelf(w, d, h)
    if kind == "sideboard":
        return _sideboard(w, d, h)
    if kind in ("slab", "box"):
        return [Box(kind, (w, d, h), (0.0, 0.0, h / 2))]
    raise ValueError(f"Tipo desconocido: {kind!r} (válidos: {', '.join(KINDS)})")


def bounding_box(boxes: list[Box]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(min_xyz, max_xyz) of the union of ``boxes`` in cm."""
    mins = tuple(min(b.pos_cm[i] - b.size_cm[i] / 2 for b in boxes) for i in range(3))
    maxs = tuple(max(b.pos_cm[i] + b.size_cm[i] / 2 for b in boxes) for i in range(3))
    return mins, maxs


def make_spec(piece: Piece, kind: str, texture: Path | None = None) -> Spec:
    return Spec(
        kind=kind,
        boxes=build_spec(piece, kind),
        texture=str(texture) if texture is not None else None,
        dims_cm=(piece.width_cm, piece.depth_cm, piece.height_cm),
        extra={"piece_id": piece.id},
    )


def write_spec(path: Path, spec: Spec) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_spec(path: Path) -> Spec:
    return Spec.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
