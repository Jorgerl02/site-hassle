"""Providers for organic pieces: ``fake`` (fixture GLB), ``tripo`` and ``fal``."""

from __future__ import annotations

import os

from platform_worker.providers.base import GenerationOutcome, Provider, ProviderError
from platform_worker.providers.fake import FakeProvider

PROVIDERS: tuple[str, ...] = ("fake", "tripo", "fal")

__all__ = ["PROVIDERS", "FakeProvider", "GenerationOutcome", "Provider", "ProviderError", "make"]


def make(name: str | None, env: dict[str, str | None] | None = None) -> Provider | None:
    """Build the provider ``name`` (``None``/empty → no provider: organic pieces fail with a
    clear message). Keys come from ``env`` (default: the process environment)."""
    env = dict(os.environ) if env is None else env
    if not name:
        return None
    if name == "fake":
        return FakeProvider()
    if name == "tripo":
        from platform_worker.providers.tripo import TripoProvider

        key = env.get("TRIPO_API_KEY")
        if not key:
            raise ValueError("PROVIDER=tripo necesita TRIPO_API_KEY en .env")
        return TripoProvider(key)
    if name == "fal":
        from platform_worker.providers.fal import FalProvider

        key = env.get("FAL_KEY")
        if not key:
            raise ValueError("PROVIDER=fal necesita FAL_KEY en .env")
        return FalProvider(key, model=env.get("FAL_MODEL") or "trellis")
    raise ValueError(f"Proveedor desconocido {name!r} (válidos: {', '.join(PROVIDERS)})")
