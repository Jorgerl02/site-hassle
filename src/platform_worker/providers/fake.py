"""Offline provider for development: copies a fixture GLB (no network, cost 0)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from platform_worker.providers.base import GenerationOutcome

DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "platform" / "sample.glb"
)


class FakeProvider:
    name = "fake"

    def __init__(self, fixture: Path | None = None) -> None:
        self.fixture = Path(fixture) if fixture is not None else DEFAULT_FIXTURE

    def generate(
        self, images: list[Path], dst_glb: Path, *, seed: int | None = None
    ) -> GenerationOutcome:
        if not self.fixture.is_file():
            raise FileNotFoundError(f"No existe el GLB de prueba: {self.fixture}")
        start = time.monotonic()
        dst_glb = Path(dst_glb)
        dst_glb.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.fixture, dst_glb)
        return GenerationOutcome(
            glb_path=dst_glb,
            cost_usd=0.0,
            seconds=time.monotonic() - start,
            meta={"provider": self.name, "fixture": str(self.fixture), "seed": seed},
        )
