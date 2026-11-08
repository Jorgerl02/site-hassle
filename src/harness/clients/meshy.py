"""Meshy API client (image-to-3D and multi-image-to-3D).

Docs consulted 2026-11-08:
- https://docs.meshy.ai/en/api/image-to-3d
- https://docs.meshy.ai/en/api/multi-image-to-3d
- https://docs.meshy.ai/en/api/errors
- https://docs.meshy.ai/en/api/pricing  (30 credits per textured generation, meshy-7.1 / 2K)

Neither endpoint documents a ``seed`` parameter, so ``seed`` is recorded in meta but not sent.
"""

from __future__ import annotations

import base64
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from harness.core.pricing import MESHY_USD_PER_MODEL

DEFAULT_BASE_URL = "https://api.meshy.ai/openapi/v1"
SINGLE_ENDPOINT = "image-to-3d"
MULTI_ENDPOINT = "multi-image-to-3d"
MAX_MULTI_IMAGES = 4  # the API returns 400 above this
SEED_SUPPORTED = False

TERMINAL_OK = "SUCCEEDED"
TERMINAL_FAILED = {"FAILED", "CANCELED"}
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
MAX_RETRIES = 3  # retries after the first attempt

# Request parameters shared by both endpoints (furniture: PBR textures, GLB only).
DEFAULT_PARAMS: dict[str, Any] = {
    "ai_model": "latest",
    "should_texture": True,
    "enable_pbr": True,
    "target_formats": ["glb"],
}


class MeshyError(RuntimeError):
    """Task failure, timeout or non-retryable HTTP error. ``payload`` is the last status."""

    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


@dataclass
class GenerationOutcome:
    glb_path: Path
    cost_usd: float
    seconds: float
    meta: dict[str, Any] = field(default_factory=dict)


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


class MeshyClient:
    # Seconds; doubled per retry. Class attributes so tests can zero them.
    retry_backoff_s: float = 2.0

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout_s: float = 600.0,
        poll_interval_s: float = 5.0,
    ) -> None:
        if not api_key:
            raise ValueError("MESHY_API_KEY no está configurada")
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s

    # -- HTTP -----------------------------------------------------------------

    def _request(self, http: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last: httpx.Response | Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt:
                time.sleep(self.retry_backoff_s * 2 ** (attempt - 1))
            try:
                response = http.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                last = exc
                continue
            if response.status_code in TRANSIENT_STATUS:
                last = response
                continue
            if response.is_error:
                raise MeshyError(
                    f"Meshy HTTP {response.status_code} en {method} {url}",
                    _json_or_text(response),
                )
            return response
        if isinstance(last, httpx.Response):
            raise MeshyError(
                f"Meshy HTTP {last.status_code} en {method} {url} tras {MAX_RETRIES} reintentos",
                _json_or_text(last),
            )
        raise MeshyError(f"Meshy sin respuesta en {method} {url}: {last}")

    # -- public ---------------------------------------------------------------

    def generate(
        self, images: list[Path], dst_glb: Path, *, seed: int | None = None
    ) -> GenerationOutcome:
        """1 image → image-to-3d; ≥2 images → multi-image-to-3d (first 4).
        Blocks until done and downloads the GLB to ``dst_glb``."""
        if not images:
            raise ValueError("Se necesita al menos una imagen")
        start = time.monotonic()
        multi = len(images) >= 2
        used = list(images[:MAX_MULTI_IMAGES]) if multi else [images[0]]
        endpoint = MULTI_ENDPOINT if multi else SINGLE_ENDPOINT
        body: dict[str, Any] = dict(DEFAULT_PARAMS)
        if multi:
            body["image_urls"] = [_data_uri(p) for p in used]
        else:
            body["image_url"] = _data_uri(used[0])

        meta: dict[str, Any] = {
            "provider": "meshy",
            "endpoint": endpoint,
            "multi_image": multi,
            "images": [str(p) for p in used],
            "images_dropped": [str(p) for p in images[len(used) :]],
            "request": dict(DEFAULT_PARAMS),
            "seed_requested": seed,
            "seed_supported": SEED_SUPPORTED,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(headers=headers, timeout=60.0) as http:
            created = self._request(http, "POST", f"{self.base_url}/{endpoint}", json=body).json()
            task_id = created.get("result")
            if not task_id:
                raise MeshyError("Meshy no devolvió id de tarea", created)
            meta["task_id"] = task_id
            payload = self._poll(http, f"{self.base_url}/{endpoint}/{task_id}", meta)

        glb_url = (payload.get("model_urls") or {}).get("glb")
        if not glb_url:
            raise MeshyError(f"Tarea Meshy {task_id} sin model_urls.glb", payload)
        dst_glb = Path(dst_glb)
        dst_glb.parent.mkdir(parents=True, exist_ok=True)
        # Signed asset URL: no Authorization header.
        with httpx.Client(timeout=120.0, follow_redirects=True) as http:
            dst_glb.write_bytes(self._request(http, "GET", glb_url).content)

        meta["consumed_credits"] = payload.get("consumed_credits")
        meta["final_status"] = payload
        return GenerationOutcome(
            glb_path=dst_glb,
            cost_usd=MESHY_USD_PER_MODEL,
            seconds=time.monotonic() - start,
            meta=meta,
        )

    def _poll(self, http: httpx.Client, url: str, meta: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        polls = 0
        while True:
            payload = self._request(http, "GET", url).json()
            polls += 1
            meta["polls"] = polls
            status = payload.get("status")
            if status == TERMINAL_OK:
                return payload
            if status in TERMINAL_FAILED:
                error = (payload.get("task_error") or {}).get("message") or status
                raise MeshyError(f"Tarea Meshy {payload.get('id')} {status}: {error}", payload)
            if time.monotonic() - start >= self.timeout_s:
                raise MeshyError(
                    f"Timeout de {self.timeout_s:.0f} s esperando la tarea Meshy "
                    f"{payload.get('id')} (estado {status})",
                    payload,
                )
            time.sleep(self.poll_interval_s)


def _json_or_text(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text}
    return data if isinstance(data, dict) else {"status_code": response.status_code, "body": data}
