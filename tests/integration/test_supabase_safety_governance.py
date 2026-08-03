import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
PUBLISHABLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY")
SERVICE_ROLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY")
USER_A_TOKEN = os.getenv("JANANI_STAGING_USER_A_TOKEN")

_REQUIRED = [SUPABASE_URL, PUBLISHABLE_KEY, SERVICE_ROLE_KEY, USER_A_TOKEN]

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not all(_REQUIRED),
        reason="Synthetic local Supabase credentials are not configured",
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
    result = headers(SERVICE_ROLE_KEY or "", prefer=prefer)
    result["apikey"] = SERVICE_ROLE_KEY or ""
    return result


def rest_url(path: str) -> str:
    assert SUPABASE_URL is not None
    return f"{SUPABASE_URL}/rest/v1/{path}"


def insert_service_record(table: str, payload: dict) -> dict:
    response = httpx.post(
        rest_url(table),
        headers=service_headers(prefer="return=representation"),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()[0]


def call_service_rpc(name: str, payload: dict):
    response = httpx.post(
        rest_url(f"rpc/{name}"),
        headers=service_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def test_clinical_governance_requires_service_role_and_dual_approval() -> None:
    assert USER_A_TOKEN is not None
    now = datetime.now(UTC)

    denied_read = httpx.get(
        rest_url("clinical_safety_rule_candidates"),
        headers=headers(USER_A_TOKEN),
        params={"select": "id"},
        timeout=20,
    )
    assert denied_read.status_code in {401, 403}

    denied_write = httpx.post(
        rest_url("clinical_safety_reviewers"),
        headers=headers(USER_A_TOKEN),
        json={
            "display_name": "Unauthorised user",
            "role": "obstetrician",
            "license_jurisdiction": "IN-test",
            "license_reference": f"DENIED-{uuid4()}",
            "credential_verified_at": (now - timedelta(days=1)).isoformat(),
            "credential_expires_at": (now + timedelta(days=30)).isoformat(),
        },
        timeout=20,
    )
    assert denied_write.status_code in {401, 403}

    obstetrician_id = str(uuid4())
    safety_reviewer_id = str(uuid4())
    reviewer_base = {
        "credential_verified_at": (now - timedelta(days=1)).isoformat(),
        "credential_expires_at": (now + timedelta(days=180)).isoformat(),
        "active": True,
    }
    insert_service_record(
        "clinical_safety_reviewers",
        {
            **reviewer_base,
            "id": obstetrician_id,
            "display_name": "Synthetic obstetrician",
            "role": "obstetrician",
            "license_jurisdiction": "IN-test",
            "license_reference": f"OB-{uuid4()}",
        },
    )
    insert_service_record(
        "clinical_safety_reviewers",
        {
            **reviewer_base,
            "id": safety_reviewer_id,
            "display_name": "Synthetic clinical safety reviewer",
            "role": "clinical_safety",
            "license_jurisdiction": "IN-test",
            "license_reference": f"CS-{uuid4()}",
        },
    )

    candidate_id = str(uuid4())
    digest = hashlib.sha256(candidate_id.encode()).hexdigest()
    insert_service_record(
        "clinical_safety_rule_candidates",
        {
            "id": candidate_id,
            "rule_id": f"SYNTHETIC-RULE-{uuid4()}",
            "version": "1.0.0-synthetic",
            "status": "draft",
            "severity": "urgent",
            "predicate_key": "structured.synthetic.flag",
            "clinical_rationale": (
                "Synthetic rationale used to verify dual clinical approval controls only."
            ),
            "applicability": {
                "minimum_gestational_week": 0,
                "maximum_gestational_week": 45,
                "required_structured_fields": ["gestational_week"],
            },
            "escalation_text": {
                "wording_version": "synthetic-1",
                "english": "Synthetic escalation wording that is not approved for patient use.",
                "telugu": "ఇది రోగుల వినియోగానికి ఆమోదించని కృత్రిమ పరీక్ష సందేశం మాత్రమే.",
            },
            "source_manifest": [
                {
                    "source_id": "SYNTHETIC-SOURCE",
                    "title": "Synthetic governance source",
                    "publisher": "Janani AI test suite",
                    "reference": "synthetic://governance-test",
                    "section": "Test-only",
                    "reviewed_at": (now - timedelta(days=1)).isoformat(),
                    "expires_at": (now + timedelta(days=90)).isoformat(),
                    "development_placeholder": False,
                }
            ],
            "content_digest": digest,
        },
    )

    denied_rpc = httpx.post(
        rest_url("rpc/record_janani_clinical_rule_review"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_review_id": str(uuid4()),
            "p_candidate_id": candidate_id,
            "p_reviewer_id": obstetrician_id,
            "p_decision": "approve",
            "p_rationale": "Unauthorised review must be denied.",
            "p_reviewed_at": now.isoformat(),
        },
        timeout=20,
    )
    assert denied_rpc.status_code in {401, 403}

    obstetric_review_id = str(uuid4())
    safety_review_id = str(uuid4())
    for review_id, reviewer_id, rationale in (
        (
            obstetric_review_id,
            obstetrician_id,
            "Synthetic obstetric review approved the exact candidate digest.",
        ),
        (
            safety_review_id,
            safety_reviewer_id,
            "Synthetic safety review approved the exact candidate digest.",
        ),
    ):
        result = call_service_rpc(
            "record_janani_clinical_rule_review",
            {
                "p_review_id": review_id,
                "p_candidate_id": candidate_id,
                "p_reviewer_id": reviewer_id,
                "p_decision": "approve",
                "p_rationale": rationale,
                "p_reviewed_at": now.isoformat(),
            },
        )
        assert result == review_id

    release_id = str(uuid4())
    activates_at = datetime.now(UTC) + timedelta(seconds=2)
    expires_at = datetime.now(UTC) + timedelta(days=30)
    approved = call_service_rpc(
        "approve_janani_clinical_safety_release",
        {
            "p_release_id": release_id,
            "p_candidate_id": candidate_id,
            "p_activates_at": activates_at.isoformat(),
            "p_expires_at": expires_at.isoformat(),
            "p_supersedes_release_id": None,
        },
    )
    assert approved == release_id

    time.sleep(2.5)
    activated = call_service_rpc(
        "activate_janani_clinical_safety_release",
        {
            "p_release_id": release_id,
            "p_reason": "Synthetic local governance activation test",
        },
    )
    assert activated == release_id

    release_read = httpx.get(
        rest_url("clinical_safety_releases"),
        headers=service_headers(),
        params={
            "select": "id,status,candidate_digest",
            "id": f"eq.{release_id}",
        },
        timeout=20,
    )
    release_read.raise_for_status()
    assert release_read.json() == [
        {"id": release_id, "status": "active", "candidate_digest": digest}
    ]

    approvals_read = httpx.get(
        rest_url("clinical_safety_release_approvals"),
        headers=service_headers(),
        params={"select": "reviewer_role", "release_id": f"eq.{release_id}"},
        timeout=20,
    )
    approvals_read.raise_for_status()
    assert {item["reviewer_role"] for item in approvals_read.json()} == {
        "obstetrician",
        "clinical_safety",
    }

    candidate_mutation = httpx.patch(
        rest_url("clinical_safety_rule_candidates"),
        headers=service_headers(),
        params={"id": f"eq.{candidate_id}"},
        json={"clinical_rationale": "Mutated content must be denied after insertion."},
        timeout=20,
    )
    assert candidate_mutation.status_code == 403

    review_mutation = httpx.patch(
        rest_url("clinical_safety_rule_reviews"),
        headers=service_headers(),
        params={"id": f"eq.{obstetric_review_id}"},
        json={"rationale": "Mutation must be denied."},
        timeout=20,
    )
    assert review_mutation.status_code == 403

    events_read = httpx.get(
        rest_url("clinical_safety_governance_events"),
        headers=service_headers(),
        params={"select": "id,event_type", "aggregate_id": f"eq.{release_id}"},
        timeout=20,
    )
    events_read.raise_for_status()
    event_types = {item["event_type"] for item in events_read.json()}
    assert {"release_approved", "release_activated"} <= event_types

    event_id = events_read.json()[0]["id"]
    event_mutation = httpx.delete(
        rest_url("clinical_safety_governance_events"),
        headers=service_headers(),
        params={"id": f"eq.{event_id}"},
        timeout=20,
    )
    assert event_mutation.status_code == 403
