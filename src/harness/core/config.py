"""Settings loaded from ``.env`` plus the process environment (environment wins)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field

from harness.core.models import SCALE_TOLERANCE

DEFAULT_ENV_FILE = Path(".env")
_UNSET = object()


class MissingKeyError(RuntimeError):
    """A required API key is not configured (infrastructure, not the candidate's fault)."""


class Settings(BaseModel):
    tripo_api_key: str | None = None
    meshy_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    blender_bin: Path | None = None
    # Relative bounding-box tolerance per axis sold to the client (0.03 = 3 %).
    scale_tolerance: float = Field(default=SCALE_TOLERANCE, gt=0, lt=1)

    @classmethod
    def load(cls, env_file: Path | None | object = _UNSET) -> Settings:
        if env_file is _UNSET:
            env_file = DEFAULT_ENV_FILE  # resolved at call time so tests can redirect it
        values: dict[str, str | None] = {}
        if env_file is not None and Path(env_file).exists():
            values.update(dotenv_values(env_file))
        values.update(os.environ)

        def get(key: str) -> str | None:
            value = (values.get(key) or "").strip()
            return value or None

        blender = get("BLENDER_BIN")
        return cls(
            scale_tolerance=_parse_tolerance(get("SCALE_TOLERANCE")),
            tripo_api_key=get("TRIPO_API_KEY"),
            meshy_api_key=get("MESHY_API_KEY"),
            anthropic_api_key=get("ANTHROPIC_API_KEY"),
            gemini_api_key=get("GEMINI_API_KEY"),
            blender_bin=Path(blender) if blender else None,
        )


def _parse_tolerance(raw: str | None) -> float:
    """``SCALE_TOLERANCE`` as a fraction in (0, 1); empty or unset → ``SCALE_TOLERANCE``."""
    if raw is None:
        return SCALE_TOLERANCE
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        value = float("nan")
    if not 0 < value < 1:
        raise ValueError(
            f"SCALE_TOLERANCE debe ser una fracción entre 0 y 1 (p. ej. 0.03 = 3 %); "
            f"recibido {raw!r}"
        )
    return value


def resolve_scale_tolerance(tolerance: float | None = None) -> float:
    """``tolerance`` if given, else ``Settings.load().scale_tolerance`` (read at call time)."""
    if tolerance is None:
        return Settings.load().scale_tolerance
    if not 0 < tolerance < 1:
        raise ValueError(f"La tolerancia debe estar entre 0 y 1; recibido {tolerance!r}")
    return float(tolerance)
