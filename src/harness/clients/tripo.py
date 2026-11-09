"""Tripo3D API client (photo -> textured GLB), Tripo API v3.

Docs read 2026-11-09 at https://developers.tripo3d.ai/en/docs/ (the old
platform.tripo3d.ai/docs/* pages now redirect there): ``generation-image-to-model/standard``,
``generation-multiview-to-model/standard``, ``files``, ``task-query``, ``billing``,
``error-handling``, ``rate-limits``, ``models-and-versions``, ``migration-v2-to-v3``,
``changelog``, and the pricing page https://developers.tripo3d.ai/en/pricing.

- ``POST /files`` multipart ``file`` (JPEG/PNG, ≤ 20 MB) -> ``data.file_token``.
- ``POST /generation/image-to-model`` ``{"input": <file_token>, "model": ..., ...}``.
- ``POST /generation/multiview-to-model`` ``{"inputs": [{"front": tok}, {"left": tok}, ...]}``
  (view-key format: each object names its view, ``front`` is mandatory, ≥ 2 images, order
  free). Both return ``data.task_id``. Only explicitly labelled ``views`` go multiview.
- ``GET /tasks/{task_id}`` -> ``data.status`` queued/running (ongoing), success,
  failed/cancelled (final; legacy banned/expired are final too; ``unknown`` is waited out
  within the deadline); ``data.output.model_url`` (GLB); ``data.credits_consumed`` (number).

Every response is wrapped as ``{"code": 0, "data": {...}}``; ``code != 0`` is an error.

Pietra settings (Tripo web) -> API (see ``TripoSettings``): v3.1 -> ``model``
``v3.1-20260211``; HD Model / 4K texture -> ``texture_quality="detailed"`` (the API has no
4K switch: ``detailed`` is "HD", ``extreme`` is 8K); Ultra Mesh -> ``geometry_quality=
"detailed"``; PBR -> ``pbr``; polycount -> ``face_limit``; AI Complete -> closest is
``enable_image_autofix`` (image-to-model only), OFF by default because it alters the
customer's photo and the mapping is an inference (``TRIPO_IMAGE_AUTOFIX=1`` enables it).
Quad is NOT sent: the docs say ``quad=true`` forces FBX output, and the contract is a GLB.
"""

from __future__ import annotations

import io
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx
from PIL import Image

from harness.core import pricing

DEFAULT_BASE_URL = "https://openapi.tripo3d.ai/v3"
IMAGE_TO_MODEL = "image_to_model"
MULTIVIEW_TO_MODEL = "multiview_to_model"
ENDPOINTS = {
    IMAGE_TO_MODEL: "/generation/image-to-model",
    MULTIVIEW_TO_MODEL: "/generation/multiview-to-model",
}
# "v3.1-20260211 — recommended; latest, best quality" (models-and-versions, 2026-11-09).
DEFAULT_MODEL_VERSION = "v3.1-20260211"
# Documented H Series ``model`` values (P1/P2 have other parameters and prices).
MODEL_VERSIONS = ("v3.1-20260211", "v3.0-20250812", "v2.5-20250123")
LEGACY_MODEL_VERSION = "v2.5-20250123"
# "Only valid when model ≥ v3.0-20250812" (the ones this client sends).
V3_ONLY_PARAMS = ("texture_quality", "geometry_quality", "auto_size")
TEXTURE_QUALITIES = ("fast", "standard", "detailed", "extreme")
GEOMETRY_QUALITIES = ("standard", "detailed")
ORIENTATIONS = ("default", "align_image")
TEXTURE_ALIGNMENTS = ("original_image", "geometry")
TEXTURE_VERSIONS = ("v3.5-20260815", "v3.0-20250812", "v2.5-20250123")
FAST_TEXTURE_VERSION = "v3.5-20260815"  # texture_quality="fast" requires it
MAX_FACE_LIMIT = 2_000_000  # triangle, v3.x Ultra (Standard v3.1: 1,500,000)

# Credit table and USD per credit: ``harness.core.pricing`` (TRIPO_*).
USD_PER_CREDIT = pricing.TRIPO_USD_PER_CREDIT

