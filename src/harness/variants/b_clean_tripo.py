"""Variant B: clean_image on every photo -> multiview_to_model (>= 2 photos) or
image_to_model (1 photo), one seed per candidate."""

from __future__ import annotations

import time
from pathlib import Path

from harness.clients.tripo import TripoClient
from harness.core.config import Settings
from harness.core.models import Piece, VariantResult
from harness.prep import clean
from harness.variants.a_tripo_direct import (
    DEFAULT_BASE_SEED,
    resolve_client,
    run_tripo_candidates,
)

CLEAN_DIRNAME = "clean"
CLEAN_SIZE = 1024


class CleanTripoVariant:
    name = "B"

    def __init__(
        self,
        client: TripoClient | None = None,
        *,
        settings: Settings | None = None,
        base_seed: int = DEFAULT_BASE_SEED,
    ) -> None:
        self._client = client
        self._settings = settings
        self.base_seed = base_seed

    @property
    def client(self) -> TripoClient:
        self._client = resolve_client(self._client, self._settings)
        return self._client

    def prepare(self, piece: Piece, workdir: Path) -> tuple[list[Path], list[str]]:
        """Clean every photo into ``workdir/clean``; photos with no detectable object are
        skipped (reported as warnings). Raises ``ValueError`` if none survives."""
        out_dir = Path(workdir) / CLEAN_DIRNAME
        cleaned: list[Path] = []
        skipped: list[str] = []
        for k, src in enumerate(piece.images, start=1):
            dst = out_dir / f"{k:02d}_{Path(src).stem}.png"
            try:
                cleaned.append(clean.clean_image(src, dst, size=CLEAN_SIZE))
            except ValueError as exc:
                skipped.append(str(exc))
        if not cleaned:
            raise ValueError(f"Ninguna foto de {piece.id} es utilizable tras limpiar: {skipped}")
        return cleaned, skipped

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        workdir = Path(workdir)
        start = time.monotonic()
        images, skipped = self.prepare(piece, workdir)
        clean_s = time.monotonic() - start
        result = run_tripo_candidates(
            variant=self.name,
            client=self.client,
            piece=piece,
            workdir=workdir,
            images=images,
            candidates=candidates,
            base_seed=self.base_seed,
            extra_meta={
                "clean_images": [str(p) for p in images],
                "clean_skipped": skipped,
                "clean_seconds": clean_s,
            },
            # Cleaning is shared by all candidates: each one carries its share.
            extra_seconds=clean_s / max(candidates, 1),
        )
        if skipped:
            note = "fotos descartadas al limpiar: " + "; ".join(skipped)
            result.notes = "; ".join(filter(None, [result.notes, note]))
        return result
