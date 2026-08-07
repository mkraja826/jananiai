import os
from uuid import uuid4

import httpx
import pytest

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
PUBLISHABLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY")
SERVICE_ROLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY")
USER_A_ID = os.getenv("JANANI_STAGING_USER_A_ID")
USER_A_TOKEN = os.getenv("JANANI_STAGING_USER_A_TOKEN")
USER_B_ID = os.getenv("JANANI_STAGING_USER_B_ID")
USER_B_TOKEN = os.getenv("JANANI_STAGING_USER_B_TOKEN")

_REQUIRED = [
    SUPABASE_URL,
    PUBLISHABLE_KEY,
    SERVICE_ROLE_KEY,
    USER_A_ID,
    USER_A_TOKEN,
    USER_B_ID,
    USER_B_TOKEN,
]

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not all(_REQUIRED),
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


def service_headers(*, prefer: str | None = None) -> dict[str, str]:
    key = SERVICE_ROLE_KEY or ""
    result = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        result["Prefer"] = prefer
    return result


def rest_url(path: str) -> str:
    assert SUPABASE_URL is not None
    return f"{SUPABASE_URL}/rest/v1/{path}"


def assert_denied(response: httpx.Response) -> None:
    assert response.status_code in {400, 401, 403, 404}, response.text


def create_episode(token: str, user_id: str) -> str:
    episode_id = str(uuid4())
    response = httpx.post(
        rest_url("pregnancies"),
        headers=headers(token, prefer="return=representation"),
        json={
            "id": episode_id,
            "user_id": user_id,
            "gestational_week": 20,
            "dating_source": "unknown",
            "synthetic": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    return episode_id


def create_attachment(user_id: str, pregnancy_id: str) -> str:
    attachment_id = str(uuid4())
    response = httpx.post(
        rest_url("attachment_records"),
        headers=service_headers(prefer="return=representation"),
        json={
            "id": attachment_id,
            "user_id": user_id,
            "pregnancy_id": pregnancy_id,
            "kind": "lab_report",
            "mime_type": "application/pdf",
            "storage_object_path": f"{user_id}/fixtures/{attachment_id}.pdf",
            "display_label": "Synthetic report",
            "capture_source": "file_upload",
            "file_size_bytes": 1234,
            "content_sha256": "a" * 64,
            "integrity_status": "verified",
            "integrity_verified_at": "2026-08-07T10:00:00Z",
            "synthetic": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    return attachment_id


def test_structured_timeline_records_are_owner_scoped_and_append_only() -> None:
    assert USER_A_TOKEN and USER_B_TOKEN and USER_A_ID and USER_B_ID

    pregnancy_a = create_episode(USER_A_TOKEN, USER_A_ID)
    attachment_a = create_attachment(USER_A_ID, pregnancy_a)

    observation_id = str(uuid4())
    observation = httpx.post(
        rest_url("pregnancy_observations"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": observation_id,
            "user_id": USER_A_ID,
            "pregnancy_id": pregnancy_a,
            "kind": "lab_result",
            "observed_at": "2026-08-07T10:00:00Z",
            "source": "document_confirmed",
            "confirmed": True,
            "label": "Synthetic analyte",
            "value_text": "4.2",
            "unit": "synthetic-unit",
            "source_attachment_id": attachment_a,
            "synthetic": True,
        },
        timeout=20,
    )
    observation.raise_for_status()

    encounter_id = str(uuid4())
    encounter = httpx.post(
        rest_url("pregnancy_encounters"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": encounter_id,
            "user_id": USER_A_ID,
            "pregnancy_id": pregnancy_a,
            "occurred_at": "2026-08-07T11:00:00Z",
            "encounter_type": "routine_visit",
            "summary": "Synthetic encounter",
            "source": "user_entered",
            "confirmed": False,
            "synthetic": True,
        },
        timeout=20,
    )
    encounter.raise_for_status()

    cross_observation_read = httpx.get(
        rest_url("pregnancy_observations"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "id": f"eq.{observation_id}"},
        timeout=20,
    )
    cross_observation_read.raise_for_status()
    assert cross_observation_read.json() == []

    cross_encounter_read = httpx.get(
        rest_url("pregnancy_encounters"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "id": f"eq.{encounter_id}"},
        timeout=20,
    )
    cross_encounter_read.raise_for_status()
    assert cross_encounter_read.json() == []

    cross_insert = httpx.post(
        rest_url("pregnancy_observations"),
        headers=headers(USER_B_TOKEN),
        json={
            "id": str(uuid4()),
            "user_id": USER_B_ID,
            "pregnancy_id": pregnancy_a,
            "kind": "weight",
            "observed_at": "2026-08-07T12:00:00Z",
            "source": "user_entered",
            "weight_kg": 60,
            "synthetic": True,
        },
        timeout=20,
    )
    assert_denied(cross_insert)

    update = httpx.patch(
        rest_url("pregnancy_observations"),
        headers=headers(USER_A_TOKEN),
        params={"id": f"eq.{observation_id}"},
        json={"value_text": "changed"},
        timeout=20,
    )
    assert_denied(update)

    delete = httpx.delete(
        rest_url("pregnancy_encounters"),
        headers=headers(USER_A_TOKEN),
        params={"id": f"eq.{encounter_id}"},
        timeout=20,
    )
    assert_denied(delete)

    superseding = httpx.post(
        rest_url("pregnancy_observations"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": str(uuid4()),
            "user_id": USER_A_ID,
            "pregnancy_id": pregnancy_a,
            "kind": "lab_result",
            "observed_at": "2026-08-07T12:30:00Z",
            "source": "user_entered",
            "confirmed": False,
            "label": "Synthetic analyte",
            "value_text": "4.3",
            "unit": "synthetic-unit",
            "supersedes_observation_id": observation_id,
            "synthetic": True,
        },
        timeout=20,
    )
    superseding.raise_for_status()
