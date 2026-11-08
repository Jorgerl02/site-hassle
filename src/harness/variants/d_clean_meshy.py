"""Variant D: clean every photo (rembg, crop, square on white) → Meshy.

≥2 photos use Meshy multi-image-to-3d (up to 4); 1 photo uses image-to-3d.
Meshy has no documented seed, so candidates are independent re-runs of the same request.
"""

from __future__ import annotations

from pathlib import Path

from harness.clients.meshy import MeshyClient
from harness.core import storage
from harness.core.config import Settings
from harness.core.models import Candidate, Piece, VariantResult
from harness.prep.clean import clean_image

CLEAN_DIRNAME = "clean"


class CleanMeshyVariant:
    name = "D"

    def __init__(self, client: MeshyClient | None = None, settings: Settings | None = None) -> None:
        self._client = client
        self._settings = settings

    @property
    def client(self) -> MeshyClient:
        # Built lazily so the registry can list the variant without a key.
        if self._client is None:
            settings = self._settings or Settings.load()
            if not settings.meshy_api_key:
                raise RuntimeError("Variante D: falta MESHY_API_KEY en .env o en el entorno")
            self._client = MeshyClient(settings.meshy_api_key)
        return self._client

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        workdir = Path(workdir)
        clean_dir = workdir / CLEAN_DIRNAME
        cleaned = [
            clean_image(src, clean_dir / f"{i}.png") for i, src in enumerate(piece.images, start=1)
        ]

        result: list[Candidate] = []
        for index in range(1, candidates + 1):
            cand = storage.candidate_dir(workdir, index)
            outcome = self.client.generate(cleaned, storage.model_path(cand), seed=index)
            meta = {
                "variant": self.name,
                "piece_id": piece.id,
                "index": index,
                "source_images": [str(p) for p in piece.images],
                "clean_images": [str(p) for p in cleaned],
                "cost_usd": outcome.cost_usd,
                "seconds": outcome.seconds,
                **outcome.meta,
            }
            storage.write_meta(cand, meta)
            result.append(
                Candidate(
                    index=index,
                    glb_path=outcome.glb_path,
                    cost_usd=outcome.cost_usd,
                    seconds=outcome.seconds,
                    meta=meta,
                )
            )

        mode = "multi-imagen" if len(cleaned) >= 2 else "imagen única"
        notes = (
            f"clean_image en {len(cleaned)} foto(s) → Meshy {mode}; "
            "Meshy no admite semilla: candidatos = repeticiones independientes"
        )
        return VariantResult(variant=self.name, piece_id=piece.id, candidates=result, notes=notes)
