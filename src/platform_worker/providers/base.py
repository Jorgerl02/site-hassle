"""Provider contract for organic pieces: same signature as the harness API clients."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from harness.clients.tripo import GenerationOutcome

__all__ = ["GenerationOutcome", "Provider", "ProviderError"]


class ProviderError(RuntimeError):
    """The provider failed to produce a GLB."""


@runtime_checkable
class Provider(Protocol):
    name: str

    def generate(
        self, images: list[Path], dst_glb: Path, *, seed: int | None = None
    ) -> GenerationOutcome: ...
