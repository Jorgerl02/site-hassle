"""Automatic interpretation of a piece's photos: is it rectilinear, how does it stand, what
type is it, and do the photo and the dimensions agree.

The customer form only asks for photos and dimensions; "Type", "Is it straight?" and "How
does it stand?" are optional. When they are left at their defaults the worker infers them
here, deterministically, from three sources of evidence:

- the background-removed silhouette of the first photo (``harness.prep.clean`` rembg
  helpers): how rounded its top and bottom caps are (a round or oval top seen from slightly
  above is an ellipse, a box's top is straight), how much of its outline lies on long
  horizontal/vertical runs, and the shape of its bottom band (legs, side panels, a single
  central pedestal or a continuous base);
- the dimensions: a thin piece (``harness.variants.f_router`` rule) is a slab-like box;
- the name and notes (Spanish and English word stems): "sofá", "jarrón", "cabecero"…

:class:`Interpreter` is the seam for a vision model: any object with the same
``interpret`` signature can replace :class:`SilhouetteInterpreter`.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
from PIL import Image, ImageOps

from harness.prep.clean import BBOX_PERCENTILES
from harness.variants.f_router import THIN_MAX_RATIO, THIN_MIN_CM

Support = Literal["patas", "paneles", "caja", "pie_central"]
TopShape = Literal["rect", "round"]
# ``pie_central`` is only inferred (the form and ``pieces.support`` offer the other three).
SUPPORTS: tuple[str, ...] = ("patas", "paneles", "caja", "pie_central")
# Values ``pieces.support`` accepts (CHECK constraint); the only ones merge_answers returns.
DB_SUPPORTS: tuple[str, ...] = ("patas", "paneles", "caja", "no_se")
CUSTOMER_SUPPORTS: tuple[str, ...] = ("patas", "paneles", "caja")
# Parametric kind of route E chosen by merge_answers (``routing_kind``).
RoutingKind = Literal["table", "panel_table", "box", "box_legs", "pedestal"]
SUPPORT_ROUTING: dict[str, RoutingKind] = {"patas": "table", "paneles": "panel_table"}
BOX_KINDS: frozenset[str] = frozenset({"cabecero", "panel"})
# Base words in the notes turn a «caja» answer into box_legs (same rule as intake.py).
BASE_WORDS = re.compile(r"\b(patas?|zocalo)\b")
# E's pedestal: base_diameter_ratio range, and |w − d| / max above which the top is oval.
PEDESTAL_BASE_RANGE = (0.15, 0.95)
PEDESTAL_ROUND_TOLERANCE = 0.02
# Values of the ``piece_kind`` enum (platform database).
PIECE_KINDS: tuple[str, ...] = (
    "mesa",
    "mesita",
    "aparador",
    "estanteria",
    "cabecero",
    "panel",
    "sofa",
    "sillon",
    "silla",
    "jarron",
    "lampara",
    "otro",
)
# Defaults stored on a piece whose customer skipped the optional questions.
DEFAULT_KIND = "otro"
DEFAULT_SUPPORT = "no_se"
DEFAULT_MIN_CONFIDENCE = 0.6
# merge_answers: an inferred value this confident that contradicts an explicit customer
# answer is reported as a conflict (manual review).
CONFLICT_CONFIDENCE = 0.85

# Silhouette analysis works on the mask cropped to its percentile bbox and resized so its
# long side has this many pixels (cheap, and thresholds stay resolution-independent).
WORK_SIZE = 256
# Degenerate masks are "no object": a crop under MIN_CROP_PX on a side, or a mask covering
# less than MIN_FRAME_FILL or more than MAX_FRAME_FILL of the frame (an all-white photo).
MIN_CROP_PX = 20
MIN_FRAME_FILL = 0.01
MAX_FRAME_FILL = 0.97
# rembg runs on the photo downscaled to this long side (speed, memory).
REMBG_MAX_SIDE = 1600

# Straight outline: a run must span this fraction of the bbox's longer side and may drift
# this many work pixels across its length (slightly rotated edges still count).
STRAIGHT_MIN_RUN = 0.06
STRAIGHT_TOLERANCE_PX = 1

# Rounded caps. Walking down from the top row, the left outline moves out until the
# piece's leftmost point; for a round/oval top seen from above (an ellipse) that path bulges
# outwards from its chord by ~40 % of its horizontal extent, for a box's top edge it is a
# straight line. Same on the right side and, upside down, at the bottom (a cylinder's base).
# Caps narrower than CAP_MIN_SPAN of the width are corner radii, not round shapes.
CAP_MIN_SPAN = 0.06
CAP_MIN_ROWS = 2
ROUND_THRESHOLD = 0.15  # bulge / extent at which a cap counts as round
ROUND_SOFTNESS = 0.03

# Bottom band: rows below the body (the last row at least BODY_ROW_FILL of the widest row)
# and within the lowest BAND_MAX_FRACTION of the height; the lowest FLOOR_SKIP rows are
# ignored (rembg halo).
BAND_MAX_FRACTION = 0.20
BODY_ROW_FILL = 0.90
FLOOR_SKIP = 0.01
BAND_MIN_ROWS = 3
# A column belongs to a support when it is filled in at least this fraction of the rows of
# the band's upper half (splayed or tapered legs cross it diagonally; in a three-quarter
# view the far supports end higher than the near ones, but all of them cross that half).
COLUMN_OCCUPANCY = 0.35
RUN_MERGE_GAP = 0.02  # gaps narrower than this fraction of the width are merged
RUN_MIN_WIDTH = 0.01  # runs narrower than this fraction of the width are noise
CONTINUOUS_COVERAGE = 0.80  # filled fraction of the width for a continuous base
CENTRE_GAP = 0.06  # a gap at least this wide (fraction of the width) splits the base
PANEL_MIN_WIDTH = 0.10  # a support run at least this wide (fraction of the width) is a panel
PANEL_MIN_OCCUPANCY = 0.6  # …and fills its columns (a diagonal tube does not)
EXTREME_MARGIN = 0.25  # side panels start/end within this fraction of the width's ends
# Single central pedestal: one run centred within PEDESTAL_CENTRE of the width, narrower
# than PEDESTAL_MAX_RATIO of the top's width, whose centre column is filled up to the top;
# the top is the widest row above the band, in the upper PEDESTAL_TOP_ZONE of the height
# and solid (≥ PEDESTAL_TOP_FILL of its span: a coat rack's hooks are not a top).
PEDESTAL_CENTRE = 0.10
PEDESTAL_MAX_RATIO = 0.60
PEDESTAL_COLUMN_FILL = 0.90
PEDESTAL_TOP_ZONE = 0.45
PEDESTAL_TOP_FILL = 0.90

# Combination of the evidence into P(rectilinear) (logistic). Tuned on the 30 pilot photos
# (scripts/eval_interpret.py, tests/fixtures/platform/interpret_labels.csv).
ROUND_WEIGHT = 4.0  # ± this from the caps' roundness (outweighs any single text hint)
STRAIGHT_WEIGHT = 2.0  # × (straightness − 0.5)
THIN_WEIGHT = 3.0
TEXT_WEIGHT = 3.0  # × TextHint.evidence
# A round/oval top on one central column is buildable by E (parametric ``pedestal``):
# with a confident pie_central the round caps are expected, so this replaces the outline
# evidence.
PEDESTAL_WEIGHT = 3.0
# The log-odds are divided by this before the sigmoid: the evidence weights are hand-set,
# so the raw probabilities are overconfident (pilot errors scored 0.97–0.99 without it).
CONFIDENCE_TEMPERATURE = 2.0

# check_dimensions: tolerated mismatch between the photo's width/height and the entered
# dimensions, and between width and depth of a round top.
ASPECT_TOLERANCE = 0.30
# A three-quarter view widens the silhouette up to hypot(width, depth); a view from
# slightly above adds part of the depth to the height (product shots: ≲ 20° elevation).
ELEVATION_DEPTH_SHARE = 0.35
ROUND_TOP_RATIO = (0.75, 1.33)  # width / depth of a round top
TABLE_KINDS: frozenset[str] = frozenset({"mesa", "mesita"})


@dataclass(frozen=True)
class Interpretation:
    """What the photos (and the name/notes) say about the piece.

    ``support`` is meaningful for rectilinear pieces and for ``pie_central`` (a round top
    on a central pedestal); ``kind`` is a ``piece_kind`` value or None (no opinion);
    ``confidence`` is the confidence of the rectilinear decision in [0, 1] and
    ``support_confidence`` that of ``support`` (an unsure support is left None);
    ``reasons`` are short English sentences for the admin. ``top_shape`` is the shape of
    the top seen in the photo, ``base_ratio`` the pedestal's width / the top's width
    (``pie_central`` only) and ``photo_aspect`` the silhouette's width / height."""

    rectilinear: bool | None
    support: Support | None
    kind: str | None
    confidence: float
    reasons: list[str] = field(default_factory=list)
    top_shape: TopShape | None = None
    base_ratio: float | None = None
    photo_aspect: float | None = None
    support_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form, e.g. for ``piece_models.meta["interpretation"]``."""
        return asdict(self)


class Interpreter(Protocol):
    """Infers the optional form answers from the photos.

    TODO(vlm): a vision-model implementation (same signature) can replace
    :class:`SilhouetteInterpreter` once a key is available; ``merge_answers`` and
    ``check_dimensions`` stay."""

    def interpret(
        self,
        photos: list[Path],
        *,
        width_cm: float,
        height_cm: float,
        depth_cm: float,
        name: str = "",
        notes: str = "",
    ) -> Interpretation: ...


# --------------------------------------------------------------------------- text hints


@dataclass(frozen=True)
class TextHint:
    """A word in the name/notes: the kind it names and its rectilinear evidence in
    [-1, 1] (negative = organic)."""

    word: str
    kind: str
    evidence: float


# (accent-free stem or phrase, kind, evidence). Stems match at a word start ("sofas",
# "butacas", "chairs"); at the same position the longer phrase wins ("mesa de noche" is a
# mesita, "mesa" alone a mesa). Furniture with straight variants (chairs, stools, sofas)
# carries weaker organic evidence than vases and lamps; tables can be round, so "mesa" is a
# weak rectilinear hint while cabinets, shelves and headboards are strong ones.
TEXT_HINTS: tuple[tuple[str, str, float], ...] = (
    ("sofa", "sofa", -0.6),
    ("couch", "sofa", -0.6),
    ("sillon", "sillon", -0.8),
    ("butaca", "sillon", -0.8),
    ("armchair", "sillon", -0.8),
    ("silla", "silla", -0.5),
    ("chair", "silla", -0.5),
    ("taburete", "silla", -0.4),
    ("stool", "silla", -0.4),
    ("jarron", "jarron", -1.0),
    ("jarra", "jarron", -1.0),
    ("vase", "jarron", -1.0),
    ("lampara", "lampara", -1.0),
    ("lamp", "lampara", -1.0),
    ("cabecero", "cabecero", 1.0),
    ("headboard", "cabecero", 1.0),
    ("panel", "panel", 1.0),
    ("aparador", "aparador", 0.8),
    ("sideboard", "aparador", 0.8),
    ("comoda", "aparador", 0.8),
    ("dresser", "aparador", 0.8),
    ("cajonera", "aparador", 0.8),
    ("zapatero", "aparador", 0.8),
    ("shoe cabinet", "aparador", 0.8),
    ("credenza", "aparador", 0.8),
    ("mueble tv", "aparador", 0.8),
    ("estanteria", "estanteria", 0.8),
    ("estante", "estanteria", 0.8),
    ("libreria", "estanteria", 0.8),
    ("shelf", "estanteria", 0.8),
    ("shelving", "estanteria", 0.8),
    ("bookcase", "estanteria", 0.8),
    ("mesita", "mesita", 0.6),
    ("mesa de noche", "mesita", 0.6),
    ("mesa auxiliar", "mesita", 0.4),
    ("nightstand", "mesita", 0.6),
    ("bedside", "mesita", 0.6),
    ("side table", "mesita", 0.4),
    ("end table", "mesita", 0.4),
    ("mesa", "mesa", 0.4),
    ("table", "mesa", 0.4),
    ("escritorio", "mesa", 0.6),
    ("desk", "mesa", 0.6),
    ("consola", "mesa", 0.6),
    ("banco", "otro", 0.6),
    ("bench", "otro", 0.6),
    ("perchero", "otro", 0.0),
    ("coat rack", "otro", 0.0),
)
# Words that cancel a rectilinear hint ("mesa redonda", "round table", "curvado"): a round
# table may be organic or a buildable pedestal ("mesa redonda de pie central"), so the
# photo decides. Regexes after a word boundary: "redondeado"/"rounded" (rounded corners of
# a box) do not count.
ROUND_WORDS: tuple[str, ...] = (r"redond(?!e)", "ovalad", r"round(?!ed)", "oval", "curv")
ROUND_EVIDENCE = 0.0


def normalise(text: str) -> str:
    """Lowercase, accent-free text."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _first_hint(text: str) -> TextHint | None:
    norm = normalise(text)
    best: tuple[int, int, TextHint] | None = None  # (start, -len, hint)
    for word, kind, evidence in TEXT_HINTS:
        match = re.search(rf"\b{re.escape(word)}", norm)
        if match is None:
            continue
        key = (match.start(), -len(word))
        if best is None or key < best[:2]:
            best = (*key, TextHint(word, kind, evidence))
    return best[2] if best else None


