"""Tripo provider: reuses ``harness.clients.tripo.TripoClient`` with ``TripoSettings``
(defaults = the Pietra settings, overridable with ``TRIPO_*`` env vars)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from harness.clients.tripo import TripoClient, TripoSettings
from platform_worker.providers.base import GenerationOutcome


class TripoProvider:
    name = "tripo"

    def __init__(
        self,
        api_key: str,
        *,
        settings: TripoSettings | None = None,
        env: Mapping[str, str | None] | None = None,
        client: TripoClient | None = None,
    ) -> None:
        """``settings`` wins; else ``TripoSettings.from_env(env)`` (``env`` defaults to the
        process environment)."""
        if client is None:
            settings = settings if settings is not None else TripoSettings.from_env(env)
            client = TripoClient(api_key, settings=settings)
        self._client = client

    @property
    def settings(self) -> TripoSettings:
        return self._client.settings

    def generate(
        self, images: list[Path], dst_glb: Path, *, seed: int | None = None
    ) -> GenerationOutcome:
        # Customer photos carry no view labels and Tripo multiview needs them, so the client
        # sends only the first photo (image-to-model) and records the rest as ignored.
        return self._client.generate(list(images), dst_glb, seed=seed)
