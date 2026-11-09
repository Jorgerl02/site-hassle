"""Worker settings: the process environment over a ``.env`` file, resolved at call time.

The file is ``WORKER_ENV_FILE`` when set, else ``harness.core.config.DEFAULT_ENV_FILE``
(``.env``), so the redirection the test suite applies to the harness also isolates the
worker from the repo's real ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

from harness.core import config as harness_config

WORKER_KEYS: tuple[str, ...] = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "PROVIDER",
    "TRIPO_API_KEY",
    "FAL_KEY",
    "FAL_MODEL",
    "BLENDER_BIN",
    "NOTIFY_URL",
    "WORKER_SHARED_SECRET",
    "WORKER_DAILY_BUDGET_USD",
)


def env_file_path() -> Path:
    """``WORKER_ENV_FILE`` or the harness ``DEFAULT_ENV_FILE`` (read now, not at import)."""
    override = os.environ.get("WORKER_ENV_FILE")
    return Path(override) if override else Path(harness_config.DEFAULT_ENV_FILE)


def load_settings(env_file: Path | None = None) -> dict[str, str | None]:
    """``env_file`` (default :func:`env_file_path`) overlaid by ``os.environ``; blank → None."""
    path = Path(env_file) if env_file is not None else env_file_path()
    values: dict[str, str | None] = {}
    if path.is_file():
        values.update(dotenv_values(path))
    values.update(os.environ)
    return {k: (v.strip() or None) if isinstance(v, str) else v for k, v in values.items()}
