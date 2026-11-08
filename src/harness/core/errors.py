"""Failure classification shared by the CLI (run meta), the variants (candidate metas),
the resume logic and the evaluation."""

from __future__ import annotations

from typing import Literal

import httpx

from harness.core.blender import BlenderNotAvailable
from harness.core.config import MissingKeyError

ErrorKind = Literal["infra", "candidate"]

__all__ = ["ErrorKind", "MissingKeyError", "error_kind"]


def error_kind(exc: BaseException) -> ErrorKind:
    """``"infra"`` (missing key, no Blender, network) or ``"candidate"`` (provider failed).

    Looks through the whole cause chain: clients wrap network errors in their own types.
    """
    infra: tuple[type[BaseException], ...] = (
        MissingKeyError,
        BlenderNotAvailable,
        httpx.TransportError,
        ConnectionError,
    )
    try:
        import anthropic

        infra = (*infra, anthropic.APIConnectionError)
    except ImportError:  # pragma: no cover
        pass
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, infra):
            return "infra"
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return "candidate"
