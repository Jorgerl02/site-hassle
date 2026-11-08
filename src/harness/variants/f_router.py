"""Variant F — router: a VLM decides whether the piece is rectilinear or organic.

rectilinear → E (parametric, Blender); organic → C (synthetic views + Tripo) when the piece
has ≥ 2 photos, else B (clean + Tripo). If E cannot run because Blender is missing, the
organic route is used instead and the fallback is recorded in ``notes`` and in every
candidate's meta.

The delegate runs under ``workdir/route_<X>/`` (deeper than the ``<piece>/<variant>/cand_*``
layout, so the evaluation never discovers it as a variant of its own); its candidate folders
are then copied to F's own ``workdir/cand_<n>/``.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.config import Settings
from harness.core.models import Candidate, Piece, VariantResult
from harness.core.variant import Variant

ROUTER_PROMPT = (
    "Mira las fotos de este mueble. ¿La pieza es rectilínea (cajas, tableros, patas rectas) "
    "u orgánica (curvas, tapizado, formas libres)?\n"
    "Responde solo con un objeto JSON: "
    '{"rectilinear": true si es rectilínea o false si es orgánica, '
    '"motivo": "una frase en español"}.'
)
ROUTER_SCHEMA_HINT = '{"rectilinear": bool, "motivo": str}'
DELEGATE_DIR_PREFIX = "route_"
MIN_PHOTOS_FOR_SYNTH = 2


class RouterVariant:
    name = "F"

    def __init__(
        self,
        vlm: Any | None = None,
        *,
        e: Variant | None = None,
        c: Variant | None = None,
        b: Variant | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._vlm = vlm
        self._delegates: dict[str, Variant | None] = {"E": e, "C": c, "B": b}
        self._settings = settings

    @property
    def vlm(self) -> Any:
        # Built lazily so the registry can list the variant without a key.
        if self._vlm is None:
            from harness.clients.vlm import VLMClient

            key = (self._settings or Settings.load()).anthropic_api_key
            if not key:
                raise RuntimeError("Variante F: falta ANTHROPIC_API_KEY en .env o en el entorno")
            self._vlm = VLMClient(api_key=key)
        return self._vlm

    def delegate(self, route: str) -> Variant:
        if self._delegates[route] is None:
            if route == "E":
                from harness.variants.e_parametric import ParametricVariant

                self._delegates[route] = ParametricVariant()
            elif route == "C":
                from harness.variants.c_synth_tripo import SynthTripoVariant

                self._delegates[route] = SynthTripoVariant(settings=self._settings)
            else:
                from harness.variants.b_clean_tripo import CleanTripoVariant

                self._delegates[route] = CleanTripoVariant(settings=self._settings)
        return self._delegates[route]  # type: ignore[return-value]

    def classify(self, piece: Piece) -> dict[str, Any]:
        """Ask the VLM; returns ``{rectilinear, motivo, cost_usd, source, ...}``.

        If the VLM fails or answers without a boolean, the CSV label (``piece.rectilinear``)
        is used when present; otherwise the error propagates.
        """
        vlm = self.vlm
        cost_before = float(getattr(vlm, "total_cost_usd", 0.0) or 0.0)
        info: dict[str, Any] = {"csv_rectilinear": piece.rectilinear}
        try:
            answer = vlm.ask_json(ROUTER_PROMPT, list(piece.images), ROUTER_SCHEMA_HINT)
            if not isinstance(answer.get("rectilinear"), bool):
                raise ValueError(f"'rectilinear' no es booleano: {answer!r}")
            info.update(
                rectilinear=answer["rectilinear"],
                motivo=str(answer.get("motivo", "")),
                vlm_answer=answer,
                source="vlm",
            )
        except Exception as exc:
            if piece.rectilinear is None:
                raise
            info.update(rectilinear=piece.rectilinear, motivo="", source="csv", vlm_error=str(exc))
        info["cost_usd"] = float(getattr(vlm, "total_cost_usd", 0.0) or 0.0) - cost_before
        if piece.rectilinear is not None:
            info["agrees_with_csv"] = info["rectilinear"] == piece.rectilinear
        return info

    def organic_route(self, piece: Piece) -> str:
        return "C" if len(piece.images) >= MIN_PHOTOS_FOR_SYNTH else "B"

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        workdir = Path(workdir)
        router = self.classify(piece)
        route = "E" if router["rectilinear"] else self.organic_route(piece)
        fallback: str | None = None

        try:
            result = self._run_delegate(route, piece, workdir, candidates)
        except BlenderNotAvailable as exc:
            if route != "E":
                raise
            fallback = f"E no disponible ({exc}); se usa la ruta orgánica"
            route = self.organic_route(piece)
            result = self._run_delegate(route, piece, workdir, candidates)

        router_meta = {**router, "routed_to": route, "fallback": fallback}
        n = len(result.candidates)
        vlm_share = router["cost_usd"] / n if n else 0.0
        delegate_root = self._delegate_dir(workdir, route)
        out: list[Candidate] = []
        for cand in result.candidates:
            src_dir = storage.candidate_dir(delegate_root, cand.index)
            dst_dir = storage.candidate_dir(workdir, cand.index)
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            glb = self._relocate(cand.glb_path, src_dir, dst_dir)
            cost = cand.cost_usd + vlm_share
            meta = {
                **cand.meta,
                "variant": self.name,
                "piece_id": piece.id,
                "index": cand.index,
                "routed_to": route,
                "router": router_meta,
                "router_cost_usd_share": vlm_share,
                "delegate_cost_usd": cand.cost_usd,
                "delegate_glb_path": str(cand.glb_path),
                "cost_usd": cost,
                "seconds": cand.seconds,
            }
            storage.write_meta(dst_dir, meta)
            out.append(
                Candidate(
                    index=cand.index, glb_path=glb, cost_usd=cost, seconds=cand.seconds, meta=meta
                )
            )

        kind = "rectilínea" if router["rectilinear"] else "orgánica"
        parts = [f"VLM ({router['source']}): {kind} → ruta {route}"]
        if fallback:
            parts.append(fallback)
        if result.notes:
            parts.append(f"[{route}] {result.notes}")
        return VariantResult(
            variant=self.name, piece_id=piece.id, candidates=out, notes="; ".join(parts)
        )

    def _delegate_dir(self, workdir: Path, route: str) -> Path:
        return workdir / f"{DELEGATE_DIR_PREFIX}{route}"

    def _run_delegate(
        self, route: str, piece: Piece, workdir: Path, candidates: int
    ) -> VariantResult:
        sub = self._delegate_dir(workdir, route)
        sub.mkdir(parents=True, exist_ok=True)
        return self.delegate(route).run(piece, sub, candidates)

    @staticmethod
    def _relocate(glb: Path, src_dir: Path, dst_dir: Path) -> Path:
        """Path of ``glb`` inside F's candidate folder (copied there if it lived elsewhere)."""
        glb = Path(glb)
        try:
            return dst_dir / glb.resolve().relative_to(src_dir.resolve())
        except ValueError:
            target = storage.model_path(dst_dir)
            shutil.copyfile(glb, target)
            return target
