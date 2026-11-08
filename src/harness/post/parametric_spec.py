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

Kind = Literal["table", "panel_table", "shelf", "sideboard", "slab", "box", "box_legs"]
KINDS: tuple[str, ...] = (
    "table",
    "panel_table",
    "shelf",
    "sideboard",
    "slab",
    "box",
    "box_legs",
)
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
# panel_table: a top on vertical panels instead of legs (p04 teak coffee table, p07 marble
# side table). ``panel_inset`` is the distance from the top's edge to the panel's outer face.
PANEL_THICKNESS = 3.0
PANEL_INSET_RATIO = 0.08  # default panel_inset = 8 % of the width
PANEL_LAYOUTS: tuple[str, ...] = ("sides", "pairs")
PANEL_FIN_RATIO = 0.5  # "pairs": length of the perpendicular panel = 50 % of the depth
# "pairs" seen from above: "T" = fin at mid-depth of the end panel, "L" = fin at its front end
PANEL_PAIR_SHAPES: tuple[str, ...] = ("T", "L")
PANEL_TABLE_PARAMS: tuple[str, ...] = (
    "top_thickness",
    "panel_thickness",
    "panel_inset",
    "panel_layout",
    "panel_fin_length",
    "panel_pair_shape",
    "shelf_height_cm",
)
# box_legs: a closed body on four square legs (p03 shoe cabinet) and/or on a recessed
# plinth (p08 bedside table). Legs are used when ``leg_height_cm`` is given or no plinth is;
# with both, the plinth stands on the legs. ``leg_inset_cm`` = distance to the outer leg
# face from the body edge, or from the plinth footprint when there is a plinth (real
# distance from the body edge = plinth_inset_cm + leg_inset_cm).
BOX_LEG_HEIGHT = 10.0
BOX_LEG_SIZE = 5.0
BOX_LEG_INSET = 3.0
BOX_PLINTH_HEIGHT = 5.0  # only used when the text says "zócalo" without a height
BOX_PLINTH_INSET = 2.0
BOX_BASE_MAX_RATIO = 0.5  # legs + plinth never take more than half the height
# Texture hints of the body (always applied for box_legs):
# - ``side_edge`` (fraction of the photo width, default BOX_SIDE_EDGE): its sides and top
#   sample the photo's left ``side_edge`` columns (the solid frame stile) instead of the
#   whole front, so drawers are not repeated on the sides and the top shows no rim;
# - ``top_crop`` (fraction of the photo height, default BOX_TOP_CROP): its vertical faces
#   stop that many rows below the photo's top edge, so the rim of the top seen from above
#   is not mapped onto the upper edge of the front / sides.
BOX_SIDE_EDGE = 0.03
BOX_TOP_CROP = 0.03
BOX_LEGS_PARAMS: tuple[str, ...] = (
    "leg_height_cm",
    "leg_size_cm",
    "leg_inset_cm",
    "plinth_height_cm",
    "plinth_inset_cm",
    "side_edge",
    "top_crop",
)
# Checked AFTER ``KEYWORDS`` (a "mesa con patas" stays a table): base words → box_legs.
BOX_LEGS_WORDS: tuple[str, ...] = ("pata",)
BOX_PLINTH_WORDS: tuple[str, ...] = ("zocalo",)

# Spanish keywords (accent-free, lowercase). The earliest match in the text wins, so
# "mesa con tablero de travertino" is a table and "tablero para mesa" is a slab.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "table": ("mesa", "mesita", "escritorio", "consola"),
    "shelf": ("estanteria", "estante", "libreria", "librero", "balda"),
    "sideboard": ("aparador", "comoda", "credenza", "buffet", "cajonera", "mueble tv"),
    "slab": ("encimera", "losa", "tablero", "placa", "lamina"),
}

# Checked BEFORE ``KEYWORDS`` (anywhere in the text): any panel keyword, or "auxiliar"
# together with a stone word → panel_table ("Mesa auxiliar de mármol" is a panel table).
PANEL_KEYWORDS: tuple[str, ...] = ("panel", "laterales", "estructura en u")
PANEL_AUX_WORD = "auxiliar"
PANEL_STONE_WORDS: tuple[str, ...] = ("marmol", "travertino", "piedra")

