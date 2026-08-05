import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
PUBLISHABLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY")
SERVICE_ROLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY")
USER_A_ID = os.getenv("JANANI_STAGING_USER_A_ID")
USER_A_TOKEN = os.getenv("JANANI_STAGING_USER_A_TOKEN")
USER_B_ID = os.getenv("JANANI_STAGING_USER_B_ID")

_REQUIRED = [
    SUPABASE_URL,
    PUBLISHABLE_KEY,
    SERVICE_ROLE_KEY,
    USER_A_ID,
    USER_A_TOKEN,
    USER_B_ID,
]

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not all(_REQUIRED),
        reason="Synthetic local Supabase credentials are not configured",
    ),
]


def rest_url(path: str) -> str:
    assert SUPABASE_URL is not None
    return f"{SUPABASE_URL}/rest/v1/{path}"


def user_headers() -> dict[str, str]:
    assert PUBLISHABLE_KEY is not None
    assert USER_A_TOKEN is not None
    return {
        "apikey": PUBLISHABLE_KEY,
        "Authorization": f"Bearer {USER_A_TOKEN}",
        "Content-Type": "application/json",
    }


def service_headers(*, prefer: str | None = None) -> dict[str, str]:
    assert SERVICE_ROLE_KEY is not None
    result = {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        result["Prefer"] = prefer
    return result


def call_service_rpc(name: str, payload: dict):
    response = httpx.post(
        rest_url(f"rpc/{name}"),
        headers=service_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def read_service_rows(table: str, select: str, **filters: str) -> list[dict]:
    response = httpx.get(
        rest_url(table),
        headers=service_headers(),
        params={"select": select, **filters},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def test_reviewer_onboarding_reverification_and_deactivation_are_controlled() -> None:
    assert USER_A_ID is not None
    assert USER_B_ID is not None
    now = datetime.now(UTC)
    verified_at = now - timedelta(minutes=1)
    expires_at = now + timedelta(days=180)
    attested_at = now - timedelta(minutes=2)
    license_reference = f"SYNTHETIC-REVIEWER-{uuid4()}"

    denied_read = httpx.get(
        rest_url("clinical_safety_reviewers"),
        headers=user_headers(),
        params={"select": "id"},
        timeout=20,
    )
    assert denied_read.status_code in {401, 403}

    denied_rpc = httpx.post(
        rest_url("rpc/onboard_janani_clinical_reviewer"),
        headers=user_headers(),
        json={
            "p_actor_user_id": USER_A_ID,
            "p_reviewer_user_id": USER_B_ID,
            "p_display_name": "Synthetic Language Reviewer",
            "p_role": "language_reviewer",
            "p_license_jurisdiction": "IN-test",
            "p_license_reference": license_reference,
            "p_credential_verified_at": verified_at.isoformat(),
            "p_credential_expires_at": expires_at.isoformat(),
            "p_conflict_of_interest_attested_at": attested_at.isoformat(),
            "p_attestation_version": "coi-v1",
            "p_evidence_reference": "vault://synthetic/reviewer/integration",
            "p_reason": "Synthetic onboarding validates the controlled reviewer administration RPC.",
        },
        timeout=20,
    )
    assert denied_rpc.status_code in {401, 403}

    reviewer_id = call_service_rpc(
        "onboard_janani_clinical_reviewer",
        {
            "p_actor_user_id": USER_A_ID,
            "p_reviewer_user_id": USER_B_ID,
            "p_display_name": "Synthetic Language Reviewer",
            "p_role": "language_reviewer",
            "p_license_jurisdiction": "IN-test",
            "p_license_reference": license_reference,
            "p_credential_verified_at": verified_at.isoformat(),
            "p_credential_expires_at": expires_at.isoformat(),
            "p_conflict_of_interest_attested_at": attested_at.isoformat(),
            "p_attestation_version": "coi-v1",
            "p_evidence_reference": "vault://synthetic/reviewer/integration",
            "p_reason": "Synthetic onboarding validates the controlled reviewer administration RPC.",
        },
    )

    rows = read_service_rows(
        "clinical_safety_reviewers",
        (
            "id,user_id,role,active,attestation_version,evidence_reference,"
            "onboarded_by_user_id,deactivated_at"
        ),
        id=f"eq.{reviewer_id}",
    )
    assert rows == [
        {
            "id": reviewer_id,
            "user_id": USER_B_ID,
            "role": "language_reviewer",
            "active": True,
            "attestation_version": "coi-v1",
            "evidence_reference": "vault://synthetic/reviewer/integration",
            "onboarded_by_user_id": USER_A_ID,
            "deactivated_at": None,
        }
    ]

    direct_update = httpx.patch(
        rest_url("clinical_safety_reviewers"),
        headers=service_headers(prefer="return=representation"),
        params={"id": f"eq.{reviewer_id}"},
        json={"credential_expires_at": (now + timedelta(days=365)).isoformat()},
        timeout=20,
    )
    assert direct_update.status_code == 403

    new_verified_at = now
    new_expires_at = now + timedelta(days=365)
    assert call_service_rpc(
        "reverify_janani_clinical_reviewer",
        {
            "p_actor_user_id": USER_A_ID,
            "p_reviewer_id": reviewer_id,
            "p_credential_verified_at": new_verified_at.isoformat(),
            "p_credential_expires_at": new_expires_at.isoformat(),
            "p_conflict_of_interest_attested_at": attested_at.isoformat(),
            "p_attestation_version": "coi-v2",
            "p_evidence_reference": "vault://synthetic/reviewer/integration/v2",
            "p_reason": "Synthetic reverification validates controlled credential renewal and audit history.",
        },
    ) == reviewer_id

    reverified = read_service_rows(
        "clinical_safety_reviewers",
        "id,active,attestation_version,evidence_reference",
        id=f"eq.{reviewer_id}",
    )
    assert reverified == [
        {
            "id": reviewer_id,
            "active": True,
            "attestation_version": "coi-v2",
            "evidence_reference": "vault://synthetic/reviewer/integration/v2",
        }
    ]

    assert call_service_rpc(
        "deactivate_janani_clinical_reviewer",
        {
            "p_actor_user_id": USER_A_ID,
            "p_reviewer_id": reviewer_id,
            "p_reason": "Synthetic deactivation validates controlled reviewer lifecycle termination.",
        },
    ) == reviewer_id

    deactivated = read_service_rows(
        "clinical_safety_reviewers",
        "id,active,deactivated_by_user_id,deactivation_reason",
        id=f"eq.{reviewer_id}",
    )
    assert deactivated == [
        {
            "id": reviewer_id,
            "active": False,
            "deactivated_by_user_id": USER_A_ID,
            "deactivation_reason": (
                "Synthetic deactivation validates controlled reviewer lifecycle termination."
            ),
        }
    ]

    duplicate_deactivation = httpx.post(
        rest_url("rpc/deactivate_janani_clinical_reviewer"),
        headers=service_headers(),
        json={
            "p_actor_user_id": USER_A_ID,
            "p_reviewer_id": reviewer_id,
            "p_reason": "Synthetic duplicate deactivation must fail closed after reviewer termination.",
        },
        timeout=20,
    )
    assert duplicate_deactivation.status_code == 403

    events = read_service_rows(
        "clinical_safety_governance_events",
        "event_type,aggregate_id,actor_user_id",
        aggregate_type="eq.reviewer",
        aggregate_id=f"eq.{reviewer_id}",
    )
    assert [item["event_type"] for item in events] == [
        "reviewer_onboarded",
        "reviewer_reverified",
        "reviewer_deactivated",
    ]
    assert {item["aggregate_id"] for item in events} == {reviewer_id}
    assert {item["actor_user_id"] for item in events} == {USER_A_ID}