def text_hint(name: str = "", notes: str = "") -> TextHint | None:
    """The earliest type word in the name, else in the notes (accent-insensitive, Spanish
    and English); a round/oval/curved word makes a rectilinear hint neutral."""
    for text in (name, notes):
        hint = _first_hint(text)
        if hint is None:
            continue
        norm = normalise(f"{name} {notes}")
        if hint.evidence > 0 and any(re.search(rf"\b{w}", norm) for w in ROUND_WORDS):
            return TextHint(hint.word, hint.kind, ROUND_EVIDENCE)
        return hint
    return None


# --------------------------------------------------------------------------- dimensions


def is_thin(width_cm: float, height_cm: float, depth_cm: float) -> bool:
    """Same rule as ``harness.variants.f_router.is_thin`` (headboards, panels)."""
    w, h, d = width_cm, height_cm, depth_cm
    if min(w, h, d) < THIN_MIN_CM:
        return True
    return w / d > THIN_MAX_RATIO or h / d > THIN_MAX_RATIO


def thin_kind(width_cm: float, height_cm: float) -> str:
    """A thin piece lower than it is wide is a headboard, otherwise a panel."""
    return "cabecero" if height_cm < width_cm else "panel"


# --------------------------------------------------------------------------- silhouette


class NoObject(ValueError):
    """The mask does not show a usable object (see :func:`prepare_mask`)."""


