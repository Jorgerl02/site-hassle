"""fal.ai provider (TRELLIS or Hunyuan3D v3) through the queue API.

Docs consulted 2026-11-09 (fal.ai/docs via Context7 ``/websites/fal_ai`` and the model pages
fal.ai/models/fal-ai/trellis/api, fal.ai/models/fal-ai/hunyuan3d-v3/image-to-3d/api):

- ``POST https://queue.fal.run/{endpoint_id}`` with ``Authorization: Key $FAL_KEY`` and the
  model input as JSON → ``{"request_id", "status_url", "response_url", ...}``;
- ``GET status_url`` → ``{"status": "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED", ...}``;
- ``GET response_url`` → the model output.
- ``fal-ai/trellis``: input ``image_url`` (+ ``seed``, ``texture_size``), output
  ``model_mesh.url``. ``fal-ai/hunyuan3d-v3/image-to-3d``: input ``input_image_url``,
  output ``model_glb.url`` (also ``model_urls.glb``).
- Image URLs accept a base64 ``data:`` URI (Hunyuan docs: ≤ 6 MB recommended for base64).
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from platform_worker.providers.base import GenerationOutcome, ProviderError

QUEUE_BASE_URL = "https://queue.fal.run"
TRELLIS = "fal-ai/trellis"
HUNYUAN3D_V3 = "fal-ai/hunyuan3d-v3/image-to-3d"
MODELS: dict[str, str] = {"trellis": TRELLIS, "hunyuan3d": HUNYUAN3D_V3}
# USD per generation from fal.ai pricing (2026-11-09; TODO verificar en fal.ai/pricing):
# TRELLIS 0,02 $; Hunyuan3D v3 0,225–0,45 $ depending on options (upper bound kept so the
# recorded cost never under-reports).
USD_PER_MODEL: dict[str, float] = {TRELLIS: 0.02, HUNYUAN3D_V3: 0.45}
REQUEST_TIMEOUT_S = 60.0
_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def data_uri(path: Path) -> str:
    mime = _MIME.get(Path(path).suffix.lower(), "image/png")
    return f"data:{mime};base64,{base64.b64encode(Path(path).read_bytes()).decode('ascii')}"


def build_input(endpoint: str, image: Path, seed: int | None) -> dict[str, Any]:
    if endpoint == TRELLIS:
        payload: dict[str, Any] = {"image_url": data_uri(image), "texture_size": "2048"}
        if seed is not None:
            payload["seed"] = seed
        return payload
    return {"input_image_url": data_uri(image), "enable_pbr": True}


def glb_url(endpoint: str, result: dict[str, Any]) -> str | None:
    for key in ("model_mesh", "model_glb"):
        value = result.get(key)
        if isinstance(value, dict) and value.get("url"):
            return str(value["url"])
        if isinstance(value, str) and value:
            return value
    urls = result.get("model_urls") or {}
    glb = urls.get("glb") if isinstance(urls, dict) else None
    if isinstance(glb, dict):
        return glb.get("url")
    return glb


class FalProvider:
    name = "fal"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "trellis",
        timeout_s: float = 900.0,
        poll_interval_s: float = 5.0,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key:
            raise ValueError("Falta la clave de fal.ai (FAL_KEY)")
        self.endpoint = MODELS.get(model, model)
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self._auth = {"Authorization": f"Key {api_key}"}
        self._http = http_client or httpx.Client(timeout=REQUEST_TIMEOUT_S)
        self._sleep = sleep
        self._clock = clock

    def _json(self, response: httpx.Response, what: str) -> dict[str, Any]:
        if response.is_error:
            raise ProviderError(
                f"fal.ai respondió {response.status_code} en {what}: {response.text[:300]}"
            )
        return response.json()

    def generate(
        self, images: list[Path], dst_glb: Path, *, seed: int | None = None
    ) -> GenerationOutcome:
        if not images:
            raise ValueError("generate() necesita al menos una imagen")
        start = self._clock()
        payload = build_input(self.endpoint, Path(images[0]), seed)
        submit = self._json(
            self._http.post(f"{QUEUE_BASE_URL}/{self.endpoint}", json=payload, headers=self._auth),
            "el envío",
        )
        request_id = submit.get("request_id")
        status_url = submit.get("status_url")
        response_url = submit.get("response_url")
        if not (request_id and status_url and response_url):
            raise ProviderError(f"fal.ai no devolvió request_id/status_url: {submit}")

        history: list[str] = []
        while True:
            status = self._json(self._http.get(status_url, headers=self._auth), "el estado")
            state = str(status.get("status"))
            history.append(state)
            if state == "COMPLETED":
                if status.get("error"):
                    raise ProviderError(f"fal.ai terminó con error: {status.get('error')}")
                break
            if state not in ("IN_QUEUE", "IN_PROGRESS"):
                raise ProviderError(f"fal.ai devolvió el estado {state!r}")
            if self._clock() - start + self.poll_interval_s > self.timeout_s:
                raise ProviderError(
                    f"Tiempo agotado ({self.timeout_s:.0f} s) esperando a fal.ai ({request_id})"
                )
            self._sleep(self.poll_interval_s)

        result = self._json(self._http.get(response_url, headers=self._auth), "el resultado")
        url = glb_url(self.endpoint, result)
        if not url:
            raise ProviderError(f"fal.ai no devolvió el GLB ({request_id})")
        download = self._http.get(url, follow_redirects=True)  # public CDN URL: no auth
        if download.is_error:
            raise ProviderError(f"Descarga del GLB de fal.ai falló ({download.status_code})")
        dst_glb = Path(dst_glb)
        dst_glb.parent.mkdir(parents=True, exist_ok=True)
        dst_glb.write_bytes(download.content)
        cost = USD_PER_MODEL.get(self.endpoint, 0.0)
        return GenerationOutcome(
            glb_path=dst_glb,
            cost_usd=cost,
            seconds=self._clock() - start,
            meta={
                "provider": self.name,
                "endpoint": self.endpoint,
                "request_id": request_id,
                "seed": seed,
                "status_history": history,
                "cost_usd": cost,
                "cost_source": "platform_worker.providers.fal.USD_PER_MODEL",
            },
        )