SLAB_MAX_HEIGHT_RATIO = 0.15  # height / max(width, depth) below this → slab
SHELF_MIN_HEIGHT_RATIO = 1.5  # height / width above this (and shallow) → shelf
SHELF_MAX_DEPTH = 50.0


@dataclass(frozen=True)
class Box:
    name: str
    size_cm: tuple[float, float, float]
    pos_cm: tuple[float, float, float]
    # Optional photo rows (Blender v, 0 = bottom) sampled by this box's vertical faces,
    # bottom→top of the box; None = straight projection over the whole piece height.
    uv_v: tuple[float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "size_cm": list(self.size_cm),
            "pos_cm": list(self.pos_cm),
        }
        if self.uv_v is not None:
            out["uv_v"] = list(self.uv_v)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Box:
        size = tuple(float(v) for v in data["size_cm"])
        pos = tuple(float(v) for v in data["pos_cm"])
        if len(size) != 3 or len(pos) != 3:
            raise ValueError(f"Box {data.get('name')!r}: size_cm y pos_cm deben tener 3 valores")
        uv_v = data.get("uv_v")
        return cls(
            name=str(data["name"]),
            size_cm=size,  # type: ignore[arg-type]
            pos_cm=pos,  # type: ignore[arg-type]
            uv_v=(float(uv_v[0]), float(uv_v[1])) if uv_v is not None else None,
        )


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


def _has_word(norm: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}", norm) is not None


def is_panel_text(text: str) -> bool:
    """Panel keywords ("panel", "paneles", "patas de panel", "laterales", "estructura en U")
    or "auxiliar" + "mármol"/"travertino"/"piedra"."""
    norm = _normalise(text)
    if any(_has_word(norm, w) for w in PANEL_KEYWORDS):
        return True
    return _has_word(norm, PANEL_AUX_WORD) and any(_has_word(norm, w) for w in PANEL_STONE_WORDS)


def classify_text(text: str) -> str | None:
    """``panel_table`` if :func:`is_panel_text`, else the kind whose keyword appears earliest
    in ``text`` (whole-word prefix match), or None."""
    if is_panel_text(text):
        return "panel_table"
    norm = _normalise(text)
    best: tuple[int, str] | None = None
    for kind, words in KEYWORDS.items():
        for word in words:
            match = re.search(rf"\b{re.escape(word)}", norm)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), kind)
    return best[1] if best else None


def base_params_from_text(text: str) -> dict[str, Any] | None:
    """box_legs params implied by ``text``: "zócalo" → plinth (plus default legs if "patas"
    is also there), "patas" → legs; None when neither word appears."""
    norm = _normalise(text)
    legs = any(_has_word(norm, w) for w in BOX_LEGS_WORDS)
    plinth = any(_has_word(norm, w) for w in BOX_PLINTH_WORDS)
    if not legs and not plinth:
        return None
    params: dict[str, Any] = {}
    if plinth:
        params["plinth_height_cm"] = BOX_PLINTH_HEIGHT
    if legs and plinth:
        params["leg_height_cm"] = BOX_LEG_HEIGHT
    return params


def classify_with_params(piece: Piece) -> tuple[Kind, dict[str, Any]]:
    """Heuristic ``(kind, params)``: description keywords first, then name, then
    proportions (slab / shelf); a remaining ``box`` becomes ``box_legs`` when the text has
    a base word ("patas" / "zócalo")."""
    texts = (piece.description or "", piece.name or "")
    for text in texts:
        kind = classify_text(text)
        if kind is not None:
            return kind, {}  # type: ignore[return-value]
    w, h, d = piece.width_cm, piece.height_cm, piece.depth_cm
    if h <= SLAB_MAX_HEIGHT_RATIO * max(w, d):
        return "slab", {}
    if h >= SHELF_MIN_HEIGHT_RATIO * w and d <= SHELF_MAX_DEPTH:
        return "shelf", {}
    # The base words only refine a plain box ("perchero con patas" stays a shelf).
    for text in texts:
        params = base_params_from_text(text)
        if params is not None:
            return "box_legs", params
    return "box", {}


