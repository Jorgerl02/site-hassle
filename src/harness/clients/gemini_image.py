"""Gemini image editing ("Nano Banana" family) via the ``google-genai`` SDK.

Docs read 2026-11-08: https://aistudio.google.com/docs/image-generation (redirect target of
https://ai.google.dev/gemini-api/docs/image-generation) and Context7 /googleapis/python-genai.
The current docs use the Interactions API (``client.interactions.create``) with text + base64
image input blocks and return the image in ``interaction.output_image.data`` (base64).
"""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Any

from PIL import Image

from harness.core import pricing

# Docs: "Recommended for all new projects to use Nano Banana 2.1".
DEFAULT_MODEL = "gemini-nano-banana-2.1"
DEFAULT_ASPECT_RATIO = "1:1"
DEFAULT_IMAGE_SIZE = "1K"

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class GeminiImageError(RuntimeError):
    pass


def _mime_type(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")


def _decode(data: str | bytes) -> bytes:
    if isinstance(data, bytes):
        # Raw image bytes start with a known magic; otherwise treat as base64 text.
        if data[:4] in (b"\x89PNG", b"RIFF") or data[:3] == b"\xff\xd8\xff":
            return data
        data = data.decode("ascii")
    return base64.b64decode(data)


class GeminiImageClient:
    """``edit(image, prompt, dst)``: one image + text instruction → one edited image (PNG).

    ``client`` may be any object exposing ``interactions.create(**body)`` (tests inject a stub).
    Every call costs ``pricing.GEMINI_IMAGE_USD`` and is recorded in ``calls``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        client: Any | None = None,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        image_size: str = DEFAULT_IMAGE_SIZE,
    ) -> None:
        if client is None:
            if not api_key:
                raise GeminiImageError("Falta GEMINI_API_KEY para el cliente de imagen de Gemini")
            from google import genai  # heavy import, only when a real client is needed

            client = genai.Client(api_key=api_key)
        self._client = client
        self.model = model
        self.aspect_ratio = aspect_ratio
        self.image_size = image_size
        self.calls: list[dict[str, Any]] = []

    @property
    def total_cost_usd(self) -> float:
        return sum(call["cost_usd"] for call in self.calls)

    def edit(self, image: Path, prompt: str, dst: Path) -> Path:
        image, dst = Path(image), Path(dst)
        start = time.monotonic()
        interaction = self._client.interactions.create(
            model=self.model,
            input=[
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "data": base64.b64encode(image.read_bytes()).decode("ascii"),
                    "mime_type": _mime_type(image),
                },
            ],
            response_format={
                "type": "image",
                "mime_type": "image/png",
                "aspect_ratio": self.aspect_ratio,
                "image_size": self.image_size,
            },
        )
        output = getattr(interaction, "output_image", None)
        data = getattr(output, "data", None) if output is not None else None
        # A call that returns no image is still billed (tokens); record it before failing.
        self.calls.append(
            {
                "model": self.model,
                "src": str(image),
                "dst": str(dst),
                "interaction_id": getattr(interaction, "id", None),
                "cost_usd": pricing.GEMINI_IMAGE_USD,
                "seconds": time.monotonic() - start,
                "ok": bool(data),
            }
        )
        if not data:
            text = getattr(interaction, "output_text", "") or ""
            raise GeminiImageError(f"Gemini no devolvió imagen para {image.name}: {text[:200]}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(_decode(data))) as img:
            img.convert("RGB").save(dst)
        return dst
