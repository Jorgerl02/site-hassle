"""Vision-language client (Claude via the Anthropic SDK) that returns parsed JSON."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anthropic

from harness.core import pricing

DEFAULT_MODEL = "claude-sonnet-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_RETRYABLE_STATUS = {408, 409, 429}


class VLMError(RuntimeError):
    """The model refused, or no valid JSON was obtained after all attempts."""


def _image_block(path: Path) -> dict[str, Any]:
    media_type = _MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ValueError(f"Formato de imagen no soportado: {path}")
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def _extract_json(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("la respuesta no contiene un objeto JSON")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("el JSON de la respuesta no es un objeto")
    return value


def _is_retryable(exc: anthropic.APIError) -> bool:
    if isinstance(exc, anthropic.APIConnectionError):  # includes APITimeoutError
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in _RETRYABLE_STATUS or exc.status_code >= 500
    return False


def token_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * pricing.ANTHROPIC_INPUT_USD_PER_MTOK
        + output_tokens * pricing.ANTHROPIC_OUTPUT_USD_PER_MTOK
    ) / 1_000_000


class VLMClient:
    """``ask_json`` sends images + prompt and returns the parsed JSON object.

    Retries (exponential backoff) on transient API errors and on unparsable JSON.
    Every attempt's token cost is recorded in ``calls`` and ``total_cost_usd``.
    Pass ``client`` to inject a preconfigured ``anthropic.Anthropic`` (e.g. in tests).

    ``allow_fallback`` (default False) opts in to server-side fallback models. The judge must
    keep it off so every score comes from the requested model; the router may enable it.
    The model that actually answered is in ``calls[i]["model"]`` / ``last_model``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        client: anthropic.Anthropic | None = None,
        max_attempts: int = 3,
        backoff_s: float = 2.0,
        max_tokens: int = 16000,
        sleep: Callable[[float], None] = time.sleep,
        allow_fallback: bool = False,
    ) -> None:
        # SDK retries disabled: retry/backoff is owned here so JSON failures are retried too.
        self._client = client or anthropic.Anthropic(api_key=api_key, max_retries=0)
        self.model = model
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.max_tokens = max_tokens
        self.allow_fallback = allow_fallback
        self._sleep = sleep
        self.calls: list[dict[str, Any]] = []
        self.total_cost_usd = 0.0

    @property
    def last_model(self) -> str | None:
        return self.calls[-1]["model"] if self.calls else None

    @property
    def last_cost_usd(self) -> float:
        return self.calls[-1]["cost_usd"] if self.calls else 0.0

    def ask_json(self, prompt: str, images: list[Path], schema_hint: str) -> dict[str, Any]:
        content: list[dict[str, Any]] = [_image_block(Path(p)) for p in images]
        content.append(
            {
                "type": "text",
                "text": f"{prompt}\n\nResponde únicamente con un objeto JSON válido, sin texto "
                f"adicional, que siga este esquema:\n{schema_hint}",
            }
        )

        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            if attempt:
                self._sleep(self.backoff_s * 2 ** (attempt - 1))
            try:
                extra: dict[str, Any] = (
                    {"betas": [FALLBACK_BETA], "fallbacks": "default"}
                    if self.allow_fallback
                    else {}
                )
                response = self._client.beta.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{"role": "user", "content": content}],
                    **extra,
                )
            except anthropic.APIError as exc:
                if not _is_retryable(exc):
                    raise
                last_error = exc
                continue

            self._record(response)
            if response.stop_reason == "refusal":
                raise VLMError(f"El modelo rechazó la petición: {response.stop_details}")
            text = "".join(b.text for b in response.content if b.type == "text")
            try:
                return _extract_json(text)
            except ValueError as exc:  # json.JSONDecodeError is a ValueError
                last_error = exc

        raise VLMError(f"Sin JSON válido tras {self.max_attempts} intentos: {last_error}")

    def _record(self, response: Any) -> None:
        usage = response.usage
        input_tokens = (
            usage.input_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0)
        )
        cost = token_cost_usd(input_tokens, usage.output_tokens)
        self.calls.append(
            {
                "model": response.model,
                "input_tokens": input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_usd": cost,
            }
        )
        self.total_cost_usd += cost
