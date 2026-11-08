"""Tripo3D API client (photo -> textured GLB).

Endpoints (Tripo OpenAPI v2, docs consulted 2026-11-08,
https://platform.tripo3d.ai/docs/upload, /docs/generation, /docs/task):

- ``POST /upload/sts`` multipart ``file`` -> ``data.image_token`` (used as ``file_token``)
- ``POST /task`` ``{"type": "image_to_model", "file": {...}}`` or
  ``{"type": "multiview_to_model", "files": [front, left, back, right]}`` -> ``data.task_id``
- ``GET /task/{task_id}`` -> ``data.status`` in queued/running (ongoing) or
  success/failed/banned/expired/cancelled/unknown (final); ``data.output.pbr_model``
  (or ``model``) is a GLB URL that expires after ~5 minutes; ``data.consumed_credit``.

Every response is wrapped as ``{"code": 0, "data": {...}}``; ``code != 0`` is an error.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from harness.core import pricing

DEFAULT_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
# Highest-fidelity non-P1 version listed for both image_to_model and multiview_to_model.
DEFAULT_MODEL_VERSION = "v3.1-20260211"
# Quality/texture parameters sent with every generation (PBR textures, standard quality).
DEFAULT_GENERATION_PARAMS: dict[str, Any] = {
    "texture": True,
    "pbr": True,
    "texture_quality": "standard",
    "texture_alignment": "original_image",
}
# 1 credit = 0.01 USD (https://developers.tripo3d.ai/, read 2026-11-08). Only used to record
# an informative USD figure next to ``consumed_credit``; ``cost_usd`` comes from ``pricing``.
# TODO verificar 2026-11-08 https://platform.tripo3d.ai/docs/billing
USD_PER_CREDIT = 0.01

MULTIVIEW_SLOTS = ("front", "left", "back", "right")
ONGOING_STATUSES = frozenset({"queued", "running"})
SUCCESS_STATUS = "success"
RETRYABLE_STATUS_CODES = frozenset({408, 429})
MAX_RETRIES = 3
REQUEST_TIMEOUT_S = 60.0
_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class TripoError(RuntimeError):
    """A Tripo request or task failed (or timed out). ``payload`` is the last status/body."""

    def __init__(self, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.payload = payload


@dataclass
class GenerationOutcome:
    glb_path: Path
    cost_usd: float
    seconds: float
    meta: dict[str, Any] = field(default_factory=dict)


def _mime(path: Path) -> str:
    mime = _MIME_TYPES.get(path.suffix.lower())
    if mime is None:
        raise ValueError(f"Formato de imagen no soportado por Tripo: {path}")
    return mime


def _file_ref(token: str, path: Path) -> dict[str, str]:
    return {"type": path.suffix.lower().lstrip(".") or "jpg", "file_token": token}


class TripoClient:
    """Blocking client: ``generate`` uploads, creates the task, polls and downloads the GLB.

    ``http_client``, ``sleep`` and ``clock`` are injectable for tests.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout_s: float = 600.0,
        poll_interval_s: float = 5.0,
        model_version: str = DEFAULT_MODEL_VERSION,
        generation_params: dict[str, Any] | None = None,
        max_retries: int = MAX_RETRIES,
        backoff_s: float = 2.0,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key:
            raise ValueError("Falta la clave de Tripo (TRIPO_API_KEY)")
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.model_version = model_version
        self.generation_params = dict(
            DEFAULT_GENERATION_PARAMS if generation_params is None else generation_params
        )
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self._sleep = sleep
        self._clock = clock
        self._auth = {"Authorization": f"Bearer {api_key}"}
        self._http = http_client or httpx.Client(timeout=REQUEST_TIMEOUT_S)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> TripoClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- HTTP helpers -------------------------------------------------------------------

    def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send with retries on 408/429/5xx and transport errors (``max_retries`` retries)."""
        for attempt in range(self.max_retries + 1):
            last = attempt == self.max_retries
            try:
                response = self._http.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                if last:
                    raise TripoError(f"Error de red con Tripo: {exc}") from exc
            else:
                code = response.status_code
                transient = code in RETRYABLE_STATUS_CODES or code >= 500
                if not transient or last:
                    return response
            self._sleep(self.backoff_s * 2**attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    def _api(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._send(method, f"{self.base_url}{path}", headers=self._auth, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}
        if response.is_error or not isinstance(body, dict) or body.get("code", 0) != 0:
            raise TripoError(
                f"Tripo {method} {path} respondió {response.status_code}: {body}", body
            )
        data = body.get("data")
        if not isinstance(data, dict):
            raise TripoError(f"Respuesta de Tripo sin 'data' en {method} {path}", body)
        return data

    # -- API steps ----------------------------------------------------------------------

    def upload(self, image: Path) -> str:
        image = Path(image)
        files = {"file": (image.name, image.read_bytes(), _mime(image))}
        data = self._api("POST", "/upload/sts", files=files)
        token = data.get("image_token") or data.get("file_token")
        if not token:
            raise TripoError("La subida a Tripo no devolvió image_token", data)
        return str(token)

    def build_request(
        self, images: list[Path], tokens: list[str], seed: int | None
    ) -> dict[str, Any]:
        request: dict[str, Any] = {"model_version": self.model_version}
        if len(tokens) == 1:
            request["type"] = "image_to_model"
            request["file"] = _file_ref(tokens[0], images[0])
        else:
            refs: list[dict[str, str]] = [
                _file_ref(token, path) for token, path in zip(tokens, images, strict=True)
            ]
            refs += [{}] * (len(MULTIVIEW_SLOTS) - len(refs))
            request["type"] = "multiview_to_model"
            request["files"] = refs
        request.update(self.generation_params)
        if seed is not None:
            request["model_seed"] = seed
            request["texture_seed"] = seed
        return request

    def create_task(self, request: dict[str, Any]) -> str:
        data = self._api("POST", "/task", json=request)
        task_id = data.get("task_id")
        if not task_id:
            raise TripoError("Tripo no devolvió task_id", data)
        return str(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._api("GET", f"/task/{task_id}")

    def download(self, url: str, dst: Path) -> Path:
        # Signed storage URL: no Authorization header.
        response = self._send("GET", url)
        if response.is_error:
            raise TripoError(f"Descarga del GLB falló ({response.status_code})", url)
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(response.content)
        return dst

    # -- Public contract ----------------------------------------------------------------

    def generate(
        self, images: list[Path], dst_glb: Path, *, seed: int | None = None
    ) -> GenerationOutcome:
        """1 image -> image_to_model; >=2 images -> multiview_to_model (first 4, in order
        front, left, back, right). Blocks until done and downloads the GLB to ``dst_glb``.
        Raises ``TripoError`` on failure or when ``timeout_s`` (total wall clock) elapses."""
        images = [Path(p) for p in images]
        if not images:
            raise ValueError("generate() necesita al menos una imagen")
        used = images[: len(MULTIVIEW_SLOTS)]
        start = self._clock()
        deadline = start + self.timeout_s

        tokens = [self.upload(path) for path in used]
        upload_s = self._clock() - start

        request = self.build_request(used, tokens, seed)
        task_id = self.create_task(request)
        created_at = self._clock()

        history: list[dict[str, Any]] = []
        while True:
            task = self.get_task(task_id)
            status = str(task.get("status", "unknown"))
            history.append(
                {
                    "t": round(self._clock() - start, 3),
                    "status": status,
                    "progress": task.get("progress"),
                }
            )
            if status == SUCCESS_STATUS:
                break
            if status not in ONGOING_STATUSES:
                raise TripoError(f"La tarea Tripo {task_id} terminó con estado '{status}'", task)
            if self._clock() + self.poll_interval_s > deadline:
                raise TripoError(
                    f"Tiempo agotado ({self.timeout_s:.0f} s) esperando la tarea Tripo {task_id}",
                    task,
                )
            self._sleep(self.poll_interval_s)
        task_s = self._clock() - created_at

        output = task.get("output") or {}
        url = output.get("pbr_model") or output.get("model") or output.get("base_model")
        if not url:
            raise TripoError(f"La tarea Tripo {task_id} no devolvió URL de modelo", task)
        download_start = self._clock()
        glb = self.download(url, dst_glb)
        seconds = self._clock() - start

        credits = task.get("consumed_credit", output.get("consumed_credit"))
        cost_usd = pricing.TRIPO_USD_PER_MODEL
        meta: dict[str, Any] = {
            "provider": "tripo",
            "task_id": task_id,
            "task_type": request["type"],
            "model_version": self.model_version,
            "seed": seed,
            "images": [str(p) for p in used],
            "images_ignored": [str(p) for p in images[len(used) :]],
            "request": request,
            "status_history": history,
            "final_status": task,
            "model_url_field": next(
                k for k in ("pbr_model", "model", "base_model") if output.get(k)
            ),
            "consumed_credit": credits,
            "consumed_credit_usd": (
                round(float(credits) * USD_PER_CREDIT, 4) if credits is not None else None
            ),
            "cost_usd": cost_usd,
            "cost_source": "pricing.TRIPO_USD_PER_MODEL",
            "timings": {
                "upload_s": upload_s,
                "task_s": task_s,
                "download_s": self._clock() - download_start,
                "total_s": seconds,
            },
        }
        return GenerationOutcome(glb_path=glb, cost_usd=cost_usd, seconds=seconds, meta=meta)
