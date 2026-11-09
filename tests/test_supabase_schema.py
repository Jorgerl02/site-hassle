"""Schema, SQL functions, RLS and Storage policies of the hosted Supabase project.

These tests talk to the real project (there is no local Supabase): PostgREST `rpc/...`,
`auth/v1/admin/users` and Storage. They are skipped when no service role key is available
in `platform/.env.local` or in the environment. Every user is created as `test_*` and
deleted at teardown; pieces, ledger rows and purchases go with it (ON DELETE CASCADE).
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[1] / "platform" / ".env.local"


def _load_env() -> dict[str, str]:
    values = {k: v for k, v in dotenv_values(ENV_FILE).items() if v} if ENV_FILE.exists() else {}
    for key in (
        "NEXT_PUBLIC_SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


ENV = _load_env()
URL = ENV.get("NEXT_PUBLIC_SUPABASE_URL", "https://oyntcaxzskzntiyzxquy.supabase.co").rstrip("/")
ANON = ENV.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
SERVICE = ENV.get("SUPABASE_SERVICE_ROLE_KEY", "")

pytestmark = pytest.mark.skipif(
    not (SERVICE and ANON), reason="SUPABASE_SERVICE_ROLE_KEY / anon key not available"
)

PASSWORD = "test-" + uuid.uuid4().hex


def _headers(token: str, apikey: str) -> dict[str, str]:
    return {"apikey": apikey, "Authorization": f"Bearer {token}"}


@dataclass
class User:
    id: str
    email: str
    token: str
    client: httpx.Client  # authenticated as this user (anon key + user JWT)


@pytest.fixture(scope="module")
def svc() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=URL, headers=_headers(SERVICE, SERVICE), timeout=30) as client:
        yield client


def _create_user(svc: httpx.Client, label: str) -> User:
    email = f"test_{label}_{uuid.uuid4().hex[:10]}@site-hassle.test"
    r = svc.post(
        "/auth/v1/admin/users",
        json={
            "email": email,
            "password": PASSWORD,
            "email_confirm": True,
            "user_metadata": {"attribution": {"utm_source": "test", "ref": label}},
        },
    )
    assert r.status_code in (200, 201), r.text
    user_id = r.json()["id"]
    for wait in (0, 5, 15, 30):  # Auth rate-limits password sign-ins per IP
        time.sleep(wait)
        r = httpx.post(
            f"{URL}/auth/v1/token?grant_type=password",
            headers={"apikey": ANON},
            json={"email": email, "password": PASSWORD},
            timeout=30,
        )
        if r.status_code != 429:
            break
    if r.status_code != 200:
        svc.delete(f"/auth/v1/admin/users/{user_id}")
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    client = httpx.Client(base_url=URL, headers=_headers(token, ANON), timeout=30)
    return User(id=user_id, email=email, token=token, client=client)


@pytest.fixture(scope="module")
def users(svc: httpx.Client) -> Iterator[dict[str, User]]:
    """Two `test_*` users per run (sign-ins are rate-limited), deleted at the end."""
    created: dict[str, User] = {}
    try:
        for label in ("a", "b"):
            created[label] = _create_user(svc, label)
        yield created
    finally:
        for user in created.values():
            user.client.close()
            svc.delete(f"/auth/v1/admin/users/{user.id}")


def _reset(svc: httpx.Client, user: User) -> User:
    """Each test starts with no pieces and no credits for the user."""
    for table in ("credit_ledger", "purchases", "pieces"):
        svc.delete(f"/rest/v1/{table}?user_id=eq.{user.id}").raise_for_status()
    return user


@pytest.fixture
def a(svc: httpx.Client, users: dict[str, User]) -> User:
    return _reset(svc, users["a"])


@pytest.fixture
def b(svc: httpx.Client, users: dict[str, User]) -> User:
    return _reset(svc, users["b"])


# ---------------------------------------------------------------- helpers


def rpc(client: httpx.Client, name: str, **params: Any) -> httpx.Response:
    return client.post(f"/rest/v1/rpc/{name}", json=params)


def error_message(r: httpx.Response) -> str:
    try:
        return r.json().get("message", "")
    except ValueError:
        return r.text


def insert_piece(svc: httpx.Client, user_id: str, **fields: Any) -> dict[str, Any]:
    row = {
        "user_id": user_id,
        "name": "test_mesa",
        "kind": "mesa",
        "width_cm": 120,
        "height_cm": 75,
        "depth_cm": 60,
        **fields,
    }
    r = svc.post("/rest/v1/pieces", json=row, headers={"Prefer": "return=representation"})
    assert r.status_code == 201, r.text
    return r.json()[0]


def patch_piece(svc: httpx.Client, piece_id: str, **fields: Any) -> dict[str, Any]:
    r = svc.patch(
        f"/rest/v1/pieces?id=eq.{piece_id}",
        json=fields,
        headers={"Prefer": "return=representation"},
    )
    assert r.status_code == 200, r.text
    return r.json()[0]


def get_piece(svc: httpx.Client, piece_id: str) -> dict[str, Any]:
    r = svc.get(f"/rest/v1/pieces?id=eq.{piece_id}")
    assert r.status_code == 200, r.text
    return r.json()[0]


def balance(svc: httpx.Client, user_id: str) -> int:
    r = rpc(svc, "credit_balance", p_user=user_id)
    assert r.status_code == 200, r.text
    return r.json()


def grant(svc: httpx.Client, user_id: str, delta: int, session: str | None) -> httpx.Response:
    return rpc(
        svc, "grant_credits", p_user=user_id, p_delta=delta, p_reason="purchase", p_session=session
    )


def ledger(svc: httpx.Client, user_id: str) -> list[dict[str, Any]]:
    r = svc.get(f"/rest/v1/credit_ledger?user_id=eq.{user_id}&order=created_at")
    assert r.status_code == 200, r.text
    return r.json()


def iso_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


# ---------------------------------------------------------------- profiles


def test_new_user_gets_profile_with_attribution(svc: httpx.Client, a: User) -> None:
    r = a.client.get("/rest/v1/profiles?select=id,email,is_admin,attribution,plan")
    assert r.status_code == 200, r.text
    assert r.json() == [
        {
            "id": a.id,
            "email": a.email,
            "is_admin": False,
            "attribution": {"utm_source": "test", "ref": "a"},
            "plan": None,
        }
    ]
    # A user can never promote himself to admin.
    r = a.client.patch(f"/rest/v1/profiles?id=eq.{a.id}", json={"is_admin": True})
    assert r.status_code in (401, 403), r.text
    r = svc.get(f"/rest/v1/profiles?id=eq.{a.id}&select=is_admin")
    assert r.json() == [{"is_admin": False}]


# ---------------------------------------------------------------- credits and approval


def test_approve_requires_credit_then_consumes_once(svc: httpx.Client, a: User) -> None:
    piece = insert_piece(svc, a.id, status="ready")

    r = rpc(a.client, "approve_piece", p_piece_id=piece["id"])
    assert r.status_code >= 400 and error_message(r) == "insufficient_credits", r.text
    assert get_piece(svc, piece["id"])["status"] == "ready"

    session = f"test_sess_{uuid.uuid4().hex}"
    r = grant(svc, a.id, 1, session)
    assert r.status_code == 200 and r.json() == 1, r.text

    r = rpc(a.client, "approve_piece", p_piece_id=piece["id"])
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "balance": 0}
    assert get_piece(svc, piece["id"])["status"] == "approved"

    r = rpc(a.client, "approve_piece", p_piece_id=piece["id"])
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True and r.json()["already"] is True
    assert balance(svc, a.id) == 0

    consumes = [row for row in ledger(svc, a.id) if row["reason"] == "consume"]
    assert len(consumes) == 1
    assert consumes[0]["delta"] == -1 and consumes[0]["piece_id"] == piece["id"]


def test_approve_rejects_wrong_state(svc: httpx.Client, a: User) -> None:
    grant(svc, a.id, 1, None)
    piece = insert_piece(svc, a.id, status="review")
    r = rpc(a.client, "approve_piece", p_piece_id=piece["id"])
    assert r.status_code >= 400 and error_message(r) == "invalid_state", r.text
    assert balance(svc, a.id) == 1


def test_grant_credits_is_idempotent_by_session(svc: httpx.Client, a: User) -> None:
    session = f"test_sess_{uuid.uuid4().hex}"
    assert grant(svc, a.id, 10, session).json() == 10
    r = grant(svc, a.id, 10, session)
    assert r.status_code == 200 and r.json() == 10, r.text
    assert len(ledger(svc, a.id)) == 1
    # Without a session id grants always add (admin gifts).
    assert grant(svc, a.id, 1, None).json() == 11
    assert grant(svc, a.id, 1, None).json() == 12


def test_grant_and_claim_are_service_role_only(a: User) -> None:
    r = grant(a.client, a.id, 100, None)
    assert r.status_code in (401, 403, 404), r.text
    r = rpc(a.client, "claim_next_piece")
    assert r.status_code in (401, 403, 404), r.text
    r = rpc(a.client, "requeue_stale_pieces")
    assert r.status_code in (401, 403, 404), r.text


def test_concurrent_approve_of_same_piece_consumes_one_credit(svc: httpx.Client, a: User) -> None:
    grant(svc, a.id, 2, None)
    piece = insert_piece(svc, a.id, status="ready")

    async def both() -> list[httpx.Response]:
        async with httpx.AsyncClient(
            base_url=URL, headers=_headers(a.token, ANON), timeout=30
        ) as client:
            calls = [
                client.post("/rest/v1/rpc/approve_piece", json={"p_piece_id": piece["id"]})
                for _ in range(2)
            ]
            return list(await asyncio.gather(*calls))

    results = asyncio.run(both())
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert sorted(bool(r.json().get("already")) for r in results) == [False, True]
    assert balance(svc, a.id) == 1
    assert get_piece(svc, piece["id"])["status"] == "approved"


def test_concurrent_approve_of_two_pieces_with_one_credit(svc: httpx.Client, a: User) -> None:
    grant(svc, a.id, 1, None)
    pieces = [insert_piece(svc, a.id, status="ready") for _ in range(2)]

    async def both() -> list[httpx.Response]:
        async with httpx.AsyncClient(
            base_url=URL, headers=_headers(a.token, ANON), timeout=30
        ) as client:
            calls = [
                client.post("/rest/v1/rpc/approve_piece", json={"p_piece_id": p["id"]})
                for p in pieces
            ]
            return list(await asyncio.gather(*calls))

    results = asyncio.run(both())
    ok = [r for r in results if r.status_code == 200]
    failed = [r for r in results if r.status_code != 200]
    assert len(ok) == 1 and len(failed) == 1, [r.text for r in results]
    assert error_message(failed[0]) == "insufficient_credits"
    assert balance(svc, a.id) == 0


# ---------------------------------------------------------------- daily limit


def test_fourth_piece_of_the_day_hits_daily_limit(svc: httpx.Client, a: User) -> None:
    for n in range(3):
        r = a.client.post(
            "/rest/v1/pieces",
            json={
                "name": f"test_{n}",
                "kind": "mesita",
                "width_cm": 50,
                "height_cm": 45,
                "depth_cm": 40,
            },
            headers={"Prefer": "return=representation"},
        )
        assert r.status_code == 201, r.text
        row = r.json()[0]
        assert row["user_id"] == a.id and row["status"] == "queued" and row["attempt"] == 1

    r = rpc(a.client, "pieces_created_today", p_user=a.id)
    assert r.status_code == 200 and r.json() == 3, r.text

    r = a.client.post(
        "/rest/v1/pieces",
        json={"name": "test_4", "kind": "mesita", "width_cm": 50, "height_cm": 45, "depth_cm": 40},
    )
    assert r.status_code >= 400 and error_message(r) == "daily_limit", r.text

    # The worker/admin (service role) is not limited.
    insert_piece(svc, a.id)


def test_client_insert_must_be_own_and_queued(a: User, b: User) -> None:
    base = {"name": "test_x", "kind": "mesa", "width_cm": 1, "height_cm": 1, "depth_cm": 1}
    r = a.client.post("/rest/v1/pieces", json={**base, "user_id": b.id})
    assert r.status_code in (401, 403), r.text
    r = a.client.post("/rest/v1/pieces", json={**base, "status": "ready"})
    assert r.status_code in (401, 403), r.text


def test_client_inserts_photos_only_for_own_queued_piece(
    svc: httpx.Client, a: User, b: User
) -> None:
    queued = insert_piece(svc, a.id)
    ready = insert_piece(svc, a.id, status="ready")

    def photo(piece: dict[str, Any], owner: str) -> dict[str, Any]:
        return {"piece_id": piece["id"], "storage_path": f"{owner}/{piece['id']}/1.jpg"}

    r = a.client.post("/rest/v1/piece_photos", json={**photo(queued, a.id), "position": 1})
    assert r.status_code == 201, r.text
    r = a.client.post("/rest/v1/piece_photos", json=photo(ready, a.id))
    assert r.status_code in (401, 403), r.text
    r = a.client.post("/rest/v1/piece_photos", json=photo(queued, b.id))  # wrong prefix
    assert r.status_code in (401, 403), r.text
    r = b.client.post("/rest/v1/piece_photos", json=photo(queued, b.id))  # not his piece
    assert r.status_code in (401, 403), r.text


# ---------------------------------------------------------------- versions and rejection


def test_request_new_version_until_max_versions(svc: httpx.Client, a: User) -> None:
    piece = insert_piece(svc, a.id, status="ready")
    for expected_attempt in (2, 3):
        r = rpc(a.client, "request_new_version", p_piece_id=piece["id"])
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "queued" and r.json()["attempt"] == expected_attempt
        patch_piece(svc, piece["id"], status="ready")
    r = rpc(a.client, "request_new_version", p_piece_id=piece["id"])
    assert r.status_code >= 400 and error_message(r) == "max_versions", r.text
    assert get_piece(svc, piece["id"])["status"] == "ready"


def test_reject_piece(svc: httpx.Client, a: User) -> None:
    piece = insert_piece(svc, a.id, status="ready")
    r = rpc(a.client, "reject_piece", p_piece_id=piece["id"], p_reason="No se parece")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected" and r.json()["reject_reason"] == "No se parece"
    r = rpc(a.client, "reject_piece", p_piece_id=piece["id"], p_reason="otra vez")
    assert r.status_code >= 400 and error_message(r) == "invalid_state", r.text


# ---------------------------------------------------------------- worker queue


def test_claim_next_piece_takes_oldest_then_another(svc: httpx.Client, a: User) -> None:
    older = insert_piece(svc, a.id, created_at=iso_ago(60 * 24 * 365))
    newer = insert_piece(svc, a.id, created_at=iso_ago(60 * 24 * 364))
    ours = {older["id"], newer["id"]}

    claimed: list[str] = []
    foreign: list[str] = []
    for _ in range(50):  # other queued pieces in the project may be older than ours
        r = rpc(svc, "claim_next_piece")
        assert r.status_code == 200, r.text
        row = r.json()
        if not row or row.get("id") is None:
            break
        assert row["status"] == "generating" and row["claimed_at"] is not None
        if row["id"] in ours:
            claimed.append(row["id"])
            if len(claimed) == 2:
                break
        else:
            foreign.append(row["id"])
    for piece_id in foreign:  # put back what was not ours
        patch_piece(svc, piece_id, status="queued", claimed_at=None)

    assert claimed == [older["id"], newer["id"]]


def test_requeue_stale_pieces(svc: httpx.Client, a: User) -> None:
    stale = insert_piece(svc, a.id, status="generating", claimed_at=iso_ago(40))
    fresh = insert_piece(svc, a.id, status="generating", claimed_at=iso_ago(5))
    r = rpc(svc, "requeue_stale_pieces")
    assert r.status_code == 200 and r.json() >= 1, r.text
    row = get_piece(svc, stale["id"])
    assert row["status"] == "queued" and row["claimed_at"] is None
    assert get_piece(svc, fresh["id"])["status"] == "generating"


def test_updated_at_is_maintained(svc: httpx.Client, a: User) -> None:
    piece = insert_piece(svc, a.id)
    updated = patch_piece(svc, piece["id"], status="generating", claimed_at=iso_ago(0))
    assert updated["updated_at"] is not None
    assert updated["updated_at"] >= piece["created_at"]


# ---------------------------------------------------------------- RLS between users


def test_user_cannot_see_or_act_on_another_users_piece(svc: httpx.Client, a: User, b: User) -> None:
    grant(svc, b.id, 5, None)
    grant(svc, a.id, 3, None)
    piece = insert_piece(svc, a.id, status="ready")
    svc.post(
        "/rest/v1/piece_photos",
        json={
            "piece_id": piece["id"],
            "storage_path": f"{a.id}/{piece['id']}/1.jpg",
            "position": 1,
        },
    ).raise_for_status()

    assert b.client.get(f"/rest/v1/pieces?id=eq.{piece['id']}").json() == []
    assert b.client.get(f"/rest/v1/piece_photos?piece_id=eq.{piece['id']}").json() == []
    assert b.client.get(f"/rest/v1/credit_ledger?user_id=eq.{a.id}").json() == []
    assert len(a.client.get(f"/rest/v1/pieces?id=eq.{piece['id']}").json()) == 1

    for name, params in (
        ("approve_piece", {"p_piece_id": piece["id"]}),
        ("request_new_version", {"p_piece_id": piece["id"]}),
        ("reject_piece", {"p_piece_id": piece["id"], "p_reason": "x"}),
    ):
        r = rpc(b.client, name, **params)
        assert r.status_code >= 400 and error_message(r) == "not_found", (name, r.text)

    r = rpc(b.client, "credit_balance", p_user=a.id)
    assert r.status_code >= 400, r.text
    assert rpc(b.client, "credit_balance", p_user=b.id).json() == 5

    # The client cannot change a piece directly (only through the functions above).
    r = a.client.patch(f"/rest/v1/pieces?id=eq.{piece['id']}", json={"status": "approved"})
    assert r.status_code in (200, 204, 401, 403)
    assert get_piece(svc, piece["id"])["status"] == "ready"
    assert balance(svc, b.id) == 5 and balance(svc, a.id) == 3


def test_models_hidden_until_ready_and_admin_queue_is_service_only(
    svc: httpx.Client, a: User
) -> None:
    piece = insert_piece(svc, a.id, status="review")
    svc.post(
        "/rest/v1/piece_models",
        json={
            "piece_id": piece["id"],
            "attempt": 1,
            "provider": "parametric",
            "candidate": 0,
            "preview_path": f"{piece['id']}/1/model_preview.glb",
            "max_error": 0.4,
        },
    ).raise_for_status()

    assert a.client.get(f"/rest/v1/piece_models?piece_id=eq.{piece['id']}").json() == []
    r = svc.get(f"/rest/v1/admin_review_queue?id=eq.{piece['id']}")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1 and rows[0]["provider"] == "parametric"
    assert rows[0]["preview_path"] == f"{piece['id']}/1/model_preview.glb"

    r = a.client.get("/rest/v1/admin_review_queue")
    assert r.status_code in (401, 403), r.text

    patch_piece(svc, piece["id"], status="ready")
    assert len(a.client.get(f"/rest/v1/piece_models?piece_id=eq.{piece['id']}").json()) == 1


# ---------------------------------------------------------------- Storage


def test_photos_bucket_is_private_per_user_prefix(svc: httpx.Client, a: User, b: User) -> None:
    piece_id = str(uuid.uuid4())
    own = f"/storage/v1/object/photos/{a.id}/{piece_id}/1.jpg"
    other = f"/storage/v1/object/photos/{b.id}/{piece_id}/1.jpg"
    jpeg = {"Content-Type": "image/jpeg"}
    try:
        r = a.client.post(own, content=b"\xff\xd8\xff\xe0test", headers=jpeg)
        assert r.status_code == 200, r.text
        r = a.client.post(other, content=b"\xff\xd8\xff\xe0test", headers=jpeg)
        assert r.status_code >= 400, r.text
        assert (
            a.client.get(
                f"/storage/v1/object/authenticated/photos/{a.id}/{piece_id}/1.jpg"
            ).status_code
            == 200
        )
        r = b.client.get(f"/storage/v1/object/authenticated/photos/{a.id}/{piece_id}/1.jpg")
        assert r.status_code >= 400, r.text
        # models: only the service role writes.
        r = a.client.post(f"/storage/v1/object/models/{piece_id}/1/model_web.glb", content=b"x")
        assert r.status_code >= 400, r.text
    finally:
        svc.request(
            "DELETE",
            "/storage/v1/object/photos",
            json={"prefixes": [f"{a.id}/{piece_id}/1.jpg", f"{b.id}/{piece_id}/1.jpg"]},
        )


def test_buckets_exist_with_expected_visibility(svc: httpx.Client) -> None:
    r = svc.get("/storage/v1/bucket")
    assert r.status_code == 200, r.text
    public = {b["id"]: b["public"] for b in r.json()}
    assert public.get("photos") is False
    assert public.get("previews") is True
    assert public.get("models") is False
    assert public.get("renders") is False