def classify(piece: Piece) -> Kind:
    """Heuristic kind (see :func:`classify_with_params`)."""
    return classify_with_params(piece)[0]


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


def panel_table_params(w: float, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolved panel_table parameters (defaults filled in); rejects unknown keys."""
    params = dict(params or {})
    unknown = sorted(set(params) - set(PANEL_TABLE_PARAMS))
    if unknown:
        raise ValueError(f"panel_table: parámetros desconocidos {unknown}")
    layout = params.get("panel_layout", "sides")
    if layout not in PANEL_LAYOUTS:
        raise ValueError(f"panel_table: panel_layout {layout!r} (válidos: {PANEL_LAYOUTS})")
    shape = params.get("panel_pair_shape", "T")
    if shape not in PANEL_PAIR_SHAPES:
        raise ValueError(f"panel_table: panel_pair_shape {shape!r} (válidos: {PANEL_PAIR_SHAPES})")
    shelf = params.get("shelf_height_cm")
    return {
        "top_thickness": float(params.get("top_thickness", TABLE_TOP_THICKNESS)),
        "panel_thickness": float(params.get("panel_thickness", PANEL_THICKNESS)),
        "panel_inset": float(params.get("panel_inset", PANEL_INSET_RATIO * w)),
        "panel_layout": layout,
        "panel_fin_length": (
            float(params["panel_fin_length"]) if "panel_fin_length" in params else None
        ),
        "panel_pair_shape": shape,
        "shelf_height_cm": float(shelf) if shelf is not None else None,
    }


def _panel_table(w: float, d: float, h: float, params: dict[str, Any] | None) -> list[Box]:
    p = panel_table_params(w, params)
    top_t = min(p["top_thickness"], h / 2)
    pt = min(p["panel_thickness"], w / 4)
    inset = min(max(p["panel_inset"], 0.0), w / 2 - pt)  # outer face never past the centre
    panel_h = h - top_t
    x_out = w / 2 - inset  # outer face of each panel
    xc = x_out - pt / 2
    x_in = x_out - pt  # inner face
    boxes = [Box("top", (w, d, top_t), (0.0, 0.0, h - top_t / 2))]
    if p["panel_layout"] == "sides":
        panel_d = d
        for side, sign in (("l", -1), ("r", 1)):
            boxes.append(
                Box(f"panel_{side}", (pt, panel_d, panel_h), (sign * xc, 0.0, panel_h / 2))
            )
    else:  # "pairs": an end panel along the depth + a perpendicular fin (T or L)
        inset_d = min(inset, d / 4)
        panel_d = d - 2 * inset_d
        fin = p["panel_fin_length"] if p["panel_fin_length"] is not None else PANEL_FIN_RATIO * d
        fin = max(min(fin, x_in), 0.0)
        fin_y = 0.0 if p["panel_pair_shape"] == "T" else -(panel_d / 2 - pt / 2)
        for side, sign in (("l", -1), ("r", 1)):
            boxes.append(
                Box(f"panel_{side}", (pt, panel_d, panel_h), (sign * xc, 0.0, panel_h / 2))
            )
            if fin > 0:
                boxes.append(
                    Box(
                        f"panel_{side}_fin",
                        (fin, pt, panel_h),
                        (sign * (x_in - fin / 2), fin_y, panel_h / 2),
                    )
                )
    shelf = p["shelf_height_cm"]
    if shelf is not None:
        shelf_t = top_t
        z_top = min(max(shelf, shelf_t), panel_h)  # shelf_height_cm = height of its top face
        boxes.append(Box("shelf", (2 * x_in, panel_d, shelf_t), (0.0, 0.0, z_top - shelf_t / 2)))
    return boxes


def box_legs_params(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolved box_legs parameters; rejects unknown keys. ``leg_height_cm`` is None when
    the piece has no legs (a plinth only), ``plinth_height_cm`` None without plinth."""
    params = dict(params or {})
    unknown = sorted(set(params) - set(BOX_LEGS_PARAMS))
    if unknown:
        raise ValueError(f"box_legs: parámetros desconocidos {unknown}")
    plinth = params.get("plinth_height_cm")
    leg = params.get("leg_height_cm", None if plinth is not None else BOX_LEG_HEIGHT)
    out = {
        "leg_height_cm": float(leg) if leg is not None else None,
        "leg_size_cm": float(params.get("leg_size_cm", BOX_LEG_SIZE)),
        "leg_inset_cm": float(params.get("leg_inset_cm", BOX_LEG_INSET)),
        "plinth_height_cm": float(plinth) if plinth is not None else None,
        "plinth_inset_cm": float(params.get("plinth_inset_cm", BOX_PLINTH_INSET)),
        "side_edge": float(params.get("side_edge", BOX_SIDE_EDGE)),
        "top_crop": float(params.get("top_crop", BOX_TOP_CROP)),
    }
    if not 0.0 < out["side_edge"] <= 1.0:
        raise ValueError(f"box_legs: side_edge debe estar en (0, 1] ({out['side_edge']})")
    if not 0.0 <= out["top_crop"] < 0.5:
        raise ValueError(f"box_legs: top_crop debe estar en [0, 0.5) ({out['top_crop']})")
    for key, value in out.items():
        if value is not None and value < 0:
            raise ValueError(f"box_legs: {key} no puede ser negativo ({value})")
    return out


def _box_legs(w: float, d: float, h: float, params: dict[str, Any] | None) -> list[Box]:
    p = box_legs_params(params)
    leg_h = p["leg_height_cm"] or 0.0
    plinth_h = p["plinth_height_cm"] or 0.0
    base_max = BOX_BASE_MAX_RATIO * h
    if leg_h + plinth_h > base_max:  # scale the base down on very low pieces
        scale = base_max / (leg_h + plinth_h)
        leg_h, plinth_h = leg_h * scale, plinth_h * scale
    base_h = leg_h + plinth_h
    body_h = h - base_h
    boxes = [Box("body", (w, d, body_h), (0.0, 0.0, base_h + body_h / 2))]
    if plinth_h > 0:
        inset = min(max(p["plinth_inset_cm"], 0.0), w / 4, d / 4)
        boxes.append(
            Box(
                "plinth",
                (w - 2 * inset, d - 2 * inset, plinth_h),
                (0.0, 0.0, leg_h + plinth_h / 2),
            )
        )
    if leg_h > 0:
        side = min(max(p["leg_size_cm"], 0.1), w / 2, d / 2)
        # Legs under a plinth sit under the plinth's footprint.
        ref_w = boxes[-1].size_cm[0] if plinth_h > 0 else w
        ref_d = boxes[-1].size_cm[1] if plinth_h > 0 else d
        boxes.extend(_legs(ref_w, ref_d, leg_h, side, p["leg_inset_cm"]))
    return boxes


def build_spec(piece: Piece, kind: str, params: dict[str, Any] | None = None) -> list[Box]:
    """Boxes (cm) for ``piece`` built as ``kind``; their union bbox equals the piece's dims.

    ``params`` only applies to ``panel_table`` (see :data:`PANEL_TABLE_PARAMS`) and
    ``box_legs`` (see :data:`BOX_LEGS_PARAMS`); other kinds reject non-empty params."""
    w, h, d = float(piece.width_cm), float(piece.height_cm), float(piece.depth_cm)
    if params and kind not in ("panel_table", "box_legs"):
        raise ValueError(f"El tipo {kind!r} no admite parámetros ({sorted(params)})")
    if kind == "panel_table":
        return _panel_table(w, d, h, params)
    if kind == "box_legs":
        return _box_legs(w, d, h, params)
    if kind == "table":
        return _table(w, d, h)
    if kind == "shelf":
        return _shelf(w, d, h)
    if kind == "sideboard":
        return _sideboard(w, d, h)
    if kind in ("slab", "box"):
        return [Box(kind, (w, d, h), (0.0, 0.0, h / 2))]
    raise ValueError(f"Tipo desconocido: {kind!r} (válidos: {', '.join(KINDS)})")


TOP_EDGE_ROWS = 0.06  # photo rows (fraction) above the top/support split = the top's edge
SUPPORT_V_FLOOR = 0.04  # supports skip the photo's lowest rows (floor shadow / fill halo)


def with_photo_regions(boxes: list[Box], top_row: float | None) -> list[Box]:
    """panel_table: map the vertical faces of the top onto the photo rows just above
    ``top_row`` (its front edge) and those of the supports (panels, shelf) onto the rows
    below it, so panels do not show the photo's top surface. ``top_row`` is the fraction
    of photo rows, from the top, where the top ends (None → boxes unchanged)."""
    if top_row is None or not 0.0 < top_row < 1.0:
        return boxes
    split = 1.0 - top_row  # Blender v of the split (v = 0 at the bottom of the photo)
    edge = min(TOP_EDGE_ROWS, top_row)
    out = []
    for b in boxes:
        uv_v = (split, split + edge) if b.name == "top" else None
        if b.name != "top":
            # supports start at the floor; scale their z range onto [0, split]
            z0 = b.pos_cm[2] - b.size_cm[2] / 2
            z1 = b.pos_cm[2] + b.size_cm[2] / 2
            top_z = max(bb.pos_cm[2] - bb.size_cm[2] / 2 for bb in boxes if bb.name == "top")
            lo = min(SUPPORT_V_FLOOR, split)
            uv_v = (
                (lo + (split - lo) * z0 / top_z, lo + (split - lo) * z1 / top_z)
                if top_z > 0
                else None
            )
        out.append(Box(b.name, b.size_cm, b.pos_cm, uv_v))
    return out


def bounding_box(boxes: list[Box]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(min_xyz, max_xyz) of the union of ``boxes`` in cm."""
    mins = tuple(min(b.pos_cm[i] - b.size_cm[i] / 2 for b in boxes) for i in range(3))
    maxs = tuple(max(b.pos_cm[i] + b.size_cm[i] / 2 for b in boxes) for i in range(3))
    return mins, maxs


def _body_v(box: Box, h: float, top_crop: float) -> tuple[float, float]:
    """Photo rows of ``box``: the straight projection (v = z / height) at its bottom, the
    photo's top edge minus ``top_crop`` at its top."""
    z0 = box.pos_cm[2] - box.size_cm[2] / 2
    return (z0 / h, 1.0 - top_crop)


def make_spec(
    piece: Piece,
    kind: str,
    texture: Path | None = None,
    params: dict[str, Any] | None = None,
    photo_regions: dict[str, Any] | None = None,
) -> Spec:
    """``photo_regions`` (``{"top_row": f, "side_band": [u0, u1]}``, from the cleaned photo)
    is only used by ``panel_table``: per-box ``uv_v`` and ``extra["side_band"]``.
    ``box_legs`` hints its body (rows from the straight projection at its bottom up to
    ``1 - top_crop``) and sets ``extra["side_band"] = [0, side_edge]``, which its sides and
    top sample."""
    extra: dict[str, Any] = {"piece_id": piece.id}
    if params:
        extra["params"] = dict(params)
    boxes = build_spec(piece, kind, params)
    if kind == "panel_table" and photo_regions:
        boxes = with_photo_regions(boxes, photo_regions.get("top_row"))
        if photo_regions.get("side_band") is not None:
            extra["side_band"] = [float(v) for v in photo_regions["side_band"]]
    if kind == "box_legs":
        p = box_legs_params(params)
        h = float(piece.height_cm)
        boxes = [
            Box(b.name, b.size_cm, b.pos_cm, _body_v(b, h, p["top_crop"]))
            if b.name == "body"
            else b
            for b in boxes
        ]
        extra["side_band"] = [0.0, p["side_edge"]]
    return Spec(
        kind=kind,
        boxes=boxes,
        texture=str(texture) if texture is not None else None,
        dims_cm=(piece.width_cm, piece.depth_cm, piece.height_cm),
        extra=extra,
    )


def write_spec(path: Path, spec: Spec) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_spec(path: Path) -> Spec:
    return Spec.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
