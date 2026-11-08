"""Variant registry by name.

Factories import their variant lazily so that importing the registry (and listing the
variants) never imports every client SDK. Variants build their clients on first ``run``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from harness.core.variant import FakeVariant, Variant


def _variant_a() -> Variant:
    from harness.variants.a_tripo_direct import TripoDirectVariant

    return TripoDirectVariant()


def _variant_b() -> Variant:
    from harness.variants.b_clean_tripo import CleanTripoVariant

    return CleanTripoVariant()


def _variant_c() -> Variant:
    from harness.variants.c_synth_tripo import SynthTripoVariant

    return SynthTripoVariant()


def _variant_d() -> Variant:
    from harness.variants.d_clean_meshy import CleanMeshyVariant

    return CleanMeshyVariant()


def _variant_e() -> Variant:
    from harness.variants.e_parametric import ParametricVariant

    return ParametricVariant()


def _variant_f(classifier: str = "auto", organic_variant: str | None = None) -> Variant:
    from harness.variants.f_router import RouterVariant

    others: dict[str, Variant] = {}
    if organic_variant is not None:
        organic_variant = organic_variant.strip().upper()
        if organic_variant not in ("B", "C"):
            # Any other registered variant can be F's organic route (e.g. "D").
            if organic_variant in ("E", "F"):
                raise ValueError(f"Variante F: {organic_variant} no puede ser la ruta orgánica")
            others[organic_variant] = get_variant(organic_variant)
    return RouterVariant(classifier=classifier, organic_variant=organic_variant, others=others)


_FACTORIES: dict[str, Callable[..., Variant]] = {
    "FAKE": FakeVariant,
    "A": _variant_a,
    "B": _variant_b,
    "C": _variant_c,
    "D": _variant_d,
    "E": _variant_e,
    "F": _variant_f,
}


def available_variants() -> list[str]:
    return sorted(_FACTORIES)


def get_variant(name: str, **options: Any) -> Variant:
    """Build the variant ``name``. ``options`` go to its factory (only F takes any today:
    ``classifier`` and ``organic_variant``); without options the factory gets no arguments."""
    key = name.strip().upper()
    try:
        factory = _FACTORIES[key]
    except KeyError:
        raise KeyError(
            f"Variante desconocida {name!r}; disponibles: {', '.join(available_variants())}"
        ) from None
    return factory(**options) if options else factory()
