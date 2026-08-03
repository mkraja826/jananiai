from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.safety.engine import SafetyEngine
from app.safety.models import RuleMetadata, RuleStatus, SafetySeverity
from app.safety.rules import build_development_rules


def production_settings() -> Settings:
    return Settings(
        environment="production",
        free_first_mode=True,
        auth_required=True,
        supabase_url="https://synthetic-project.supabase.co",
        supabase_publishable_key="sb_publishable_synthetic",
    )


def test_production_startup_is_blocked_without_approved_rules() -> None:
    settings = production_settings()
    engine = SafetyEngine(build_development_rules(), "production-test", allow_unapproved=False)

    with pytest.raises(RuntimeError, match="Production startup blocked"):
        create_app(settings=settings, safety_engine=engine)


def test_production_startup_accepts_current_approved_ruleset() -> None:
    approved_at = datetime.now(UTC)
    draft = build_development_rules()[0]
    approved = replace(
        draft,
        metadata=RuleMetadata(
            rule_id="TEST-PRODUCTION-001",
            version="1.0.0",
            status=RuleStatus.APPROVED,
            severity=SafetySeverity.EMERGENCY,
            response_template="Approved test escalation.",
            clinician_signoff_id="synthetic-clinician-id",
            approved_at=approved_at,
            next_review_at=approved_at + timedelta(days=30),
        ),
    )
    engine = SafetyEngine((approved,), "approved-production-test", allow_unapproved=False)

    application = create_app(settings=production_settings(), safety_engine=engine)
    response = TestClient(application).get("/ready")

    assert response.status_code == 200
    assert response.json()["clinical_ready"] is True
