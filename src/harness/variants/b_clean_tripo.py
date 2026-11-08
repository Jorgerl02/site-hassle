"""Variant B: clean_image on the FIRST photo -> Tripo image_to_model, one seed per candidate.

Never multiview: catalogue photos carry no view labels (``data/SAMPLE_README.md``), and
Tripo's multiview slots are fixed (front, left, back, right), so sending them would put
arbitrary photos in the wrong slots. Multiview stays exclusive to C, whose synthetic views
are labelled. B therefore isolates the effect of cleaning against A (same photo, raw).
"""

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

    def prepare(self, piece: Piece, workdir: Path) -> Path:
        """Clean ``piece.images[0]`` into ``workdir/clean``.

        Raises ``ValueError`` if no object is detected in it (a candidate failure).
        """
        src = Path(piece.images[0])
        dst = Path(workdir) / CLEAN_DIRNAME / f"01_{src.stem}.png"
        return clean.clean_image(src, dst, size=CLEAN_SIZE)

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        workdir = Path(workdir)
        start = time.monotonic()
        image = self.prepare(piece, workdir)
        clean_s = time.monotonic() - start
        return run_tripo_candidates(
            variant=self.name,
            client=self.client,
            piece=piece,
            workdir=workdir,
            images=[image],
            candidates=candidates,
            base_seed=self.base_seed,
            extra_meta={
                "source_image": str(piece.images[0]),
                "clean_images": [str(image)],
                "clean_seconds": clean_s,
            },
            # Cleaning is shared by all candidates: each one carries its share.
            extra_seconds=clean_s / max(candidates, 1),
        )
