import os
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.staging

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
PUBLISHABLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY")
USER_A_TOKEN = os.getenv("JANANI_STAGING_USER_A_TOKEN")
USER_B_TOKEN = os.getenv("JANANI_STAGING_USER_B_TOKEN")

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not all([SUPABASE_URL, PUBLISHABLE_KEY, USER_A_TOKEN, USER_B_TOKEN]),
        reason="Dedicated synthetic Supabase staging credentials are not configured",
    ),
]


def headers(token: str, *, prefer: str | None = None) -> dict[str, str]:
    result = {
        "apikey": PUBLISHABLE_KEY or "",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if prefer:
        result["Prefer"] = prefer
    return result


def user_id(token: str) -> str:
    response = httpx.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers=headers(token),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["id"]


def test_two_users_cannot_cross_read_or_cross_write_pregnancies() -> None:
    assert SUPABASE_URL is not None
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None

    user_a_id = user_id(USER_A_TOKEN)
    pregnancy_id = str(uuid4())
    insert_response = httpx.post(
        f"{SUPABASE_URL}/rest/v1/pregnancies",
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": pregnancy_id,
            "user_id": user_a_id,
            "gestational_week": 20,
            "known_conditions": ["synthetic staging record"],
        },
        timeout=15,
    )
    insert_response.raise_for_status()

    try:
        cross_read = httpx.get(
            f"{SUPABASE_URL}/rest/v1/pregnancies",
            headers=headers(USER_B_TOKEN),
            params={"select": "id", "id": f"eq.{pregnancy_id}"},
            timeout=15,
        )
        cross_read.raise_for_status()
        assert cross_read.json() == []

        cross_write = httpx.post(
            f"{SUPABASE_URL}/rest/v1/pregnancies",
            headers=headers(USER_B_TOKEN),
            json={
                "id": str(uuid4()),
                "user_id": user_a_id,
                "gestational_week": 21,
            },
            timeout=15,
        )
        assert cross_write.status_code in {401, 403}

        internal_write = httpx.post(
            f"{SUPABASE_URL}/rest/v1/context_assembly_events",
            headers=headers(USER_A_TOKEN),
            json={
                "task": "general_question",
                "status": "ready",
                "excluded_item_count": 0,
                "synthetic": True,
            },
            timeout=15,
        )
        assert internal_write.status_code in {401, 403}
    finally:
        cleanup = httpx.delete(
            f"{SUPABASE_URL}/rest/v1/pregnancies",
            headers=headers(USER_A_TOKEN),
            params={"id": f"eq.{pregnancy_id}"},
            timeout=15,
        )
        cleanup.raise_for_status()