View = Literal["front", "left", "back", "right"]
MULTIVIEW_SLOTS: tuple[View, ...] = ("front", "left", "back", "right")
ONGOING_STATUSES = frozenset({"queued", "running", "unknown"})  # unknown: bounded wait
SUCCESS_STATUS = "success"
RETRYABLE_STATUS_CODES = frozenset({408, 429})  # plus every 5xx (idempotent calls only)
# Task creation is billed: retry only when the request certainly created nothing.
NON_IDEMPOTENT_RETRY_STATUS_CODES = frozenset({429})
NON_IDEMPOTENT_RETRY_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout)
MAX_RETRIES = 3
REQUEST_TIMEOUT_S = 60.0
# The upload endpoint lists JPEG and PNG only; WebP photos are re-encoded to PNG.
_UPLOAD_MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
_CONVERT_TO_PNG = frozenset({".webp"})

# env var -> TripoSettings field
ENV_VARS: dict[str, str] = {
    "TRIPO_MODEL_VERSION": "model_version",
    "TRIPO_TEXTURE": "texture",
    "TRIPO_PBR": "pbr",
    "TRIPO_TEXTURE_QUALITY": "texture_quality",
    "TRIPO_GEOMETRY_QUALITY": "geometry_quality",
    "TRIPO_FACE_LIMIT": "face_limit",
    "TRIPO_ORIENTATION": "orientation",
    "TRIPO_TEXTURE_ALIGNMENT": "texture_alignment",
    "TRIPO_IMAGE_AUTOFIX": "image_autofix",
    "TRIPO_AUTO_SIZE": "auto_size",
    "TRIPO_TEXTURE_VERSION": "texture_version",
}
_BOOL_FIELDS = frozenset({"texture", "pbr", "image_autofix", "auto_size"})
_TRUE = frozenset({"1", "true", "yes", "on", "si", "sí"})
_FALSE = frozenset({"0", "false", "no", "off"})


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


