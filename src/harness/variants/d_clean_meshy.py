"""Variant D: clean every photo (rembg, crop, square on white) → Meshy.

≥2 photos use Meshy multi-image-to-3d (up to 4); 1 photo uses image-to-3d.
Meshy has no documented seed, so candidates are independent re-runs of the same request.
"""

from __future__ import annotations

from pathlib import Path

from harness.clients.meshy import MeshyClient
from harness.core import storage
from harness.core.config import MissingKeyError, Settings
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
                raise MissingKeyError("Variante D: falta MESHY_API_KEY en .env o en el entorno")
            self._client = MeshyClient(settings.meshy_api_key)
        return self._client

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        workdir = Path(workdir)
        clean_dir = workdir / CLEAN_DIRNAME
        cleaned = [
            clean_image(src, clean_dir / f"{i}.png") for i, src in enumerate(piece.images, start=1)
        ]

        client = self.client  # resolved before the loop: a missing key is not a candidate failure
        base_meta = {
            "variant": self.name,
            "piece_id": piece.id,
            "source_images": [str(p) for p in piece.images],
            "clean_images": [str(p) for p in cleaned],
        }
        result: list[Candidate] = []
        failures: list[str] = []
        last_error: Exception | None = None
        for index in range(1, candidates + 1):
            cand = storage.candidate_dir(workdir, index)
            try:
                outcome = client.generate(cleaned, storage.model_path(cand), seed=index)
            except Exception as exc:  # one failed candidate must not drop the paid ones
                last_error = exc
                failures.append(f"cand_{index}: {exc}")
                storage.write_meta(
                    cand,
                    {
                        **base_meta,
                        "index": index,
                        "error": str(exc),
                        "error_payload": getattr(exc, "payload", None),
                        "cost_usd": 0.0,  # nothing billed is known for a failed Meshy task
                        "seconds": 0.0,
                    },
                )
                continue
            meta = {
                **base_meta,
                "index": index,
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
        if not result and last_error is not None:
            raise last_error

        mode = "multi-imagen" if len(cleaned) >= 2 else "imagen única"
        notes = (
            f"clean_image en {len(cleaned)} foto(s) → Meshy {mode}; "
            "Meshy no admite semilla: candidatos = repeticiones independientes"
        )
        if failures:
            notes += "; candidatos fallidos: " + "; ".join(failures)
        return VariantResult(variant=self.name, piece_id=piece.id, candidates=result, notes=notes)