def prepare_mask(mask: np.ndarray | Image.Image, size: int = WORK_SIZE) -> np.ndarray:
    """Boolean mask cropped to its percentile bbox (as ``validate_input`` measures it) and
    resized so its long side is ``size`` px. Raises :class:`NoObject` (a ValueError) for
    a degenerate mask: empty, under 1 % or over 97 % of the frame, or a crop under 20 px a
    side.

    The percentile crop ignores stray rembg specks and drops the partial first/last rows
    of a slightly tilted edge, which :func:`cap_roundness` relies on (a tight crop made
    tilted box tops look rounded on the pilot photos). It also trims the thin tips of an
    elliptical top by a few %, so a pedestal's ``base_ratio`` reads slightly high (0.51 for
    the travertine fixture, 0.48 on its raw extents)."""
    arr = np.asarray(mask)
    if arr.ndim == 3:
        arr = arr[..., -1]
    arr = arr if arr.dtype == bool else arr > 0
    ys, xs = np.nonzero(arr)
    if xs.size == 0:
        raise NoObject("background removal found no object")
    frame_fill = xs.size / arr.size
    if frame_fill > MAX_FRAME_FILL:
        raise NoObject(f"the mask fills {frame_fill:.0%} of the photo (no background found)")
    if frame_fill < MIN_FRAME_FILL:
        raise NoObject(f"the object covers only {frame_fill:.1%} of the photo")
    x_lo, x_hi = np.percentile(xs, BBOX_PERCENTILES)
    y_lo, y_hi = np.percentile(ys, BBOX_PERCENTILES)
    crop = arr[int(y_lo) : int(math.ceil(y_hi)) + 1, int(x_lo) : int(math.ceil(x_hi)) + 1]
    h, w = crop.shape
    if min(h, w) < MIN_CROP_PX:
        raise NoObject(f"the object is only {w}×{h} px")
    scale = size / max(h, w)
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    img = Image.fromarray(crop.astype(np.uint8) * 255).resize(new_size, Image.Resampling.BOX)
    return np.asarray(img) >= 128


