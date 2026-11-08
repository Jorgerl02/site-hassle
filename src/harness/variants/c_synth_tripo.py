"""Variant C: clean the first photo → synthetic orthographic views (Gemini, green key) →
silhouette check → Tripo multiview with the longest passing slot prefix of
``front, left, back, right``, or the cleaned real photo alone if degraded.

A view whose Gemini call fails is skipped (cost still recorded) and the slot rule decides.

Views are generated once per piece and shared by every candidate; candidates differ only in
the Tripo seed (= candidate index). The Gemini cost is split evenly across candidates so the
per-candidate costs add up to the real spend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.core import storage
from harness.core.config import Settings
from harness.core.models import Candidate, Piece, VariantResult
from harness.prep.clean import clean_image
from harness.prep.synth_views import VIEW_NAMES, check_views, generate_views, silhouette_aspect

CLEAN_DIRNAME = "clean"


class SynthTripoVariant:
    name = "C"

    def __init__(
        self,
        tripo: Any | None = None,
        image_client: Any | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._tripo = tripo
        self._image_client = image_client
        self._settings = settings

    def _get_settings(self) -> Settings:
        if self._settings is None:
            self._settings = Settings.load()
        return self._settings

    @property
    def tripo(self) -> Any:
        # Built lazily so the registry can list the variant without keys.
        if self._tripo is None:
            from harness.clients.tripo import TripoClient

            key = self._get_settings().tripo_api_key
            if not key:
                raise RuntimeError("Variante C: falta TRIPO_API_KEY en .env o en el entorno")
            self._tripo = TripoClient(key)
        return self._tripo

    @property
    def image_client(self) -> Any:
        if self._image_client is None:
            from harness.clients.gemini_image import GeminiImageClient

            key = self._get_settings().gemini_api_key
            if not key:
                raise RuntimeError("Variante C: falta GEMINI_API_KEY en .env o en el entorno")
            self._image_client = GeminiImageClient(key)
        return self._image_client

    def run(self, piece: Piece, workdir: Path, candidates: int = 2) -> VariantResult:
        workdir = Path(workdir)
        clean = clean_image(piece.images[0], workdir / CLEAN_DIRNAME / "front.png")

        image_client = self.image_client
        calls_before = len(getattr(image_client, "calls", []))
        views = generate_views(clean, piece, workdir, client=image_client)
        image_calls = list(getattr(image_client, "calls", []))[calls_before:]
        views_cost = sum(float(c.get("cost_usd", 0.0)) for c in image_calls)
        views_seconds = sum(float(c.get("seconds", 0.0)) for c in image_calls)

        failed_views = [v for v in VIEW_NAMES if v not in views]
        check = check_views(views, piece, fallback_front=clean)
        clean_check = {"path": str(clean), "silhouette_method": "white"}
        clean_check["aspect"] = silhouette_aspect(clean, "white")
        images = list(check.passed.values())
        cost_share = views_cost / candidates if candidates else 0.0
        seconds_share = views_seconds / candidates if candidates else 0.0

        result: list[Candidate] = []
        for index in range(1, candidates + 1):
            cand = storage.candidate_dir(workdir, index)
            outcome = self.tripo.generate(images, storage.model_path(cand), seed=index)
            cost = outcome.cost_usd + cost_share
            seconds = outcome.seconds + seconds_share
            meta = {
                "variant": self.name,
                "piece_id": piece.id,
                "index": index,
                "seed": index,
                "source_image": str(piece.images[0]),
                "clean_image": str(clean),
                "clean_image_check": clean_check,
                "views": {k: str(v) for k, v in views.items()},
                "views_failed_generation": failed_views,
                "views_passed": list(check.passed),
                "views_degraded": check.degraded,
                "view_checks": check.checks,
                "view_reasons": check.reasons,
                "tripo_images": [str(p) for p in images],
                "image_calls": image_calls,
                "views_cost_usd_total": views_cost,
                "views_cost_usd_share": cost_share,
                "tripo_cost_usd": outcome.cost_usd,
                "tripo_seconds": outcome.seconds,
                "tripo_meta": outcome.meta,
                "cost_usd": cost,
                "seconds": seconds,
            }
            storage.write_meta(cand, meta)
            result.append(
                Candidate(
                    index=index,
                    glb_path=outcome.glb_path,
                    cost_usd=cost,
                    seconds=seconds,
                    meta=meta,
                )
            )

        if check.degraded:
            mode = "degradada a solo la foto limpia (" + "; ".join(check.reasons) + ")"
        else:
            mode = f"multivista con {', '.join(check.passed)}"
        notes = (
            f"Vistas sintéticas Gemini ({len(image_calls)} llamada(s), "
            f"{len(failed_views)} fallida(s), {views_cost:.3f} USD) → "
            f"Tripo {mode}; candidatos con semillas 1..{candidates}"
        )
        return VariantResult(variant=self.name, piece_id=piece.id, candidates=result, notes=notes)
