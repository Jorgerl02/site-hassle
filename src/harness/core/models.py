"""Data models shared by every task of the harness (frozen public API)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

Category = Literal["macizo_mate", "tapizado", "metal_vidrio", "patas_finas"]
CATEGORIES: tuple[str, ...] = ("macizo_mate", "tapizado", "metal_vidrio", "patas_finas")

DEFAULT_SAMPLE_CSV = Path("data/sample.csv")
MAX_PIECES = 30
SCALE_TOLERANCE = 0.03  # spec: bounding-box error < 3 % per axis

CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "name",
    "store",
    "source_url",
    "category",
    "images",
    "width_cm",
    "height_cm",
    "depth_cm",
    "description",
    "rectilinear",
)


class Piece(BaseModel):
    """One furniture piece of the fixed sample."""

    id: str = Field(min_length=1)
    name: str
    store: str
    source_url: str
    category: Category
    images: list[Path] = Field(min_length=1)
    width_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    depth_cm: float = Field(gt=0)
    description: str = ""
    rectilinear: bool | None = None


class Candidate(BaseModel):
    """One generated 3D model for a piece by a variant."""

    index: int
    glb_path: Path
    cost_usd: float = 0.0
    seconds: float = 0.0
    meta: dict[str, Any] = Field(default_factory=dict)


class VariantResult(BaseModel):
    variant: str
    piece_id: str
    candidates: list[Candidate]
    notes: str = ""


class Scores(BaseModel):
    """Rubric scores (1–5) for a candidate; ``apt`` = all four axes >= 4."""

    parecido: int = Field(ge=1, le=5)
    geometria: int = Field(ge=1, le=5)
    materiales: int = Field(ge=1, le=5)
    escala: int = Field(ge=1, le=5)
    apt: bool
    comentario: str = ""


class GeometryMetrics(BaseModel):
    """Measured bounding box (cm) and relative error vs the piece's catalogue dimensions."""

    width_cm: float
    height_cm: float
    depth_cm: float
    err_width: float
    err_height: float
    err_depth: float
    watertight: bool
    n_components: int
    n_faces: int

    @property
    def max_error(self) -> float:
        return max(self.err_width, self.err_height, self.err_depth)

    @property
    def scale_ok(self) -> bool:
        return self.max_error < SCALE_TOLERANCE


def _parse_rectilinear(raw: str) -> bool | None:
    value = raw.strip().lower()
    if value == "":
        return None
    if value in ("true", "false"):
        return value == "true"
    raise ValueError(f"rectilinear debe ser true, false o vacío; recibido {raw!r}")


def _parse_images(raw: str, root: Path) -> list[Path]:
    paths = [Path(p.strip()) for p in raw.split(";") if p.strip()]
    return [p if p.is_absolute() else root / p for p in paths]


def load_pieces(csv_path: Path = DEFAULT_SAMPLE_CSV, root: Path | None = None) -> list[Piece]:
    """Load and validate the sample CSV.

    Relative image paths are resolved against ``root`` (default: current directory, i.e. the
    repo root when run via ``uv run``). Raises ``ValueError`` with the offending row number.
    """
    root = root if root is not None else Path.cwd()
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{csv_path}: faltan columnas {missing}")
        rows = list(reader)

    if len(rows) > MAX_PIECES:
        raise ValueError(f"{csv_path}: {len(rows)} filas; el máximo es {MAX_PIECES}")

    pieces: list[Piece] = []
    seen: set[str] = set()
    for line_no, row in enumerate(rows, start=2):  # line 1 is the header
        try:
            piece = Piece(
                id=row["id"].strip(),
                name=row["name"].strip(),
                store=row["store"].strip(),
                source_url=row["source_url"].strip(),
                category=row["category"].strip(),
                images=_parse_images(row["images"], root),
                width_cm=row["width_cm"],
                height_cm=row["height_cm"],
                depth_cm=row["depth_cm"],
                description=row["description"].strip(),
                rectilinear=_parse_rectilinear(row["rectilinear"]),
            )
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"{csv_path}, línea {line_no}: {exc}") from exc
        if piece.id in seen:
            raise ValueError(f"{csv_path}, línea {line_no}: id duplicado {piece.id!r}")
        seen.add(piece.id)
        pieces.append(piece)
    return pieces