def _runs(line: np.ndarray) -> list[tuple[int, int]]:
    """``(start, end)`` (end exclusive) of the True runs of a 1-D boolean array."""
    padded = np.concatenate(([False], line, [False])).astype(np.int8)
    diff = np.diff(padded)
    starts, ends = np.flatnonzero(diff == 1), np.flatnonzero(diff == -1)
    return [(int(s), int(e)) for s, e in zip(starts, ends, strict=True)]


def _long_run_pixels(edges: np.ndarray, min_run: int, tol: int) -> int:
    """Edge pixels (rows of ``edges``) lying on runs ≥ ``min_run`` along axis 1, allowing
    ``tol`` px of drift across rows."""
    band = edges.copy()
    for k in range(1, tol + 1):
        band[k:] |= edges[:-k]
        band[:-k] |= edges[k:]
    keep = np.zeros_like(edges)
    for y in range(band.shape[0]):
        for start, end in _runs(band[y]):
            if end - start >= min_run:
                keep[y, start:end] = True
    return int((edges & keep).sum())


def straight_fraction(mask: np.ndarray) -> float:
    """Fraction of the outline on long near-horizontal/vertical straight runs."""
    padded = np.pad(mask, 1)
    h_edges = padded[1:, :] != padded[:-1, :]
    v_edges = padded[:, 1:] != padded[:, :-1]
    total = int(h_edges.sum() + v_edges.sum())
    if total == 0:
        return 0.0
    min_run = max(3, round(STRAIGHT_MIN_RUN * max(mask.shape)))
    tol = STRAIGHT_TOLERANCE_PX
    straight = _long_run_pixels(h_edges, min_run, tol) + _long_run_pixels(v_edges.T, min_run, tol)
    return straight / total


def _cross(o: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> int:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def hull_area(mask: np.ndarray) -> float:
    """Area of the convex hull of the mask's pixel squares (monotone chain)."""
    points: set[tuple[int, int]] = set()
    for y in range(mask.shape[0]):
        xs = np.flatnonzero(mask[y])
        if xs.size:
            x0, x1 = int(xs[0]), int(xs[-1]) + 1
            points.update({(x0, y), (x1, y), (x0, y + 1), (x1, y + 1)})
    pts = sorted(points)
    if len(pts) < 3:
        return 0.0
    lower: list[tuple[int, int]] = []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[int, int]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    closed = hull[1:] + hull[:1]
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(hull, closed, strict=True))
    return abs(area) / 2


