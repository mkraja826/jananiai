import hashlib
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

_REQUIRED = [
    SUPABASE_URL,
    PUBLISHABLE_KEY,
    SERVICE_ROLE_KEY,
    USER_A_ID,
    USER_A_TOKEN,
]

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not all(_REQUIRED),
        reason="Synthetic local Supabase credentials are not configured",
    ),
]

CATEGORIES = [
    "true_positive",
    "true_negative",
    "boundary",
    "interaction",
    "regression",
    "ambiguity",
    "missing_data",
    "adversarial",
    "cross_rule",
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


def read_service_rows(table: str, select: str, **filters: str) -> list[dict]:
    response = httpx.get(
        rest_url(table),
        headers=service_headers(),
        params={"select": select, **filters},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def test_review_packet_and_rehearsal_evidence_are_private_and_immutable() -> None:
    assert USER_A_ID is not None
    now = datetime.now(UTC)
    candidate_id = str(uuid4())
    candidate_digest = hashlib.sha256(candidate_id.encode()).hexdigest()
    rule_id = f"EVIDENCE-RULE-{uuid4().hex[:8]}"
    insert_service_record(
        "clinical_safety_rule_candidates",
        {
            "id": candidate_id,
            "rule_id": rule_id,
            "version": "1.0.0",
            "status": "draft",
            "severity": "urgent",
            "predicate_key": "structured.synthetic.evidence_rule",
            "clinical_rationale": (
                "Synthetic candidate used only to validate immutable review evidence persistence."
            ),
            "applicability": {
                "minimum_gestational_week": 0,
                "maximum_gestational_week": 45,
                "required_structured_fields": ["gestational_week"],
            },
            "escalation_text": {
                "wording_version": "synthetic-1",
                "english": "Synthetic escalation wording used only for evidence persistence tests.",
                "telugu": "ఇది సమీక్ష ఆధారాల నిల్వ పరీక్ష కోసం మాత్రమే ఉపయోగించే కృత్రిమ సందేశం.",
            },
            "source_manifest": [
                {
                    "source_id": f"SOURCE-{candidate_id}",
                    "title": "Synthetic evidence source",
                    "publisher": "Janani AI test suite",
                    "reference": "synthetic://review-evidence/source",
                    "section": "Test-only",
                    "reviewed_at": (now - timedelta(days=1)).isoformat(),
                    "expires_at": (now + timedelta(days=30)).isoformat(),
                    "development_placeholder": True,
                }
            ],
            "content_digest": candidate_digest,
        },
    )

    packet_id = str(uuid4())
    packet_digest = hashlib.sha256(packet_id.encode()).hexdigest()
    dataset_digest = hashlib.sha256(b"synthetic-review-dataset").hexdigest()
    packet_payload = {
        "packet_id": packet_id,
        "packet_version": "preclinical-review-2026-08-07.1",
        "generated_at": now.isoformat(),
        "candidate_id": candidate_id,
        "rule_id": rule_id,
        "candidate_version": "1.0.0",
        "candidate_digest": candidate_digest,
        "severity": "urgent",
        "predicate_key": "structured.synthetic.evidence_rule",
        "clinical_rationale": (
            "Synthetic candidate used only to validate immutable review evidence persistence."
        ),
        "source_references": ["synthetic://review-evidence/source"],
        "placeholder_sources_present": True,
        "escalation_wording_version": "synthetic-1",
        "english_escalation_text": "Synthetic review evidence wording for tests only.",
        "telugu_escalation_text": "ఇది సమీక్ష ఆధారాల పరీక్ష కోసం మాత్రమే ఉపయోగించే కృత్రిమ సందేశం.",
        "required_review_roles": [
            "obstetrician",
            "clinical_safety",
            "language_reviewer",
        ],
        "status": "clinical_input_required",
        "synthetic_only": True,
        "packet_digest": packet_digest,
        "validation": {
            "rule_id": rule_id,
            "dataset_version": "dev-validation-2026-08-07.1",
            "dataset_digest": dataset_digest,
            "case_ids": [f"case-{index}" for index in range(9)],
            "categories": CATEGORIES,
            "total_cases": 9,
            "passed_cases": 9,
        },
    }

    denied_packet_rpc = httpx.post(
        rest_url("rpc/record_janani_clinical_review_packet"),
        headers=user_headers(),
        json={"p_actor_user_id": USER_A_ID, "p_payload": packet_payload},
        timeout=20,
    )
    assert denied_packet_rpc.status_code in {401, 403}

    assert call_service_rpc(
        "record_janani_clinical_review_packet",
        {"p_actor_user_id": USER_A_ID, "p_payload": packet_payload},
    ) == packet_id

    packet_rows = read_service_rows(
        "clinical_safety_review_packets",
        "id,candidate_id,rule_id,total_cases,passed_cases,synthetic_only,recorded_by_user_id",
        id=f"eq.{packet_id}",
    )
    assert packet_rows == [
        {
            "id": packet_id,
            "candidate_id": candidate_id,
            "rule_id": rule_id,
            "total_cases": 9,
            "passed_cases": 9,
            "synthetic_only": True,
            "recorded_by_user_id": USER_A_ID,
        }
    ]

    incident_ruleset_id = str(uuid4())
    restored_ruleset_id = str(uuid4())
    insert_service_record(
        "clinical_safety_rulesets",
        {
            "id": incident_ruleset_id,
            "version": f"synthetic-incident-{uuid4()}",
            "status": "rolled_back",
            "required_rule_ids": [rule_id],
            "manifest_digest": hashlib.sha256(incident_ruleset_id.encode()).hexdigest(),
            "approved_at": (now - timedelta(days=2)).isoformat(),
            "activates_at": (now - timedelta(days=1)).isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "terminal_reason": "Synthetic incident rollback rehearsal state",
        },
    )
    insert_service_record(
        "clinical_safety_rulesets",
        {
            "id": restored_ruleset_id,
            "version": f"synthetic-restored-{uuid4()}",
            "status": "active",
            "required_rule_ids": [rule_id],
            "manifest_digest": hashlib.sha256(restored_ruleset_id.encode()).hexdigest(),
            "approved_at": (now - timedelta(days=3)).isoformat(),
            "activates_at": (now - timedelta(days=2)).isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
        },
    )

    rehearsal_id = str(uuid4())
    step_names = [
        "detect_incident",
        "verify_active_manifest",
        "execute_atomic_rollback",
        "verify_restored_manifest",
        "verify_rolled_back_state",
        "record_audit_evidence",
    ]
    rehearsal_payload = {
        "rehearsal_id": rehearsal_id,
        "scenario": "emergency_ruleset_rollback",
        "started_at": now.isoformat(),
        "completed_at": now.isoformat(),
        "active_ruleset_before": incident_ruleset_id,
        "restored_ruleset_after": restored_ruleset_id,
        "rolled_back_ruleset": incident_ruleset_id,
        "reason": "Synthetic emergency rollback rehearsal evidence persistence test.",
        "steps": [
            {
                "name": name,
                "passed": True,
                "evidence_ref": f"synthetic://rehearsal/{name}",
            }
            for name in step_names
        ],
        "passed": True,
        "synthetic_only": True,
    }

    denied_rehearsal_rpc = httpx.post(
        rest_url("rpc/record_janani_safety_rehearsal"),
        headers=user_headers(),
        json={"p_actor_user_id": USER_A_ID, "p_payload": rehearsal_payload},
        timeout=20,
    )
    assert denied_rehearsal_rpc.status_code in {401, 403}

    assert call_service_rpc(
        "record_janani_safety_rehearsal",
        {"p_actor_user_id": USER_A_ID, "p_payload": rehearsal_payload},
    ) == rehearsal_id

    rehearsal_rows = read_service_rows(
        "clinical_safety_rehearsals",
        "id,scenario,active_ruleset_before,restored_ruleset_after,passed,synthetic_only",
        id=f"eq.{rehearsal_id}",
    )
    assert rehearsal_rows == [
        {
            "id": rehearsal_id,
            "scenario": "emergency_ruleset_rollback",
            "active_ruleset_before": incident_ruleset_id,
            "restored_ruleset_after": restored_ruleset_id,
            "passed": True,
            "synthetic_only": True,
        }
    ]

    denied_packet_read = httpx.get(
        rest_url("clinical_safety_review_packets"),
        headers=user_headers(),
        params={"select": "id"},
        timeout=20,
    )
    denied_rehearsal_read = httpx.get(
        rest_url("clinical_safety_rehearsals"),
        headers=user_headers(),
        params={"select": "id"},
        timeout=20,
    )
    assert denied_packet_read.status_code in {401, 403}
    assert denied_rehearsal_read.status_code in {401, 403}

    packet_delete = httpx.delete(
        rest_url("clinical_safety_review_packets"),
        headers=service_headers(),
        params={"id": f"eq.{packet_id}"},
        timeout=20,
    )
    rehearsal_delete = httpx.delete(
        rest_url("clinical_safety_rehearsals"),
        headers=service_headers(),
        params={"id": f"eq.{rehearsal_id}"},
        timeout=20,
    )
    assert packet_delete.status_code == 403
    assert rehearsal_delete.status_code == 403

    events = read_service_rows(
        "clinical_safety_governance_events",
        "event_type,aggregate_id,actor_user_id",
        aggregate_id=f"in.({packet_id},{rehearsal_id})",
    )
    assert {(item["event_type"], item["aggregate_id"]) for item in events} == {
        ("review_packet_recorded", packet_id),
        ("rehearsal_recorded", rehearsal_id),
    }
    assert {item["actor_user_id"] for item in events} == {USER_A_ID}
