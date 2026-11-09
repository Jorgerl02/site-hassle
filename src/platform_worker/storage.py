"""Supabase Storage access with the service role (buckets of Task 1)."""

from __future__ import annotations

from pathlib import Path

import httpx

from platform_worker.db import service_headers

REQUEST_TIMEOUT_S = 300.0  # GLB/USDZ uploads of a few MB

CONTENT_TYPES: dict[str, str] = {
    ".glb": "model/gltf-binary",
    ".usdz": "model/vnd.usdz+zip",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class StorageError(RuntimeError):
    """Storage answered with an error status."""


def content_type_for(path: Path | str) -> str:
    return CONTENT_TYPES.get(Path(path).suffix.lower(), "application/octet-stream")


class Storage:
    """``download``/``upload`` of single objects. ``client`` is injectable for tests."""

    def __init__(self, url: str, service_key: str, *, client: httpx.Client | None = None) -> None:
        if not url or not service_key:
            raise ValueError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        self.base = f"{url.rstrip('/')}/storage/v1"
        self._headers = service_headers(service_key)
        self._http = client or httpx.Client(timeout=REQUEST_TIMEOUT_S)

    def close(self) -> None:
        self._http.close()

    def object_url(self, bucket: str, path: str) -> str:
        return f"{self.base}/object/{bucket}/{path.lstrip('/')}"

    def download(self, bucket: str, path: str, dst: Path) -> Path:
        response = self._http.get(self.object_url(bucket, path), headers=self._headers)
        if response.is_error:
            raise StorageError(
                f"No se pudo descargar {bucket}/{path} ({response.status_code}): "
                f"{response.text[:300]}"
            )
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(response.content)
        return dst

    def upload(self, bucket: str, path: str, src: Path, content_type: str | None = None) -> str:
        """Upload (overwriting) ``src`` to ``bucket/path``; returns ``path``."""
        src = Path(src)
        response = self._http.post(
            self.object_url(bucket, path),
            content=src.read_bytes(),
            headers={
                **self._headers,
                "Content-Type": content_type or content_type_for(src),
                "x-upsert": "true",
            },
        )
        if response.is_error:
            raise StorageError(
                f"No se pudo subir {bucket}/{path} ({response.status_code}): {response.text[:300]}"
            )
        return path