def _outline(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Leftmost x and rightmost x + 1 of each non-empty row (rows top to bottom)."""
    left, right = [], []
    for y in range(mask.shape[0]):
        xs = np.flatnonzero(mask[y])
        if xs.size:
            left.append(xs[0])
            right.append(xs[-1] + 1)
    return np.asarray(left, dtype=float), np.asarray(right, dtype=float)


def _side_bulge(xs: np.ndarray, outward: int, width: int) -> float:
    """Outward bulge / horizontal extent of the outline ``xs`` (rows from the cap's tip)
    down to where it reaches its extreme (``outward`` −1 = leftmost, +1 = rightmost) within
    the upper half; 0 for a cap too small to judge."""
    half = xs[: max(len(xs) // 2, 1)]
    extreme = half.min() if outward < 0 else half.max()
    k = int(np.flatnonzero(np.abs(half - extreme) <= 1)[0])
    span = abs(xs[k] - xs[0])
    if k < CAP_MIN_ROWS or span < CAP_MIN_SPAN * width:
        return 0.0
    chord = xs[0] + (xs[k] - xs[0]) * np.arange(k + 1) / k
    bulge = (xs[: k + 1] - chord) * outward
    return float(bulge.max() / span)


def cap_roundness(mask: np.ndarray) -> tuple[float, float]:
    """``(top, bottom)`` roundness: the largest bulge ratio of the left/right outline of the
    top cap and of the bottom cap (see :data:`ROUND_THRESHOLD`)."""
    left, right = _outline(mask)
    if left.size < 2 * CAP_MIN_ROWS:
        return 0.0, 0.0
    w = mask.shape[1]
    top = max(_side_bulge(left, -1, w), _side_bulge(right, +1, w))
    bottom = max(_side_bulge(left[::-1], -1, w), _side_bulge(right[::-1], +1, w))
    return top, bottom


@dataclass(frozen=True)
class SilhouetteFeatures:
    extent: float  # mask area / bbox area
    solidity: float  # mask area / convex hull area
    straightness: float  # see straight_fraction
    top_roundness: float  # see cap_roundness
    bottom_roundness: float
    aspect: float  # bbox width / height

    @property
    def roundness(self) -> float:
        return max(self.top_roundness, self.bottom_roundness)

    @property
    def top_shape(self) -> TopShape:
        return "round" if self.top_roundness >= ROUND_THRESHOLD else "rect"

    def rectilinear_evidence(self) -> float:
        """Log-odds contribution of the photo: round caps push organic, a straight
        outline rectilinear."""
        caps = math.tanh((ROUND_THRESHOLD - self.roundness) / ROUND_SOFTNESS)
        return ROUND_WEIGHT * caps + STRAIGHT_WEIGHT * (self.straightness - 0.5)


def silhouette_features(mask: np.ndarray) -> SilhouetteFeatures:
    """Features of a :func:`prepare_mask` mask."""
    area = float(mask.sum())
    hull = hull_area(mask)
    top, bottom = cap_roundness(mask)
    return SilhouetteFeatures(
        extent=area / mask.size,
        solidity=area / hull if hull else 0.0,
        straightness=straight_fraction(mask),
        top_roundness=top,
        bottom_roundness=bottom,
        aspect=mask.shape[1] / mask.shape[0],
    )


@dataclass(frozen=True)
class SupportReading:
    support: Support | None
    confidence: float
    reason: str
    base_ratio: float | None = None  # pie_central: pedestal width / top width


def _merge_runs(runs: list[tuple[int, int]], gap: int, min_width: int) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in runs:
        if merged and start - merged[-1][1] < gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return [(s, e) for s, e in merged if e - s >= min_width]


def _top_row(rows: np.ndarray) -> tuple[int, int, float]:
    """``(index, span, filled fraction of the span)`` of the widest row (by span)."""
    best = (0, 0, 0.0)
    for y, row in enumerate(rows):
        xs = np.flatnonzero(row)
        if xs.size and int(xs[-1] - xs[0]) + 1 > best[1]:
            span = int(xs[-1] - xs[0]) + 1
            best = (y, span, xs.size / span)
    return best


def bottom_support(mask: np.ndarray) -> SupportReading:
    """How the piece stands, from the bottom band of a :func:`prepare_mask` mask.

    Body reaching the floor or continuous fill across ≥ 80 % of the width → box; one centred
    run narrower than 60 % of the top whose column rises to the top → central pedestal;
    outer runs with a wide, solid one and an empty centre → side panels; ≥ 2 narrow runs →
    legs; one wide recessed run (plinth) → box."""
    h, w = mask.shape
    fill = mask.sum(axis=1) / w
    floor = h - max(1, round(FLOOR_SKIP * h))
    widest = float(fill[:floor].max()) if floor > 0 else 0.0
    if widest == 0:
        return SupportReading(None, 0.0, "bottom band: empty mask")
    body_rows = np.flatnonzero(fill[:floor] >= BODY_ROW_FILL * widest)
    band_top = max(int(body_rows[-1]) + 1, h - round(BAND_MAX_FRACTION * h))
    if floor - band_top < BAND_MIN_ROWS:
        return SupportReading("caja", 0.8, "bottom band: the body reaches the floor → box")
    upper = band_top + max(BAND_MIN_ROWS, (floor - band_top) // 2)
    occupancy = mask[band_top:upper].mean(axis=0)
    runs = _merge_runs(
        _runs(occupancy >= COLUMN_OCCUPANCY),
        gap=max(1, round(RUN_MERGE_GAP * w)),
        min_width=max(1, round(RUN_MIN_WIDTH * w)),
    )
    if not runs:
        return SupportReading(None, 0.0, "bottom band: no support found")
    n = len(runs)
    coverage = sum(e - s for s, e in runs) / w
    max_gap = max((b[0] - a[1] for a, b in zip(runs[:-1], runs[1:], strict=True)), default=0) / w
    if coverage >= CONTINUOUS_COVERAGE and max_gap < CENTRE_GAP:
        return SupportReading("caja", 0.85, f"bottom band: continuous {coverage:.0%} → box")

    if n == 1:
        start, end = runs[0]
        top_row, top_width, top_solid = _top_row(mask[:band_top])
        ratio = (end - start) / top_width if top_width else 1.0
        centred = abs((start + end) / 2 - w / 2) <= PEDESTAL_CENTRE * w
        column = mask[:band_top, (start + end) // 2]
        rows = np.flatnonzero(column)
        rises = rows.size > 0 and column[rows[0] :].mean() >= PEDESTAL_COLUMN_FILL
        has_top = top_row <= PEDESTAL_TOP_ZONE * h and top_solid >= PEDESTAL_TOP_FILL
        if centred and ratio < PEDESTAL_MAX_RATIO and rises and has_top:
            return SupportReading(
                "pie_central",
                0.9,
                f"bottom band: one centred column {ratio:.0%} of the top → central pedestal",
                base_ratio=round(ratio, 3),
            )
        if coverage >= 0.5:
            return SupportReading("caja", 0.6, f"bottom band: recessed base {coverage:.0%} → box")
        return SupportReading("patas", 0.4, "bottom band: one narrow run → single leg?")

    def is_panel(run: tuple[int, int]) -> bool:
        s, e = run
        return (e - s) / w >= PANEL_MIN_WIDTH and occupancy[s:e].mean() >= PANEL_MIN_OCCUPANCY

    panels = [r for r in runs if is_panel(r)]
    at_extremes = runs[0][0] <= EXTREME_MARGIN * w and runs[-1][1] >= (1 - EXTREME_MARGIN) * w
    if panels and at_extremes and max_gap >= CENTRE_GAP:
        return SupportReading("paneles", 0.75, f"bottom band: {n} runs, {len(panels)} panels")
    if not any((e - s) / w >= PANEL_MIN_WIDTH for s, e in runs):
        return SupportReading("patas", 0.8, f"bottom band: {n} narrow runs → legs")
    return SupportReading(None, 0.3, f"bottom band: {n} runs, ambiguous")


# --------------------------------------------------------------------------- interpreter


def combine(
    *,
    features: SilhouetteFeatures | None,
    support: SupportReading | None,
    hint: TextHint | None,
    thin: bool,
    width_cm: float,
    height_cm: float,
) -> Interpretation:
    """Combine the evidence into an :class:`Interpretation` (pure; tested directly)."""
    reasons: list[str] = []
    z = 0.0
    pedestal = (
        support is not None
        and support.support == "pie_central"
        and support.confidence >= DEFAULT_MIN_CONFIDENCE
        and not thin
    )
    if pedestal:
        z += PEDESTAL_WEIGHT
        reasons.append("pedestal: top on one central column → buildable (parametric pedestal)")
    if features is not None:
        if not pedestal:
            z += features.rectilinear_evidence()
        reasons.append(
            f"silhouette: caps round {features.top_roundness:.2f} top / "
            f"{features.bottom_roundness:.2f} bottom (≥ {ROUND_THRESHOLD} = round), "
            f"straight outline {features.straightness:.0%}"
        )
    if thin:
        z += THIN_WEIGHT
        reasons.append("dimensions: thin piece → slab-like box")
    if hint is not None:
        z += TEXT_WEIGHT * hint.evidence
        reasons.append(f"text: «{hint.word}» → {hint.kind} ({hint.evidence:+.1f})")
    if features is None and hint is None and not thin:
        return Interpretation(None, None, None, 0.0, reasons or ["no evidence"])
    p = 1 / (1 + math.exp(-z / CONFIDENCE_TEMPERATURE))
    rectilinear = None if z == 0 else p >= 0.5  # neutral evidence only: no decision

    kind = hint.kind if hint is not None else None
    if thin and kind not in ("cabecero", "panel"):
        kind = thin_kind(width_cm, height_cm)

    chosen: Support | None = None
    support_confidence = 0.0
    base_ratio = None
    if thin:
        chosen, support_confidence = "caja", 0.9
    elif support is not None:
        reasons.append(support.reason)
        if support.confidence >= DEFAULT_MIN_CONFIDENCE:
            chosen, support_confidence = support.support, support.confidence
            base_ratio = support.base_ratio
    return Interpretation(
        rectilinear=rectilinear,
        support=chosen,
        kind=kind,
        confidence=round(max(p, 1 - p), 3),
        reasons=reasons,
        top_shape=features.top_shape if features is not None else None,
        base_ratio=base_ratio,
        photo_aspect=round(features.aspect, 3) if features is not None else None,
        support_confidence=support_confidence,
    )


Masker = Callable[[Path], np.ndarray]


def rembg_mask(path: Path) -> np.ndarray:
    """Object mask of a photo with the harness's background removal (rembg), on the
    EXIF-upright photo downscaled to ``REMBG_MAX_SIDE`` px on its long side."""
    from harness.prep.clean import _object_mask, _remove_background

    with Image.open(path) as img:
        rgb = ImageOps.exif_transpose(img).convert("RGB")
    rgb.thumbnail((REMBG_MAX_SIDE, REMBG_MAX_SIDE), Image.Resampling.LANCZOS)
    return np.asarray(_object_mask(_remove_background(rgb))) > 0


class SilhouetteInterpreter:
    """Default :class:`Interpreter`: silhouette of the first photo + dimensions + text."""

    def __init__(self, masker: Masker = rembg_mask) -> None:
        self._masker = masker

    def interpret(
        self,
        photos: list[Path],
        *,
        width_cm: float,
        height_cm: float,
        depth_cm: float,
        name: str = "",
        notes: str = "",
    ) -> Interpretation:
        features: SilhouetteFeatures | None = None
        support: SupportReading | None = None
        problem = "photo: none" if not photos else None
        if photos:
            # Any failure (rembg/onnx RuntimeError, DecompressionBombError, unreadable file,
            # degenerate mask) degrades to text + dimensions; it never fails the piece.
            try:
                mask = prepare_mask(self._masker(Path(photos[0])))
                features = silhouette_features(mask)
                support = bottom_support(mask)
            except NoObject as exc:
                problem = f"photo: no object ({exc}) → ignored"
            except Exception as exc:
                problem = f"photo: could not be analysed ({type(exc).__name__}: {exc}) → ignored"
        result = combine(
            features=features,
            support=support,
            hint=text_hint(name, notes),
            thin=is_thin(width_cm, height_cm, depth_cm),
            width_cm=width_cm,
            height_cm=height_cm,
        )
        if problem is None:
            return result
        return replace(result, reasons=[problem, *result.reasons])


# --------------------------------------------------------------------------- consistency


def _cm(value: float) -> str:
    return f"{value:g} cm"


def _about_cm(value: float) -> str:
    """Rounded for a customer: to 5 cm from 20 cm up, else to the centimetre."""
    rounded = 5 * round(value / 5) if value >= 20 else round(value)
    return f"~{rounded:g} cm"


def check_dimensions(
    interpretation_or_mask: Interpretation | np.ndarray | Image.Image,
    width_cm: float,
    height_cm: float,
    depth_cm: float,
) -> list[str]:
    """Customer-facing (English) warnings when the photo and the dimensions disagree.

    - Proportions: the silhouette's width/height must fall within ±30 % of the range a
      front-to-three-quarter view of a ``width × height × depth`` piece can show: from
      ``width / (height + 0.35 · depth)`` (seen slightly from above) to
      ``hypot(width, depth) / height`` (seen at an angle). The warning trusts the width
      and names the height the photo implies at the nearest end of that range.
    - A round top whose width/depth ratio is outside 0.75–1.33, only for a table-like piece
      (central pedestal, or kind mesa/mesita): round-ended sideboards and arched coat racks
      also have round caps.

    Empty when there is nothing to compare: a degenerate mask, an interpretation without a
    silhouette, or a non-positive dimension."""
    if min(width_cm, height_cm, depth_cm) <= 0:
        return []
    if isinstance(interpretation_or_mask, Interpretation):
        aspect = interpretation_or_mask.photo_aspect
        top_shape = interpretation_or_mask.top_shape
        table_like = (
            interpretation_or_mask.support == "pie_central"
            or interpretation_or_mask.kind in TABLE_KINDS
        )
    else:
        try:
            mask = prepare_mask(interpretation_or_mask)
        except ValueError:
            return []
        features = silhouette_features(mask)
        aspect, top_shape = features.aspect, features.top_shape
        table_like = bottom_support(mask).support == "pie_central"
    warnings: list[str] = []
    if aspect:
        low = width_cm / (height_cm + ELEVATION_DEPTH_SHARE * depth_cm)
        high = math.hypot(width_cm, depth_cm) / height_cm
        implied = None
        if aspect < low / (1 + ASPECT_TOLERANCE):  # taller in the photo than entered
            implied = width_cm / aspect - ELEVATION_DEPTH_SHARE * depth_cm
        elif aspect > high * (1 + ASPECT_TOLERANCE):  # wider in the photo than entered
            implied = math.hypot(width_cm, depth_cm) / aspect
        if implied is not None:
            warnings.append(
                f"From the photo, the height looks closer to {_about_cm(implied)} than "
                f"{_cm(height_cm)}. Please check the height (and the width, {_cm(width_cm)})."
            )
    ratio = width_cm / depth_cm
    if (
        top_shape == "round"
        and table_like
        and not ROUND_TOP_RATIO[0] <= ratio <= ROUND_TOP_RATIO[1]
    ):
        warnings.append(
            "If the top is round, width and depth are usually similar — is the depth really "
            f"{_cm(depth_cm)}? (Ignore this if it is oval.)"
        )
    return warnings


# --------------------------------------------------------------------------- merge


def _pedestal_params(inferred: Interpretation, customer: dict[str, Any]) -> dict[str, Any]:
    """E ``pedestal`` params: ``base_diameter_ratio`` is relative to min(width, depth), the
    silhouette's ``base_ratio`` to the top's width as seen (≈ width), so it is rescaled
    when the dimensions are known and clamped to E's range; ``top_shape`` is "oval" when
    width and depth differ by more than 2 %."""
    ratio = inferred.base_ratio
    w, d = customer.get("width_cm"), customer.get("depth_cm")
    top_shape = "round"
    if w and d and float(w) > 0 and float(d) > 0:
        w, d = float(w), float(d)
        if ratio is not None:
            ratio = ratio * w / min(w, d)
        if abs(w - d) / max(w, d) > PEDESTAL_ROUND_TOLERANCE:
            top_shape = "oval"
    if ratio is not None:
        ratio = round(min(max(ratio, PEDESTAL_BASE_RANGE[0]), PEDESTAL_BASE_RANGE[1]), 3)
    return {"base_diameter_ratio": ratio, "top_shape": top_shape}


def merge_answers(
    customer: dict[str, Any],
    inferred: Interpretation,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    conflict_confidence: float = CONFLICT_CONFIDENCE,
) -> dict[str, Any]:
    """Effective answers of a piece and the parametric route they imply.

    Returns ``{"kind", "rectilinear", "support", "source", "conflict", "routing_kind",
    "pedestal_params"}``.

    ``customer`` holds the answers stored on the piece (defaults: kind "otro", rectilinear
    None, support "no_se"); it may also carry ``notes``, ``width_cm`` and ``depth_cm``.
    Precedence per field: an explicit customer answer, then the inferred value when its
    confidence ≥ ``min_confidence`` (``confidence`` for kind and rectilinear,
    ``support_confidence`` for support), then the default (kind "otro", rectilinear None so
    the kind-based heuristic downstream decides, support "no_se"). ``source`` maps each
    field to "customer", "inferred" or "default". "otro" cannot be told from the default,
    so it never overrides an inferred kind; a customer support outside patas/paneles/caja
    counts as unanswered.

    ``support`` is always a ``pieces.support`` value (patas|paneles|caja|no_se): an inferred
    central pedestal is not one, so it only shows in ``routing_kind`` = "pedestal" with
    ``pedestal_params`` ``{"base_diameter_ratio", "top_shape"}`` (else None). Inferred
    support is only used when the piece is not organic.

    ``routing_kind`` (route E's parametric kind, or None for its own heuristic / the
    organic route): pedestal as above; patas → "table", paneles → "panel_table", caja →
    "box", or "box_legs" when the notes say «patas»/«zócalo»; no support on a headboard or
    panel → "box". None when the piece is not rectilinear.

    ``conflict`` lists ``{"field", "customer", "inferred", "confidence"}`` for explicit
    customer answers that the photo contradicts with confidence ≥ ``conflict_confidence``
    (support only while the piece is not organic): the customer's value is kept, and the
    worker should send the piece to manual review instead of trusting it."""
    trusted = inferred.confidence >= min_confidence
    source: dict[str, str] = {}
    conflict: list[dict[str, Any]] = []

    kind = customer.get("kind")
    if kind and kind != DEFAULT_KIND:
        source["kind"] = "customer"
    elif trusted and inferred.kind:
        kind, source["kind"] = inferred.kind, "inferred"
    else:
        kind, source["kind"] = DEFAULT_KIND, "default"

    rectilinear = customer.get("rectilinear")
    if rectilinear is not None:
        rectilinear, source["rectilinear"] = bool(rectilinear), "customer"
        if (
            inferred.rectilinear is not None
            and inferred.rectilinear != rectilinear
            and inferred.confidence >= conflict_confidence
        ):
            conflict.append(
                {
                    "field": "rectilinear",
                    "customer": rectilinear,
                    "inferred": inferred.rectilinear,
                    "confidence": inferred.confidence,
                }
            )
    elif trusted and inferred.rectilinear is not None:
        rectilinear, source["rectilinear"] = inferred.rectilinear, "inferred"
    else:
        rectilinear, source["rectilinear"] = None, "default"

    support = customer.get("support")
    confident_support = inferred.support if inferred.support_confidence >= min_confidence else None
    pedestal = False
    if support in CUSTOMER_SUPPORTS:
        source["support"] = "customer"
        if (
            rectilinear is not False
            and inferred.support is not None
            and inferred.support != support
            and inferred.support_confidence >= conflict_confidence
        ):
            conflict.append(
                {
                    "field": "support",
                    "customer": support,
                    "inferred": inferred.support,
                    "confidence": inferred.support_confidence,
                }
            )
    else:
        support, source["support"] = DEFAULT_SUPPORT, "default"
        if confident_support and rectilinear is not False:
            if confident_support == "pie_central":
                pedestal = True
            elif confident_support in DB_SUPPORTS:
                support, source["support"] = confident_support, "inferred"

    routing_kind: RoutingKind | None = None
    if rectilinear is not False:
        if pedestal:
            routing_kind = "pedestal"
        elif support in SUPPORT_ROUTING:
            routing_kind = SUPPORT_ROUTING[support]
        elif support == "caja":
            notes = normalise(str(customer.get("notes") or ""))
            routing_kind = "box_legs" if BASE_WORDS.search(notes) else "box"
        elif kind in BOX_KINDS:
            routing_kind = "box"

    return {
        "kind": kind,
        "rectilinear": rectilinear,
        "support": support,
        "source": source,
        "conflict": conflict,
        "routing_kind": routing_kind,
        "pedestal_params": _pedestal_params(inferred, customer) if pedestal else None,
    }
