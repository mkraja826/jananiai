"""Synthetic incident-response rehearsal for deterministic safety rulesets.

The rehearsal runner exercises the existing atomic rollback domain service and
produces an immutable evidence record. It is intentionally synthetic-only and
cannot be treated as production incident handling or clinical authorisation.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.safety.governance import SafetyRuleRelease
from app.safety.rulesets import (
    RulesetStatus,
    RulesetTransition,
    SafetyRulesetGovernanceService,
    SafetyRulesetRelease,
)


class RehearsalScenario(StrEnum):
    EMERGENCY_RULESET_ROLLBACK = "emergency_ruleset_rollback"


class RehearsalStepName(StrEnum):
    DETECT_INCIDENT = "detect_incident"
    VERIFY_ACTIVE_MANIFEST = "verify_active_manifest"
    EXECUTE_ATOMIC_ROLLBACK = "execute_atomic_rollback"
    VERIFY_RESTORED_MANIFEST = "verify_restored_manifest"
    VERIFY_ROLLED_BACK_STATE = "verify_rolled_back_state"
    RECORD_AUDIT_EVIDENCE = "record_audit_evidence"


REQUIRED_ROLLBACK_STEPS = frozenset(RehearsalStepName)


class FrozenRehearsalModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SafetyRehearsalStep(FrozenRehearsalModel):
    name: RehearsalStepName
    passed: bool
    evidence_ref: Annotated[str, Field(min_length=8, max_length=240)]


class SafetyIncidentRehearsalReport(FrozenRehearsalModel):
    rehearsal_id: UUID = Field(default_factory=uuid4)
    scenario: RehearsalScenario
    started_at: datetime
    completed_at: datetime
    active_ruleset_before: UUID
    restored_ruleset_after: UUID
    rolled_back_ruleset: UUID
    reason: Annotated[str, Field(min_length=10, max_length=1000)]
    steps: Annotated[tuple[SafetyRehearsalStep, ...], Field(min_length=1)]
    synthetic_only: bool = True

    @model_validator(mode="after")
    def validate_report(self) -> "SafetyIncidentRehearsalReport":
        if not self.synthetic_only:
            raise ValueError("Current incident rehearsals must be synthetic only")
        if self.started_at.utcoffset() is None or self.completed_at.utcoffset() is None:
            raise ValueError("Rehearsal timestamps must include timezone information")
        if self.completed_at < self.started_at:
            raise ValueError("Rehearsal completion cannot precede its start")
        names = [step.name for step in self.steps]
        if len(set(names)) != len(names):
            raise ValueError("Rehearsal step names must be unique")
        missing = REQUIRED_ROLLBACK_STEPS - set(names)
        if missing:
            raise ValueError(
                "Rollback rehearsal is missing required steps: "
                f"{sorted(step.value for step in missing)}"
            )
        if self.active_ruleset_before == self.restored_ruleset_after:
            raise ValueError("Rollback rehearsal must restore a distinct prior ruleset")
        if self.rolled_back_ruleset != self.active_ruleset_before:
            raise ValueError("Rolled-back ruleset must equal the active pre-incident ruleset")
        return self

    @property
    def passed(self) -> bool:
        return all(step.passed for step in self.steps)


class EmergencyRollbackRehearsalResult(FrozenRehearsalModel):
    transition: RulesetTransition
    report: SafetyIncidentRehearsalReport


class EmergencyRollbackRehearsalRunner:
    def run(
        self,
        service: SafetyRulesetGovernanceService,
        active_ruleset: SafetyRulesetRelease,
        active_releases: tuple[SafetyRuleRelease, ...],
        replacement_ruleset: SafetyRulesetRelease,
        replacement_releases: tuple[SafetyRuleRelease, ...],
        *,
        reason: str,
        rehearsed_at: datetime | None = None,
    ) -> EmergencyRollbackRehearsalResult:
        started_at = rehearsed_at or datetime.now(UTC)
        if active_ruleset.status is not RulesetStatus.ACTIVE:
            raise ValueError("Rollback rehearsal requires an active ruleset")
        if replacement_ruleset.ruleset_id == active_ruleset.ruleset_id:
            raise ValueError("Rollback rehearsal requires a distinct prior ruleset")

        transition = service.rollback_ruleset(
            active_ruleset,
            active_releases,
            replacement_ruleset,
            replacement_releases,
            reason,
            rolled_back_at=started_at,
        )
        restored_ids = {release.release_id for release in transition.active_releases}
        expected_ids = {release.release_id for release in replacement_releases}
        rolled_back_ok = (
            transition.prior_ruleset is not None
            and transition.prior_ruleset.ruleset_id == active_ruleset.ruleset_id
            and transition.prior_ruleset.status is RulesetStatus.ROLLED_BACK
        )
        restored_ok = (
            transition.active_ruleset.ruleset_id == replacement_ruleset.ruleset_id
            and transition.active_ruleset.status is RulesetStatus.ACTIVE
            and restored_ids == expected_ids
        )

        steps = (
            SafetyRehearsalStep(
                name=RehearsalStepName.DETECT_INCIDENT,
                passed=True,
                evidence_ref=f"synthetic://rehearsal/{active_ruleset.ruleset_id}/incident",
            ),
            SafetyRehearsalStep(
                name=RehearsalStepName.VERIFY_ACTIVE_MANIFEST,
                passed=True,
                evidence_ref=f"synthetic://ruleset/{active_ruleset.ruleset_id}/verified",
            ),
            SafetyRehearsalStep(
                name=RehearsalStepName.EXECUTE_ATOMIC_ROLLBACK,
                passed=transition.prior_ruleset is not None,
                evidence_ref=f"synthetic://ruleset/{active_ruleset.ruleset_id}/rollback",
            ),
            SafetyRehearsalStep(
                name=RehearsalStepName.VERIFY_RESTORED_MANIFEST,
                passed=restored_ok,
                evidence_ref=f"synthetic://ruleset/{replacement_ruleset.ruleset_id}/restored",
            ),
            SafetyRehearsalStep(
                name=RehearsalStepName.VERIFY_ROLLED_BACK_STATE,
                passed=rolled_back_ok,
                evidence_ref=f"synthetic://ruleset/{active_ruleset.ruleset_id}/rolled-back",
            ),
            SafetyRehearsalStep(
                name=RehearsalStepName.RECORD_AUDIT_EVIDENCE,
                passed=restored_ok and rolled_back_ok,
                evidence_ref=f"synthetic://rehearsal/{active_ruleset.ruleset_id}/audit",
            ),
        )
        report = SafetyIncidentRehearsalReport(
            scenario=RehearsalScenario.EMERGENCY_RULESET_ROLLBACK,
            started_at=started_at,
            completed_at=started_at,
            active_ruleset_before=active_ruleset.ruleset_id,
            restored_ruleset_after=replacement_ruleset.ruleset_id,
            rolled_back_ruleset=active_ruleset.ruleset_id,
            reason=reason,
            steps=steps,
        )
        return EmergencyRollbackRehearsalResult(
            transition=transition,
            report=report,
        )
