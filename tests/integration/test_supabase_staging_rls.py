import os
from uuid import UUID, uuid4

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
    return headers(SERVICE_ROLE_KEY or "", prefer=prefer)


def rest_url(path: str) -> str:
    assert SUPABASE_URL is not None
    return f"{SUPABASE_URL}/rest/v1/{path}"


def user_id(token: str) -> str:
    assert SUPABASE_URL is not None
    response = httpx.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers=headers(token),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["id"]


def insert_pregnancy(token: str, owner_id: str, *, week: int = 20) -> str:
    pregnancy_id = str(uuid4())
    response = httpx.post(
        rest_url("pregnancies"),
        headers=headers(token, prefer="return=representation"),
        json={
            "id": pregnancy_id,
            "user_id": owner_id,
            "gestational_week": week,
            "known_conditions": ["synthetic local RLS record"],
        },
        timeout=20,
    )
    response.raise_for_status()
    return pregnancy_id


def test_tokens_resolve_to_distinct_synthetic_users() -> None:
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None
    assert USER_A_ID is not None
    assert USER_B_ID is not None

    assert user_id(USER_A_TOKEN) == USER_A_ID
    assert user_id(USER_B_TOKEN) == USER_B_ID
    assert USER_A_ID != USER_B_ID


def test_two_users_cannot_cross_read_or_cross_write_pregnancies() -> None:
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None
    assert USER_A_ID is not None

    pregnancy_id = insert_pregnancy(USER_A_TOKEN, USER_A_ID)

    cross_read = httpx.get(
        rest_url("pregnancies"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "id": f"eq.{pregnancy_id}"},
        timeout=20,
    )
    cross_read.raise_for_status()
    assert cross_read.json() == []

    cross_write = httpx.post(
        rest_url("pregnancies"),
        headers=headers(USER_B_TOKEN),
        json={
            "id": str(uuid4()),
            "user_id": USER_A_ID,
            "gestational_week": 21,
        },
        timeout=20,
    )
    assert cross_write.status_code in {401, 403}


def test_profile_isolation_and_append_only_consent() -> None:
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None
    assert USER_A_ID is not None

    profile_response = httpx.post(
        rest_url("user_health_profiles"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "user_id": USER_A_ID,
            "preferred_language": "en",
            "dietary_preference": "vegetarian",
            "allergies": ["synthetic allergy"],
        },
        timeout=20,
    )
    profile_response.raise_for_status()

    cross_read = httpx.get(
        rest_url("user_health_profiles"),
        headers=headers(USER_B_TOKEN),
        params={"select": "user_id", "user_id": f"eq.{USER_A_ID}"},
        timeout=20,
    )
    cross_read.raise_for_status()
    assert cross_read.json() == []

    consent_id = str(uuid4())
    consent_response = httpx.post(
        rest_url("consent_events"),
        headers=headers(USER_A_TOKEN, prefer="return=representation"),
        json={
            "id": consent_id,
            "user_id": USER_A_ID,
            "purpose": "ai_processing",
            "status": "granted",
            "policy_version": "synthetic-local-v1",
            "metadata": {"synthetic": True},
        },
        timeout=20,
    )
    consent_response.raise_for_status()

    update_response = httpx.patch(
        rest_url("consent_events"),
        headers=headers(USER_A_TOKEN),
        params={"id": f"eq.{consent_id}"},
        json={"status": "revoked"},
        timeout=20,
    )
    assert update_response.status_code in {401, 403}

    delete_response = httpx.delete(
        rest_url("consent_events"),
        headers=headers(USER_A_TOKEN),
        params={"id": f"eq.{consent_id}"},
        timeout=20,
    )
    assert delete_response.status_code in {401, 403}


def test_related_records_cannot_link_to_another_users_pregnancy() -> None:
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None
    assert USER_A_ID is not None
    assert USER_B_ID is not None

    pregnancy_id = insert_pregnancy(USER_A_TOKEN, USER_A_ID, week=22)

    medication_response = httpx.post(
        rest_url("medication_records"),
        headers=headers(USER_B_TOKEN),
        json={
            "user_id": USER_B_ID,
            "pregnancy_id": pregnancy_id,
            "name": "Synthetic medication",
            "source": "user_entered",
            "confirmed": True,
        },
        timeout=20,
    )
    assert medication_response.status_code in {401, 403}

    appointment_response = httpx.post(
        rest_url("appointment_records"),
        headers=headers(USER_B_TOKEN),
        json={
            "user_id": USER_B_ID,
            "pregnancy_id": pregnancy_id,
            "scheduled_at": "2026-08-10T10:00:00Z",
            "purpose": "Synthetic appointment",
        },
        timeout=20,
    )
    assert appointment_response.status_code in {401, 403}

    attachment_response = httpx.post(
        rest_url("attachment_records"),
        headers=headers(USER_B_TOKEN),
        json={
            "user_id": USER_B_ID,
            "pregnancy_id": pregnancy_id,
            "kind": "lab_report",
            "mime_type": "application/pdf",
            "storage_object_path": f"{USER_A_ID}/cross-user.pdf",
        },
        timeout=20,
    )
    assert attachment_response.status_code in {401, 403}


