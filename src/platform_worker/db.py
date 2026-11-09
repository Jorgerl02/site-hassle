"""PostgREST access with the Supabase service role (tables and SQL functions of Task 1)."""

from __future__ import annotations

from typing import Any

import httpx

REQUEST_TIMEOUT_S = 60.0


class WorkerDBError(RuntimeError):
    """PostgREST answered with an error status."""


def service_headers(service_key: str) -> dict[str, str]:
    return {"apikey": service_key, "Authorization": f"Bearer {service_key}"}


def _raise_for(response: httpx.Response, what: str) -> None:
    if response.is_error:
        raise WorkerDBError(
            f"Supabase respondió {response.status_code} en {what}: {response.text[:500]}"
        )


class WorkerDB:
    """Thin PostgREST client. ``client`` is injectable for tests."""

    def __init__(self, url: str, service_key: str, *, client: httpx.Client | None = None) -> None:
        if not url or not service_key:
            raise ValueError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        self.rest = f"{url.rstrip('/')}/rest/v1"
        self._headers = service_headers(service_key)
        self._http = client or httpx.Client(timeout=REQUEST_TIMEOUT_S)

    def close(self) -> None:
        self._http.close()

    def _rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = self._http.post(f"{self.rest}/rpc/{name}", json=payload, headers=self._headers)
        _raise_for(response, f"rpc/{name}")
        return response.json() if response.content else None

    def claim_next(self) -> dict[str, Any] | None:
        """Atomically move the oldest ``queued`` piece to ``generating`` and return it.

        ``claim_next_piece()`` returns a single ``pieces`` composite: PostgREST sends it as an
        object (all fields null when nothing was claimed), ``null`` or a one-row array."""
        data = self._rpc("claim_next_piece", {})
        if isinstance(data, list):
            data = data[0] if data else None
        if not data or data.get("id") is None:
            return None
        return data

    def requeue_stale(self, minutes: int = 30) -> int:
        """``generating`` pieces claimed more than ``minutes`` ago go back to ``queued``."""
        data = self._rpc("requeue_stale_pieces", {"p_minutes": minutes})
        return int(data or 0)

    def update_piece(self, piece_id: str, **fields: Any) -> dict[str, Any]:
        response = self._http.patch(
            f"{self.rest}/pieces",
            params={"id": f"eq.{piece_id}"},
            json=fields,
            headers={**self._headers, "Prefer": "return=representation"},
        )
        _raise_for(response, "pieces (update)")
        rows = response.json()
        return rows[0] if rows else {}

    def get_piece(self, piece_id: str) -> dict[str, Any] | None:
        response = self._http.get(
            f"{self.rest}/pieces",
            params={"id": f"eq.{piece_id}", "select": "*"},
            headers=self._headers,
        )
        _raise_for(response, "pieces (select)")
        rows = response.json()
        return rows[0] if rows else None

    def insert_model(self, row: dict[str, Any]) -> dict[str, Any]:
        response = self._http.post(
            f"{self.rest}/piece_models",
            json=row,
            headers={**self._headers, "Prefer": "return=representation"},
        )
        _raise_for(response, "piece_models (insert)")
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else rows

    def delete_models(self, piece_id: str, attempt: int) -> None:
        """Remove the ``piece_models`` rows of one attempt (re-processing starts clean)."""
        response = self._http.delete(
            f"{self.rest}/piece_models",
            params={"piece_id": f"eq.{piece_id}", "attempt": f"eq.{attempt}"},
            headers=self._headers,
        )
        _raise_for(response, "piece_models (delete)")

    def list_photos(self, piece_id: str) -> list[dict[str, Any]]:
        response = self._http.get(
            f"{self.rest}/piece_photos",
            params={"piece_id": f"eq.{piece_id}", "select": "*", "order": "position.asc"},
            headers=self._headers,
        )
        _raise_for(response, "piece_photos (select)")
        return list(response.json())
