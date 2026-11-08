"""Variant interface (frozen) and a fake variant for tests and integration."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

import trimesh

from harness.core import storage
from harness.core.models import Candidate, Piece, VariantResult


@runtime_checkable
class Variant(Protocol):
    name: str  # "A", "B", "C", "D", "E", "F"

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult: ...


class FakeVariant:
    """Writes ``candidates`` GLBs without any external call (cost 0).

    If ``source_glb`` is given it is copied; otherwise a box with the piece's
    dimensions (metres, glTF convention) is exported with trimesh.
    """

    def __init__(self, name: str = "FAKE", source_glb: Path | None = None) -> None:
        self.name = name
        self.source_glb = source_glb

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        result: list[Candidate] = []
        for index in range(1, candidates + 1):
            start = time.monotonic()
            glb = storage.model_path(storage.candidate_dir(workdir, index))
            if self.source_glb is not None:
                shutil.copyfile(self.source_glb, glb)
            else:
                extents = (piece.width_cm / 100, piece.height_cm / 100, piece.depth_cm / 100)
                trimesh.creation.box(extents=extents).export(glb)
            result.append(
                Candidate(
                    index=index,
                    glb_path=glb,
                    cost_usd=0.0,
                    seconds=time.monotonic() - start,
                    meta={"fake": True, "source_glb": str(self.source_glb or "")},
                )
            )
        return VariantResult(variant=self.name, piece_id=piece.id, candidates=result)
