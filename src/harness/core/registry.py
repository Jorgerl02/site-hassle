"""Variant registry by name. Task 8 registers A–F here."""

from __future__ import annotations

from collections.abc import Callable

from harness.core.variant import FakeVariant, Variant

_FACTORIES: dict[str, Callable[[], Variant]] = {
    "FAKE": FakeVariant,
}


def available_variants() -> list[str]:
    return sorted(_FACTORIES)


def get_variant(name: str) -> Variant:
    key = name.strip().upper()
    try:
        return _FACTORIES[key]()
    except KeyError:
        raise KeyError(
            f"Variante desconocida {name!r}; disponibles: {', '.join(available_variants())}"
        ) from None
