"""Tripo provider: reuses ``harness.clients.tripo.TripoClient`` (cost from ``pricing``)."""

from __future__ import annotations

from pathlib import Path

from harness.clients.tripo import TripoClient
from platform_worker.providers.base import GenerationOutcome


class TripoProvider:
    name = "tripo"

    def __init__(self, api_key: str, *, client: TripoClient | None = None) -> None:
        self._client = client or TripoClient(api_key)

    def generate(
        self, images: list[Path], dst_glb: Path, *, seed: int | None = None
    ) -> GenerationOutcome:
        # Customer photos carry no view labels: single-image generation (as variant B).
        return self._client.generate(list(images)[:1], dst_glb, seed=seed)
