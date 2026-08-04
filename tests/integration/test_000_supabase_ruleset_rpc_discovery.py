import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

SUPABASE_URL = os.getenv("JANANI_STAGING_SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY")

pytestmark = [
    pytest.mark.staging,
    pytest.mark.skipif(
        not SUPABASE_URL or not SERVICE_ROLE_KEY,
        reason="Synthetic local Supabase credentials are not configured",
    ),
]


def service_headers() -> dict[str, str]:
    assert SERVICE_ROLE_KEY is not None
    return {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def test_atomic_ruleset_rpcs_are_present_in_postgrest_openapi() -> None:
    assert SUPABASE_URL is not None
    response = httpx.get(
        f"{SUPABASE_URL}/rest/v1/",
        headers={**service_headers(), "Accept": "application/openapi+json"},
        timeout=20,
    )
    response.raise_for_status()
    paths = response.json().get("paths", {})
    ruleset_paths = sorted(path for path in paths if "ruleset" in path)

    assert "/rpc/approve_janani_clinical_safety_ruleset" in paths, ruleset_paths
    assert "/rpc/activate_janani_clinical_safety_ruleset" in paths, ruleset_paths
    assert "/rpc/rollback_janani_clinical_safety_ruleset" in paths, ruleset_paths


def test_ruleset_approval_named_payload_matches_postgrest_signature() -> None:
    assert SUPABASE_URL is not None
    now = datetime.now(UTC)
    response = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/approve_janani_clinical_safety_ruleset",
        headers=service_headers(),
        json={
            "p_ruleset_id": str(uuid4()),
            "p_version": "signature-diagnostic",
            "p_required_rule_ids": ["DIAGNOSTIC-RULE"],
            "p_release_ids": [str(uuid4())],
            "p_activates_at": (now + timedelta(minutes=1)).isoformat(),
            "p_expires_at": (now + timedelta(days=1)).isoformat(),
            "p_supersedes_ruleset_id": None,
        },
        timeout=20,
    )
    body = response.json()

    assert body.get("code") != "PGRST202", body