def test_internal_tables_reject_direct_authenticated_writes() -> None:
    assert USER_A_TOKEN is not None
    assert USER_A_ID is not None

    pregnancy_id = insert_pregnancy(USER_A_TOKEN, USER_A_ID, week=23)
    attachment_id = str(uuid4())
    attachment_response = httpx.post(
        rest_url("attachment_records"),
        headers=headers(USER_A_TOKEN),
        json={
            "id": attachment_id,
            "user_id": USER_A_ID,
            "pregnancy_id": pregnancy_id,
            "kind": "lab_report",
            "mime_type": "application/pdf",
            "storage_object_path": f"{USER_A_ID}/{attachment_id}.pdf",
        },
        timeout=20,
    )
    attachment_response.raise_for_status()

    attempts = [
        (
            "context_assembly_events",
            {
                "task": "general_question",
                "status": "ready",
                "excluded_item_count": 0,
                "synthetic": True,
            },
        ),
        (
            "safety_audit_events",
            {
                "request_id": str(uuid4()),
                "ruleset_version": "synthetic",
                "severity": "routine",
                "blocks_llm": False,
                "synthetic": True,
            },
        ),
        (
            "attachment_extractions",
            {
                "attachment_id": attachment_id,
                "extractor_name": "synthetic",
                "extractor_version": "1",
                "extracted_text": "Synthetic direct write must fail",
            },
        ),
        (
            "account_deletion_requests",
            {"user_id": USER_A_ID},
        ),
    ]

    for table, payload in attempts:
        response = httpx.post(
            rest_url(table),
            headers=headers(USER_A_TOKEN),
            json=payload,
            timeout=20,
        )
        assert response.status_code in {401, 403}, (table, response.text)


