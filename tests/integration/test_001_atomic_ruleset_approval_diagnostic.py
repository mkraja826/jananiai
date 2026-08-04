from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

from tests.integration import test_supabase_atomic_rulesets as atomic

pytestmark = atomic.pytestmark


def test_approved_releases_are_visible_before_ruleset_approval() -> None:
    now = datetime.now(UTC)
    reviewers = (
        atomic.create_reviewer("obstetrician", now),
        atomic.create_reviewer("clinical_safety", now),
    )
    activates_at = datetime.now(UTC) + timedelta(minutes=1)
    expires_at = datetime.now(UTC) + timedelta(days=1)
    release_ids = {
        atomic.create_approved_release(
            "DIAGNOSTIC-ATOMIC-RULE-A",
            "1.0.0",
            reviewers,
            activates_at,
            expires_at,
            now,
        ),
        atomic.create_approved_release(
            "DIAGNOSTIC-ATOMIC-RULE-B",
            "1.0.0",
            reviewers,
            activates_at,
            expires_at,
            now,
        ),
    }

    visible = atomic.read_rows(
        "clinical_safety_releases",
        "id,rule_id,status,activates_at,expires_at",
        id=f"in.({','.join(sorted(release_ids))})",
    )
    assert {item["id"] for item in visible} == release_ids, visible
    assert {item["status"] for item in visible} == {"approved"}, visible

    ruleset_id = str(uuid4())
    response = httpx.post(
        atomic.rest_url("rpc/approve_janani_clinical_safety_ruleset"),
        headers=atomic.service_headers(),
        json={
            "p_ruleset_id": ruleset_id,
            "p_version": f"diagnostic-{ruleset_id}",
            "p_required_rule_ids": [
                "DIAGNOSTIC-ATOMIC-RULE-A",
                "DIAGNOSTIC-ATOMIC-RULE-B",
            ],
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