def _choice(name: str, value: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise ValueError(
            f"{name}={value!r} no es válido para Tripo (válidos: {', '.join(allowed)})"
        )
    return value


def _env_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{name}={raw!r} no es un booleano (usa true/false)")


@dataclass(frozen=True)
class TripoSettings:
    """Generation options sent with every task. Defaults = the Pietra settings that worked
    in Tripo web (v3.1, HD texture, Ultra mesh, PBR, ~40k faces, aligned to the photo)."""

    model_version: str = DEFAULT_MODEL_VERSION
    texture: bool = True
    pbr: bool = True
    texture_quality: str = "detailed"
    geometry_quality: str = "detailed"
    face_limit: int | None = 40_000  # None -> adaptive topology
    orientation: str = "align_image"
    texture_alignment: str = "original_image"
    # enable_image_autofix (image-to-model only). Off: it alters the customer's photo, and
    # mapping it to Tripo web's "AI Complete" is an inference. TRIPO_IMAGE_AUTOFIX=1 enables.
    image_autofix: bool = False
    auto_size: bool = False
    texture_version: str | None = None  # None -> derived from the geometry model

    def __post_init__(self) -> None:
        _choice("TRIPO_MODEL_VERSION", self.model_version, MODEL_VERSIONS)
        if self.model_version == LEGACY_MODEL_VERSION and (
            self.texture_quality != "standard"
            or self.geometry_quality != "standard"
            or self.auto_size
        ):
            raise ValueError(
                f"{LEGACY_MODEL_VERSION} no admite texture_quality/geometry_quality/auto_size: "
                "pon TRIPO_TEXTURE_QUALITY=standard, TRIPO_GEOMETRY_QUALITY=standard y "
                "TRIPO_AUTO_SIZE=false"
            )
        if self.orientation == "align_image" and not self.textured:
            raise ValueError(
                "orientation='align_image' sólo tiene efecto con textura: pon "
                "TRIPO_ORIENTATION=default o activa TRIPO_TEXTURE/TRIPO_PBR"
            )
        _choice("TRIPO_TEXTURE_QUALITY", self.texture_quality, TEXTURE_QUALITIES)
        _choice("TRIPO_GEOMETRY_QUALITY", self.geometry_quality, GEOMETRY_QUALITIES)
        _choice("TRIPO_ORIENTATION", self.orientation, ORIENTATIONS)
        _choice("TRIPO_TEXTURE_ALIGNMENT", self.texture_alignment, TEXTURE_ALIGNMENTS)
        if self.texture_version is not None:
            _choice("TRIPO_TEXTURE_VERSION", self.texture_version, TEXTURE_VERSIONS)
        if self.texture_quality == "fast" and self.texture_version != FAST_TEXTURE_VERSION:
            raise ValueError(
                f"texture_quality='fast' exige TRIPO_TEXTURE_VERSION={FAST_TEXTURE_VERSION}"
            )
        if self.face_limit is not None and not 1 <= self.face_limit <= MAX_FACE_LIMIT:
            raise ValueError(f"TRIPO_FACE_LIMIT={self.face_limit} fuera de 1..{MAX_FACE_LIMIT}")

    @property
    def textured(self) -> bool:
        return self.texture or self.pbr  # "pbr=true forces texture=true"

    @classmethod
    def from_env(cls, env: Mapping[str, str | None] | None = None) -> TripoSettings:
        """Defaults overridden by ``TRIPO_*`` variables (blank values are ignored).
        ``TRIPO_FACE_LIMIT=0`` (or ``adaptive``) means adaptive topology."""
        env = os.environ if env is None else env
        overrides: dict[str, Any] = {}
        for var, name in ENV_VARS.items():
            raw = env.get(var)
            if raw is None or not str(raw).strip():
                continue
            raw = str(raw).strip()
            if name in _BOOL_FIELDS:
                overrides[name] = _env_bool(var, raw)
            elif name == "face_limit":
                if raw.lower() in {"0", "adaptive", "none"}:
                    overrides[name] = None
                else:
                    try:
                        overrides[name] = int(raw)
                    except ValueError:
                        raise ValueError(f"{var}={raw!r} no es un entero") from None
            else:
                overrides[name] = raw
        return cls(**overrides)

    def params(self, task_type: str) -> dict[str, Any]:
        """Request fields (besides the input) for ``task_type``."""
        out: dict[str, Any] = {
            "model": self.model_version,
            "texture": self.texture,
            "pbr": self.pbr,
            "texture_quality": self.texture_quality,
            "geometry_quality": self.geometry_quality,
            "orientation": self.orientation,
            "texture_alignment": self.texture_alignment,
            "auto_size": self.auto_size,
        }
        if self.face_limit is not None:
            out["face_limit"] = self.face_limit
        if self.texture_version is not None:
            out["texture_version"] = self.texture_version
        if self.model_version == LEGACY_MODEL_VERSION:
            for name in V3_ONLY_PARAMS:
                del out[name]
        if task_type == IMAGE_TO_MODEL:  # not a multiview-to-model parameter
            out["enable_image_autofix"] = self.image_autofix
        return out

    def estimated_credits(self) -> int:
        """Credits from the pricing table (same for image and multiview, H Series)."""
        if not self.textured:
            credits = pricing.TRIPO_CREDITS_BASE_NO_TEXTURE
        else:
            credits = (
                pricing.TRIPO_CREDITS_BASE_TEXTURE
                + pricing.TRIPO_CREDITS_TEXTURE_QUALITY_ADDON[self.texture_quality]
            )
        if self.geometry_quality == "detailed":
            credits += pricing.TRIPO_CREDITS_GEOMETRY_DETAILED_ADDON
        return credits

    def estimated_cost_usd(self) -> float:
        return round(self.estimated_credits() * USD_PER_CREDIT, 4)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _upload_payload(path: Path) -> tuple[str, bytes, str]:
    suffix = path.suffix.lower()
    if suffix in _UPLOAD_MIME_TYPES:
        return path.name, path.read_bytes(), _UPLOAD_MIME_TYPES[suffix]
    if suffix in _CONVERT_TO_PNG:
        buffer = io.BytesIO()
        with Image.open(path) as img:
            img.save(buffer, format="PNG")
        return f"{path.stem}.png", buffer.getvalue(), "image/png"
    raise ValueError(f"Formato de imagen no soportado por Tripo: {path}")


def resolve_inputs(
    images: list[Path], views: Mapping[View, Path] | None
) -> tuple[list[tuple[View | None, Path]], list[Path]]:
    """``(inputs, ignored)``. Multiview needs every photo labelled front/left/back/right
    and ``front`` is mandatory (docs), so unlabelled photos never go multiview: the first
    one is used and the rest are reported as ignored."""
    if views is None:
        if not images:
            raise ValueError("generate() necesita al menos una imagen")
        return [(None, images[0])], images[1:]
    if images:
        raise ValueError("generate(): pasa las fotos en images o en views, no en ambos")
    unknown = set(views) - set(MULTIVIEW_SLOTS)
    if unknown:
        raise ValueError(f"Vistas desconocidas para Tripo: {sorted(unknown)}")
    if "front" not in views:
        raise ValueError("Tripo multiview exige la vista 'front'")
    if len(views) == 1:
        return [(None, Path(views["front"]))], []
    return [(slot, Path(views[slot])) for slot in MULTIVIEW_SLOTS if slot in views], []


class TripoClient:
    """Blocking client: ``generate`` uploads, creates the task, polls and downloads the GLB.

    ``settings`` defaults to ``TripoSettings.from_env()``. ``http_client``, ``sleep`` and
    ``clock`` are injectable for tests.
    """

    def __init__(
        self,
        api_key: str,
        *,
        settings: TripoSettings | None = None,
        base_url: str | None = None,
        timeout_s: float = 600.0,
        poll_interval_s: float = 5.0,
        max_retries: int = MAX_RETRIES,
        backoff_s: float = 2.0,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key:
            raise ValueError("Falta la clave de Tripo (TRIPO_API_KEY)")
        self.settings = settings if settings is not None else TripoSettings.from_env()
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self._sleep = sleep
        self._clock = clock
        self._auth = {"Authorization": f"Bearer {api_key}"}
        self._http = http_client or httpx.Client(timeout=REQUEST_TIMEOUT_S)

    @property
    def model_version(self) -> str:
        return self.settings.model_version

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> TripoClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- HTTP helpers -------------------------------------------------------------------

    def _send(
        self, method: str, url: str, *, idempotent: bool = True, **kwargs: Any
    ) -> tuple[httpx.Response, int]:
        """Send with up to ``max_retries`` retries; returns ``(response, attempts)``.

        Idempotent calls (upload, polling, download) retry on 408/429/5xx and any transport
        error. Non-idempotent calls (task creation, which is billed) retry only when the
        request certainly did not create anything: HTTP 429 or a connect error/timeout.
        """
        retry_exc = httpx.TransportError if idempotent else NON_IDEMPOTENT_RETRY_EXCEPTIONS
        for attempt in range(self.max_retries + 1):
            last = attempt == self.max_retries
            try:
                response = self._http.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                if last or not isinstance(exc, retry_exc):
                    raise TripoError(f"Error de red con Tripo ({method} {url}): {exc!r}") from exc
            else:
                code = response.status_code
                if idempotent:
                    transient = code in RETRYABLE_STATUS_CODES or code >= 500
                else:
                    transient = code in NON_IDEMPOTENT_RETRY_STATUS_CODES
                if not transient or last:
                    return response, attempt + 1
            self._sleep(self.backoff_s * 2**attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    def _api_call(
        self, method: str, path: str, *, idempotent: bool = True, **kwargs: Any
    ) -> tuple[dict[str, Any], int]:
        response, attempts = self._send(
            method, f"{self.base_url}{path}", idempotent=idempotent, headers=self._auth, **kwargs
        )
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
        return data, attempts

    def _api(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        return self._api_call(method, path, **kwargs)[0]

    # -- API steps ----------------------------------------------------------------------

    def upload(self, image: Path) -> str:
        data = self._api("POST", "/files", files={"file": _upload_payload(Path(image))})
        token = data.get("file_token")
        if not token:
            raise TripoError("La subida a Tripo no devolvió file_token", data)
        return str(token)

    def build_request(
        self, tokens: list[tuple[View | None, str]], seed: int | None
    ) -> tuple[str, dict[str, Any]]:
        """``(task_type, body)`` from ``(view, file_token)`` pairs: one pair ->
        image-to-model; several (all labelled, see ``resolve_inputs``) ->
        multiview-to-model in the documented view-key format."""
        if len(tokens) == 1:
            task_type = IMAGE_TO_MODEL
            request: dict[str, Any] = {"input": tokens[0][1]}
        else:
            if any(view is None for view, _ in tokens):
                raise ValueError("multiview-to-model necesita una vista etiquetada por imagen")
            task_type = MULTIVIEW_TO_MODEL
            request = {"inputs": [{view: token} for view, token in tokens]}
        request.update(self.settings.params(task_type))
        if seed is not None:
            request["model_seed"] = seed
            request["texture_seed"] = seed
        return task_type, request

    def create_task(self, task_type: str, request: dict[str, Any]) -> tuple[str, int]:
        """Create the (billed) task; returns ``(task_id, attempts)``. Not retried on
        5xx/408/read errors, so a lost response can never produce a second paid task."""
        data, attempts = self._api_call(
            "POST", ENDPOINTS[task_type], idempotent=False, json=request
        )
        task_id = data.get("task_id")
        if not task_id:
            raise TripoError("Tripo no devolvió task_id", data)
        return str(task_id), attempts

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._api("GET", f"/tasks/{task_id}")

    def download(self, url: str, dst: Path) -> Path:
        # Signed storage URL: no Authorization header.
        response, _ = self._send("GET", url)
        if response.is_error:
            raise TripoError(f"Descarga del GLB falló ({response.status_code})", url)
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(response.content)
        return dst

    # -- Public contract ----------------------------------------------------------------

    def generate(
        self,
        images: list[Path],
        dst_glb: Path,
        *,
        seed: int | None = None,
        views: Mapping[View, Path] | None = None,
    ) -> GenerationOutcome:
        """Unlabelled ``images`` -> image-to-model with the first one only (photos are never
        labelled by position). Labelled ``views`` (``images`` empty) -> multiview-to-model,
        or image-to-model when only ``front`` is given. Blocks until done and downloads
        the GLB to ``dst_glb``. Raises ``TripoError`` on failure or when ``timeout_s``
        (total wall clock) elapses."""
        images = [Path(p) for p in images]
        inputs, ignored = resolve_inputs(images, views)
        used = [path for _, path in inputs]
        start = self._clock()
        deadline = start + self.timeout_s

        tokens = [(view, self.upload(path)) for view, path in inputs]
        upload_s = self._clock() - start

        task_type, request = self.build_request(tokens, seed)
        task_id, create_attempts = self.create_task(task_type, request)
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
        url = output.get("model_url")
        if not url:
            raise TripoError(f"La tarea Tripo {task_id} no devolvió model_url", task)
        download_start = self._clock()
        glb = self.download(url, dst_glb)
        seconds = self._clock() - start

        credits_estimated = self.settings.estimated_credits()
        cost_usd = self.settings.estimated_cost_usd()
        consumed = task.get("credits_consumed")
        meta: dict[str, Any] = {
            "provider": "tripo",
            "api": "v3",
            "task_id": task_id,
            "task_type": task_type,
            "endpoint": ENDPOINTS[task_type],
            "model_version": self.settings.model_version,
            "settings": self.settings.as_dict(),
            "seed": seed,
            "images": [str(p) for p in used],
            "views": {view: str(path) for view, path in inputs if view is not None} or None,
            "images_ignored": [str(p) for p in ignored],
            "request": request,
            "create_attempts": create_attempts,
            "status_history": history,
            "final_status": task,
            "credits_estimated": credits_estimated,
            "credits_consumed": consumed,
            "credits_consumed_usd": (
                round(float(consumed) * USD_PER_CREDIT, 4) if consumed is not None else None
            ),
            "cost_usd": cost_usd,
            "cost_source": "pricing table (credits_estimated x USD_PER_CREDIT)",
            "timings": {
                "upload_s": upload_s,
                "task_s": task_s,
                "download_s": self._clock() - download_start,
                "total_s": seconds,
            },
        }
        return GenerationOutcome(glb_path=glb, cost_usd=cost_usd, seconds=seconds, meta=meta)
