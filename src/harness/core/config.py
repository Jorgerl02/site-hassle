"""Settings loaded from ``.env`` plus the process environment (environment wins)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel

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
            tripo_api_key=get("TRIPO_API_KEY"),
            meshy_api_key=get("MESHY_API_KEY"),
            anthropic_api_key=get("ANTHROPIC_API_KEY"),
            gemini_api_key=get("GEMINI_API_KEY"),
            blender_bin=Path(blender) if blender else None,
        )