def test_authenticated_audit_rpcs_are_owner_scoped_and_minimal() -> None:
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None

    safety_event_id = str(uuid4())
    safety_response = httpx.post(
        rest_url("rpc/record_janani_safety_event"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_request_id": safety_event_id,
            "p_ruleset_version": "synthetic-local-rules",
            "p_triggered_rule_ids": [],
            "p_severity": "routine",
            "p_blocks_llm": False,
            "p_synthetic": True,
        },
        timeout=20,
    )
    safety_response.raise_for_status()
    UUID(safety_response.json())

    context_event_id = str(uuid4())
    context_response = httpx.post(
        rest_url("rpc/record_janani_context_event"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_event_id": context_event_id,
            "p_task": "general_question",
            "p_status": "ready",
            "p_safety_event_id": safety_event_id,
            "p_selected_medication_ids": [],
            "p_selected_appointment_ids": [],
            "p_selected_attachment_ids": [],
            "p_selected_knowledge_ids": [],
            "p_excluded_item_count": 0,
            "p_schema_version": "1.0",
            "p_synthetic": True,
        },
        timeout=20,
    )
    context_response.raise_for_status()
    assert context_response.json() == context_event_id

    user_a_read = httpx.get(
        rest_url("context_assembly_events"),
        headers=headers(USER_A_TOKEN),
        params={"select": "id,task,status", "id": f"eq.{context_event_id}"},
        timeout=20,
    )
    user_a_read.raise_for_status()
    assert user_a_read.json() == [
        {"id": context_event_id, "task": "general_question", "status": "ready"}
    ]

    user_b_read = httpx.get(
        rest_url("context_assembly_events"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id", "id": f"eq.{context_event_id}"},
        timeout=20,
    )
    user_b_read.raise_for_status()
    assert user_b_read.json() == []


def test_attachment_confirmation_rpc_checks_ownership() -> None:
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None
    assert USER_A_ID is not None

    pregnancy_id = insert_pregnancy(USER_A_TOKEN, USER_A_ID, week=24)
    attachment_id = str(uuid4())
    extraction_id = str(uuid4())

    attachment_response = httpx.post(
        rest_url("attachment_records"),
        headers=headers(USER_A_TOKEN),
        json={
            "id": attachment_id,
            "user_id": USER_A_ID,
            "pregnancy_id": pregnancy_id,
            "kind": "lab_report",
            "mime_type": "application/pdf",
            "storage_object_path": f"{USER_A_ID}/{attachment_id}.pdf",
            "extraction_status": "completed",
            "confirmation_status": "unconfirmed",
        },
        timeout=20,
    )
    attachment_response.raise_for_status()

    extraction_response = httpx.post(
        rest_url("attachment_extractions"),
        headers=service_headers(),
        json={
            "id": extraction_id,
            "attachment_id": attachment_id,
            "extractor_name": "synthetic-local-extractor",
            "extractor_version": "1.0",
            "extracted_text": "Synthetic confirmed report text",
            "confidence": 0.99,
        },
        timeout=20,
    )
    extraction_response.raise_for_status()

    cross_user_confirmation = httpx.post(
        rest_url("rpc/confirm_janani_attachment_extraction"),
        headers=headers(USER_B_TOKEN),
        json={
            "p_attachment_id": attachment_id,
            "p_extraction_id": extraction_id,
            "p_confirmation": "confirmed",
        },
        timeout=20,
    )
    assert cross_user_confirmation.status_code in {400, 401, 403}

    owner_confirmation = httpx.post(
        rest_url("rpc/confirm_janani_attachment_extraction"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_attachment_id": attachment_id,
            "p_extraction_id": extraction_id,
            "p_confirmation": "confirmed",
        },
        timeout=20,
    )
    owner_confirmation.raise_for_status()

    owner_read = httpx.get(
        rest_url("attachment_records"),
        headers=headers(USER_A_TOKEN),
        params={
            "select": "confirmation_status",
            "id": f"eq.{attachment_id}",
        },
        timeout=20,
    )
    owner_read.raise_for_status()
    assert owner_read.json() == [{"confirmation_status": "confirmed"}]


def test_private_storage_paths_are_owner_scoped() -> None:
    assert SUPABASE_URL is not None
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None
    assert USER_A_ID is not None

    object_path = f"{USER_A_ID}/{uuid4()}.txt"
    object_url = f"{SUPABASE_URL}/storage/v1/object/janani-private/{object_path}"
    upload_headers = headers(USER_A_TOKEN)
    upload_headers["Content-Type"] = "text/plain"

    upload_response = httpx.post(
        object_url,
        headers=upload_headers,
        content=b"synthetic local storage object",
        timeout=20,
    )
    upload_response.raise_for_status()

    owner_read = httpx.get(object_url, headers=headers(USER_A_TOKEN), timeout=20)
    owner_read.raise_for_status()
    assert owner_read.content == b"synthetic local storage object"

    cross_read = httpx.get(object_url, headers=headers(USER_B_TOKEN), timeout=20)
    assert cross_read.status_code in {400, 401, 403, 404}

    cross_upload_headers = headers(USER_B_TOKEN)
    cross_upload_headers["Content-Type"] = "text/plain"
    cross_upload = httpx.post(
        f"{SUPABASE_URL}/storage/v1/object/janani-private/{USER_A_ID}/{uuid4()}.txt",
        headers=cross_upload_headers,
        content=b"must be rejected",
        timeout=20,
    )
    assert cross_upload.status_code in {400, 401, 403}


def test_account_deletion_request_is_idempotent_and_private() -> None:
    assert USER_A_TOKEN is not None
    assert USER_B_TOKEN is not None

    first = httpx.post(
        rest_url("rpc/request_janani_account_deletion"),
        headers=headers(USER_A_TOKEN),
        json={},
        timeout=20,
    )
    first.raise_for_status()
    first_payload = first.json()
    assert first_payload["status"] == "pending"
    UUID(first_payload["request_id"])

    second = httpx.post(
        rest_url("rpc/request_janani_account_deletion"),
        headers=headers(USER_A_TOKEN),
        json={},
        timeout=20,
    )
    second.raise_for_status()
    assert second.json()["request_id"] == first_payload["request_id"]

    owner_read = httpx.get(
        rest_url("account_deletion_requests"),
        headers=headers(USER_A_TOKEN),
        params={"select": "id,status"},
        timeout=20,
    )
    owner_read.raise_for_status()
    assert owner_read.json() == [
        {"id": first_payload["request_id"], "status": "pending"}
    ]

    cross_read = httpx.get(
        rest_url("account_deletion_requests"),
        headers=headers(USER_B_TOKEN),
        params={"select": "id,status"},
        timeout=20,
    )
    cross_read.raise_for_status()
    assert cross_read.json() == []
