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


def wait_until(target: datetime) -> None:
    delay = (target - datetime.now(UTC)).total_seconds() + 0.5
    if delay > 0:
        time.sleep(delay)


def create_reviewer(role: str, now: datetime) -> str:
    reviewer_id = str(uuid4())
    insert_service_record(
        "clinical_safety_reviewers",
        {
            "id": reviewer_id,
            "display_name": f"Synthetic {role} ruleset reviewer",
            "role": role,
            "license_jurisdiction": "IN-test",
            "license_reference": f"RULESET-{role}-{uuid4()}",
            "credential_verified_at": (now - timedelta(days=1)).isoformat(),
            "credential_expires_at": (now + timedelta(days=180)).isoformat(),
            "active": True,
        },
    )
    return reviewer_id


def create_approved_release(
    rule_id: str,
    version: str,
    reviewer_ids: tuple[str, str],
    activates_at: datetime,
    expires_at: datetime,
    now: datetime,
) -> str:
    candidate_id = str(uuid4())
    digest = hashlib.sha256(candidate_id.encode()).hexdigest()
    insert_service_record(
        "clinical_safety_rule_candidates",
        {
            "id": candidate_id,
            "rule_id": rule_id,
            "version": version,
            "status": "draft",
            "severity": "urgent",
            "predicate_key": f"structured.synthetic.{rule_id.lower()}",
            "clinical_rationale": (
                "Synthetic rationale used only to validate atomic ruleset transactions."
            ),
            "applicability": {
                "minimum_gestational_week": 0,
                "maximum_gestational_week": 45,
                "required_structured_fields": ["gestational_week"],
            },
            "escalation_text": {
                "wording_version": version,
                "english": "Synthetic atomic-ruleset escalation wording for tests only.",
                "telugu": "ఇది అటామిక్ రూల్‌సెట్ పరీక్ష కోసం మాత్రమే ఉపయోగించే కృత్రిమ సందేశం.",
            },
            "source_manifest": [
                {
                    "source_id": f"SOURCE-{candidate_id}",
                    "title": "Synthetic atomic ruleset source",
                    "publisher": "Janani AI test suite",
                    "reference": "synthetic://atomic-ruleset",
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
            "Synthetic obstetrician approval for the exact atomic-ruleset candidate.",
        ),
        (
            reviewer_ids[1],
            "Synthetic clinical-safety approval for the exact atomic-ruleset candidate.",
        ),
    ):
        review_id = str(uuid4())
        assert (
            call_service_rpc(
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
        call_service_rpc(
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


def read_rows(table: str, select: str, **filters: str) -> list[dict]:
    response = httpx.get(
        rest_url(table),
        headers=service_headers(),
        params={"select": select, **filters},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def assert_exact_active_releases(expected_ids: set[str]) -> None:
    active = read_rows(
        "clinical_safety_releases",
        "id,status",
        status="eq.active",
    )
    assert {item["id"] for item in active} == expected_ids
    assert {item["status"] for item in active} == {"active"}


def test_atomic_ruleset_activation_replacement_and_rollback() -> None:
    assert USER_A_TOKEN is not None
    now = datetime.now(UTC)
    reviewers = (
        create_reviewer("obstetrician", now),
        create_reviewer("clinical_safety", now),
    )

    denied_read = httpx.get(
        rest_url("clinical_safety_rulesets"),
        headers=headers(USER_A_TOKEN),
        params={"select": "id"},
        timeout=20,
    )
    assert denied_read.status_code in {401, 403}

    first_activation = datetime.now(UTC) + timedelta(seconds=8)
    first_expiry = datetime.now(UTC) + timedelta(days=30)
    first_release_ids = {
        create_approved_release(
            "ATOMIC-RULE-A",
            "1.0.0",
            reviewers,
            first_activation,
            first_expiry,
            now,
        ),
        create_approved_release(
            "ATOMIC-RULE-B",
            "1.0.0",
            reviewers,
            first_activation,
            first_expiry,
            now,
        ),
    }
    first_ruleset_id = str(uuid4())

    denied_rpc = httpx.post(
        rest_url("rpc/approve_janani_clinical_safety_ruleset"),
        headers=headers(USER_A_TOKEN),
        json={
            "p_ruleset_id": str(uuid4()),
            "p_version": "unauthorised",
            "p_required_rule_ids": ["ATOMIC-RULE-A", "ATOMIC-RULE-B"],
            "p_release_ids": list(first_release_ids),
            "p_activates_at": first_activation.isoformat(),
            "p_expires_at": first_expiry.isoformat(),
            "p_supersedes_ruleset_id": None,
        },
        timeout=20,
    )
    assert denied_rpc.status_code in {401, 403}

    assert (
        call_service_rpc(
            "approve_janani_clinical_safety_ruleset",
            {
                "p_ruleset_id": first_ruleset_id,
                "p_version": "atomic-ruleset-1",
                "p_required_rule_ids": ["ATOMIC-RULE-A", "ATOMIC-RULE-B"],
                "p_release_ids": list(first_release_ids),
                "p_activates_at": first_activation.isoformat(),
                "p_expires_at": first_expiry.isoformat(),
                "p_supersedes_ruleset_id": None,
            },
        )
        == first_ruleset_id
    )

    incomplete_ruleset = httpx.post(
        rest_url("rpc/approve_janani_clinical_safety_ruleset"),
        headers=service_headers(),
        json={
            "p_ruleset_id": str(uuid4()),
            "p_version": "atomic-ruleset-incomplete",
            "p_required_rule_ids": ["ATOMIC-RULE-A", "ATOMIC-RULE-B"],
            "p_release_ids": [next(iter(first_release_ids))],
            "p_activates_at": first_activation.isoformat(),
            "p_expires_at": first_expiry.isoformat(),
            "p_supersedes_ruleset_id": None,
        },
        timeout=20,
    )
    assert incomplete_ruleset.status_code == 403

    wait_until(first_activation)
    assert (
        call_service_rpc(
            "activate_janani_clinical_safety_ruleset",
            {
                "p_ruleset_id": first_ruleset_id,
                "p_reason": "Synthetic first atomic ruleset activation",
            },
        )
        == first_ruleset_id
    )
    assert_exact_active_releases(first_release_ids)

    second_now = datetime.now(UTC)
    second_activation = second_now + timedelta(seconds=8)
    second_expiry = second_now + timedelta(days=30)
    second_release_ids = {
        create_approved_release(
            "ATOMIC-RULE-A",
            "2.0.0",
            reviewers,
            second_activation,
            second_expiry,
            second_now,
        ),
        create_approved_release(
            "ATOMIC-RULE-B",
            "2.0.0",
            reviewers,
            second_activation,
            second_expiry,
            second_now,
        ),
    }
    second_ruleset_id = str(uuid4())
    assert (
        call_service_rpc(
            "approve_janani_clinical_safety_ruleset",
            {
                "p_ruleset_id": second_ruleset_id,
                "p_version": "atomic-ruleset-2",
                "p_required_rule_ids": ["ATOMIC-RULE-A", "ATOMIC-RULE-B"],
                "p_release_ids": list(second_release_ids),
                "p_activates_at": second_activation.isoformat(),
                "p_expires_at": second_expiry.isoformat(),
                "p_supersedes_ruleset_id": first_ruleset_id,
            },
        )
        == second_ruleset_id
    )

    wait_until(second_activation)
    assert (
        call_service_rpc(
            "activate_janani_clinical_safety_ruleset",
            {
                "p_ruleset_id": second_ruleset_id,
                "p_reason": "Synthetic complete ruleset replacement",
            },
        )
        == second_ruleset_id
    )
    assert_exact_active_releases(second_release_ids)

    rulesets = read_rows(
        "clinical_safety_rulesets",
        "id,status",
        id=f"in.({first_ruleset_id},{second_ruleset_id})",
    )
    status_by_id = {item["id"]: item["status"] for item in rulesets}
    assert status_by_id == {
        first_ruleset_id: "retired",
        second_ruleset_id: "active",
    }

    assert (
        call_service_rpc(
            "rollback_janani_clinical_safety_ruleset",
            {
                "p_active_ruleset_id": second_ruleset_id,
                "p_replacement_ruleset_id": first_ruleset_id,
                "p_reason": "Synthetic ruleset regression rollback",
            },
        )
        == first_ruleset_id
    )
    assert_exact_active_releases(first_release_ids)

    final_rulesets = read_rows(
        "clinical_safety_rulesets",
        "id,status",
        id=f"in.({first_ruleset_id},{second_ruleset_id})",
    )
    final_status_by_id = {item["id"]: item["status"] for item in final_rulesets}
    assert final_status_by_id == {
        first_ruleset_id: "active",
        second_ruleset_id: "rolled_back",
    }

    events = read_rows(
        "clinical_safety_governance_events",
        "event_type,aggregate_id",
        aggregate_type="eq.ruleset",
    )
    event_types = {item["event_type"] for item in events}
    assert {
        "ruleset_approved",
        "ruleset_activated",
        "ruleset_retired",
        "ruleset_rolled_back",
    } <= event_types

    member = read_rows(
        "clinical_safety_ruleset_members",
        "ruleset_id,rule_id",
        ruleset_id=f"eq.{first_ruleset_id}",
    )[0]
    member_mutation = httpx.delete(
        rest_url("clinical_safety_ruleset_members"),
        headers=service_headers(),
        params={
            "ruleset_id": f"eq.{member['ruleset_id']}",
            "rule_id": f"eq.{member['rule_id']}",
        },
        timeout=20,
    )
    assert member_mutation.status_code == 403
