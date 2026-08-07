import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.safety.governance import ReleaseStatus, ReviewerRole, SafetyRuleRelease
from app.safety.rehearsal import (
    EmergencyRollbackRehearsalRunner,
    RehearsalScenario,
    RehearsalStepName,
    SafetyIncidentRehearsalReport,
    SafetyRehearsalStep,
)
from app.safety.rulesets import RulesetStatus, SafetyRulesetGovernanceService

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def release(rule_id: str) -> SafetyRuleRelease:
    return SafetyRuleRelease(
        release_id=uuid4(),
        candidate_id=uuid4(),
        rule_id=rule_id,
        rule_version="1.0.0",
        candidate_digest=hashlib.sha256(rule_id.encode()).hexdigest(),
        approval_review_ids=(uuid4(), uuid4()),
        reviewer_ids=(uuid4(), uuid4()),
        reviewer_roles=(ReviewerRole.OBSTETRICIAN, ReviewerRole.CLINICAL_SAFETY),
        status=ReleaseStatus.APPROVED,
        approved_at=NOW - timedelta(days=1),
        activates_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=90),
    )


def active_and_prior_rulesets():
    service = SafetyRulesetGovernanceService()
    first_releases = (release("RULE-A"), release("RULE-B"))
    first = service.approve_ruleset(
        first_releases,
        version="synthetic-ruleset-1",
        required_rule_ids=("RULE-A", "RULE-B"),
        approved_at=NOW - timedelta(hours=2),
        activates_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=30),
    )
    first_active = service.activate_ruleset(first, first_releases, activated_at=NOW)

    second_releases = (release("RULE-A"), release("RULE-B"))
    second = service.approve_ruleset(
        second_releases,
        version="synthetic-ruleset-2",
        required_rule_ids=("RULE-A", "RULE-B"),
        approved_at=NOW - timedelta(minutes=30),
        activates_at=NOW - timedelta(minutes=10),
        expires_at=NOW + timedelta(days=30),
        supersedes_ruleset_id=first.ruleset_id,
    )
    second_active = service.activate_ruleset(
        second,
        second_releases,
        active_ruleset=first_active.active_ruleset,
        active_releases=first_active.active_releases,
        activated_at=NOW,
        reason="Synthetic planned replacement before emergency rehearsal",
    )
    assert second_active.prior_ruleset is not None
    return service, second_active


def test_emergency_rehearsal_restores_exact_prior_ruleset() -> None:
    service, second_active = active_and_prior_rulesets()
    assert second_active.prior_ruleset is not None

    result = EmergencyRollbackRehearsalRunner().run(
        service,
        second_active.active_ruleset,
        second_active.active_releases,
        second_active.prior_ruleset,
        second_active.prior_releases,
        reason="Synthetic emergency rehearsal after detected safety regression",
        rehearsed_at=NOW + timedelta(minutes=1),
    )

    assert result.report.scenario is RehearsalScenario.EMERGENCY_RULESET_ROLLBACK
    assert result.report.synthetic_only
    assert result.report.passed
    assert result.transition.active_ruleset.status is RulesetStatus.ACTIVE
    assert result.transition.active_ruleset.version == "synthetic-ruleset-1"
    assert result.transition.prior_ruleset is not None
    assert result.transition.prior_ruleset.status is RulesetStatus.ROLLED_BACK
    assert {step.name for step in result.report.steps} == set(RehearsalStepName)
    assert all(step.evidence_ref.startswith("synthetic://") for step in result.report.steps)


def test_rehearsal_rejects_non_active_or_same_ruleset() -> None:
    service, second_active = active_and_prior_rulesets()
    assert second_active.prior_ruleset is not None

    with pytest.raises(ValueError, match="requires an active ruleset"):
        EmergencyRollbackRehearsalRunner().run(
            service,
            second_active.active_ruleset.model_copy(update={"status": RulesetStatus.RETIRED}),
            second_active.active_releases,
            second_active.prior_ruleset,
            second_active.prior_releases,
            reason="Synthetic invalid rehearsal state should fail closed",
            rehearsed_at=NOW + timedelta(minutes=1),
        )

    with pytest.raises(ValueError, match="distinct prior ruleset"):
        EmergencyRollbackRehearsalRunner().run(
            service,
            second_active.active_ruleset,
            second_active.active_releases,
            second_active.active_ruleset,
            second_active.active_releases,
            reason="Synthetic same-ruleset rehearsal should fail closed",
            rehearsed_at=NOW + timedelta(minutes=1),
        )


def test_rehearsal_report_requires_all_steps_and_synthetic_mode() -> None:
    steps = (
        SafetyRehearsalStep(
            name=RehearsalStepName.DETECT_INCIDENT,
            passed=True,
            evidence_ref="synthetic://incident/example",
        ),
    )

    with pytest.raises(ValidationError, match="missing required steps"):
        SafetyIncidentRehearsalReport(
            scenario=RehearsalScenario.EMERGENCY_RULESET_ROLLBACK,
            started_at=NOW,
            completed_at=NOW,
            active_ruleset_before=uuid4(),
            restored_ruleset_after=uuid4(),
            rolled_back_ruleset=uuid4(),
            reason="Synthetic incomplete rehearsal report validation.",
            steps=steps,
        )

    complete_steps = tuple(
        SafetyRehearsalStep(
            name=name,
            passed=True,
            evidence_ref=f"synthetic://rehearsal/{name.value}",
        )
        for name in RehearsalStepName
    )
    active_id = uuid4()
    with pytest.raises(ValidationError, match="synthetic only"):
        SafetyIncidentRehearsalReport(
            scenario=RehearsalScenario.EMERGENCY_RULESET_ROLLBACK,
            started_at=NOW,
            completed_at=NOW,
            active_ruleset_before=active_id,
            restored_ruleset_after=uuid4(),
            rolled_back_ruleset=active_id,
            reason="Non-synthetic rehearsal reports are not allowed at this phase.",
            steps=complete_steps,
            synthetic_only=False,
        )
