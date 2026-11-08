"""Variant A (baseline): first photo as-is -> Tripo image_to_model, one seed per candidate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.clients.tripo import TripoClient, TripoError
from harness.core import storage
from harness.core.config import MissingKeyError, Settings
from harness.core.models import Candidate, Piece, VariantResult

DEFAULT_BASE_SEED = 1000


def resolve_client(client: TripoClient | None, settings: Settings | None) -> TripoClient:
    """Return ``client`` or build one from ``settings`` (or ``.env``) lazily."""
    if client is not None:
        return client
    settings = settings or Settings.load()
    if not settings.tripo_api_key:
        raise MissingKeyError("Falta TRIPO_API_KEY en el entorno o en .env")
    return TripoClient(settings.tripo_api_key)


def run_tripo_candidates(
    *,
    variant: str,
    client: TripoClient,
    piece: Piece,
    workdir: Path,
    images: list[Path],
    candidates: int,
    base_seed: int,
    extra_meta: dict[str, Any] | None = None,
    extra_seconds: float = 0.0,
) -> VariantResult:
    """Generate ``candidates`` GLBs with seed = ``base_seed + index`` and write each
    candidate's ``meta.json``. A failed candidate is recorded in its meta and in ``notes``;
    if every candidate fails the last ``TripoError`` is raised."""
    results: list[Candidate] = []
    failures: list[str] = []
    last_error: TripoError | None = None
    for index in range(1, candidates + 1):
        cand_dir = storage.candidate_dir(workdir, index)
        seed = base_seed + index
        base = {
            "variant": variant,
            "piece_id": piece.id,
            "index": index,
            "seed": seed,
            **(extra_meta or {}),
        }
        try:
            outcome = client.generate(images, storage.model_path(cand_dir), seed=seed)
        except TripoError as exc:
            last_error = exc
            failures.append(f"cand_{index}: {exc}")
            storage.write_meta(cand_dir, {**base, "error": str(exc), "error_payload": exc.payload})
            continue
        meta = {**base, **outcome.meta}
        storage.write_meta(cand_dir, meta)
        results.append(
            Candidate(
                index=index,
                glb_path=outcome.glb_path,
                cost_usd=outcome.cost_usd,
                seconds=outcome.seconds + extra_seconds,
                meta=meta,
            )
        )
    if not results and last_error is not None:
        raise last_error
    notes = "; ".join(failures)
    return VariantResult(variant=variant, piece_id=piece.id, candidates=results, notes=notes)


class TripoDirectVariant:
    """A: ``piece.images[0]`` unchanged -> image_to_model, N seeds."""

    name = "A"

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

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        return run_tripo_candidates(
            variant=self.name,
            client=self.client,
            piece=piece,
            workdir=Path(workdir),
            images=[piece.images[0]],
            candidates=candidates,
            base_seed=self.base_seed,
        )
