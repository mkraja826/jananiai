import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
PUBLISHABLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY")
SERVICE_ROLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY")

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not SUPABASE_URL or not PUBLISHABLE_KEY or not SERVICE_ROLE_KEY,
        reason="Synthetic local Supabase credentials are not configured",
    ),
]


def rest_url(path: str) -> str:
    assert SUPABASE_URL is not None
    return f"{SUPABASE_URL}/rest/v1/{path}"


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


def insert_record(table: str, payload: dict) -> dict:
    response = httpx.post(
        rest_url(table),
        headers=service_headers(prefer="return=representation"),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()[0]


def call_rpc(name: str, payload: dict):
    response = httpx.post(
        rest_url(f"rpc/{name}"),
        headers=service_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def create_reviewer(role: str, now: datetime) -> str:
    reviewer_id = str(uuid4())
    insert_record(
        "clinical_safety_reviewers",
        {
            "id": reviewer_id,
            "display_name": f"Synthetic diagnostic {role}",
            "role": role,
            "license_jurisdiction": "IN-test",
            "license_reference": f"DIAGNOSTIC-{role}-{uuid4()}",
            "credential_verified_at": (now - timedelta(days=1)).isoformat(),
            "credential_expires_at": (now + timedelta(days=180)).isoformat(),
            "active": True,
        },
    )
    return reviewer_id


def create_approved_release(
    rule_id: str,
    reviewer_ids: tuple[str, str],
    activates_at: datetime,
    expires_at: datetime,
    now: datetime,
) -> str:
    candidate_id = str(uuid4())
    digest = hashlib.sha256(candidate_id.encode()).hexdigest()
    insert_record(
        "clinical_safety_rule_candidates",
        {
            "id": candidate_id,
            "rule_id": rule_id,
            "version": "1.0.0",
            "status": "draft",
            "severity": "urgent",
            "predicate_key": f"structured.synthetic.{rule_id.lower()}",
            "clinical_rationale": (
                "Synthetic rationale used only to diagnose atomic ruleset approval."
            ),
            "applicability": {
                "minimum_gestational_week": 0,
                "maximum_gestational_week": 45,
                "required_structured_fields": ["gestational_week"],
            },
            "escalation_text": {
                "wording_version": "diagnostic-1",
                "english": "Synthetic diagnostic escalation wording for tests only.",
                "telugu": "ఇది అటామిక్ రూల్‌సెట్ నిర్ధారణ పరీక్ష కోసం మాత్రమే ఉపయోగించే కృత్రిమ సందేశం.",
            },
            "source_manifest": [
                {
                    "source_id": f"SOURCE-{candidate_id}",
                    "title": "Synthetic diagnostic source",
                    "publisher": "Janani AI test suite",
                    "reference": "synthetic://ruleset-diagnostic",
                    "section": "Test-only",
                    "reviewed_at": (now - timedelta(days=1)).isoformat(),
                    "expires_at": (now + timedelta(days=120)).isoformat(),
                    "development_placeholder": False,
                }
            ],
            "content_digest": digest,
        },
    )

    for reviewer_id, rationale in (
        (
            reviewer_ids[0],
            "Synthetic obstetrician approval for the exact diagnostic candidate.",
        ),
        (
            reviewer_ids[1],
            "Synthetic clinical-safety approval for the exact diagnostic candidate.",
        ),
    ):
        review_id = str(uuid4())
        assert (
            call_rpc(
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
            == review_id
        )

    release_id = str(uuid4())
    assert (
        call_rpc(
            "approve_janani_clinical_safety_release",
            {
                "p_release_id": release_id,
                "p_candidate_id": candidate_id,
                "p_activates_at": activates_at.isoformat(),
                "p_expires_at": expires_at.isoformat(),
                "p_supersedes_release_id": None,
            },
        )
        == release_id
    )
    return release_id


def test_ruleset_approval_transaction_reports_exact_failure() -> None:
    now = datetime.now(UTC)
    reviewers = (
        create_reviewer("obstetrician", now),
        create_reviewer("clinical_safety", now),
    )
    activates_at = datetime.now(UTC) + timedelta(minutes=2)
    expires_at = datetime.now(UTC) + timedelta(days=1)
    rule_ids = (
        f"DIAGNOSTIC-RULE-A-{uuid4().hex[:8]}",
        f"DIAGNOSTIC-RULE-B-{uuid4().hex[:8]}",
    )
    release_ids = {
        create_approved_release(
            rule_ids[0],
            reviewers,
            activates_at,
            expires_at,
            now,
        ),
        create_approved_release(
            rule_ids[1],
            reviewers,
            activates_at,
            expires_at,
            now,
        ),
    }

    visible_response = httpx.get(
        rest_url("clinical_safety_releases"),
        headers=service_headers(),
        params={
            "select": "id,rule_id,status,activates_at,expires_at",
            "id": f"in.({','.join(sorted(release_ids))})",
        },
        timeout=20,
    )
    visible_response.raise_for_status()
    visible = visible_response.json()
    assert {item["id"] for item in visible} == release_ids, visible
    assert {item["status"] for item in visible} == {"approved"}, visible

    ruleset_id = str(uuid4())
    response = httpx.post(
        rest_url("rpc/approve_janani_clinical_safety_ruleset"),
        headers=service_headers(),
        json={
            "p_ruleset_id": ruleset_id,
            "p_version": f"diagnostic-{ruleset_id}",
            "p_required_rule_ids": list(rule_ids),
            "p_release_ids": sorted(release_ids),
            "p_activates_at": activates_at.isoformat(),
            "p_expires_at": expires_at.isoformat(),
            "p_supersedes_ruleset_id": None,
        },
        timeout=20,
    )

    assert response.is_success, {
        "status": response.status_code,
        "body": response.text,
        "visible_releases": visible,
    }
    assert response.json() == ruleset_id
