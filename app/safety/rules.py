from collections.abc import Callable
from dataclasses import dataclass

from app.safety.models import (
    RuleMetadata,
    RuleStatus,
    SafetySeverity,
    SymptomAssessmentRequest,
)

DEVELOPMENT_RULESET_VERSION = "dev-2026-08-03.1"


@dataclass(frozen=True, slots=True)
class SafetyRule:
    metadata: RuleMetadata
    predicate: Callable[[SymptomAssessmentRequest], bool]

    def matches(self, payload: SymptomAssessmentRequest) -> bool:
        return bool(self.predicate(payload))


def _draft_rule(
    rule_id: str,
    severity: SafetySeverity,
    response_template: str,
    predicate: Callable[[SymptomAssessmentRequest], bool],
) -> SafetyRule:
    return SafetyRule(
        metadata=RuleMetadata(
            rule_id=rule_id,
            version="0.1.0-draft",
            status=RuleStatus.DRAFT,
            severity=severity,
            response_template=response_template,
            clinician_signoff_id=None,
        ),
        predicate=predicate,
    )


def build_development_rules() -> tuple[SafetyRule, ...]:
    """Draft rules for synthetic engineering tests; not approved for patient use."""

    emergency = (
        "The information entered may require emergency medical assessment. "
        "Contact local emergency services or an appropriate maternity facility now."
    )
    urgent = (
        "The information entered may require prompt medical assessment. "
        "Contact your maternity care team or an appropriate healthcare facility now."
    )

    return (
        _draft_rule(
            "DEV-SEIZURE-001",
            SafetySeverity.EMERGENCY,
            emergency,
            lambda item: item.seizure,
        ),
        _draft_rule(
            "DEV-LOSS-CONSCIOUSNESS-001",
            SafetySeverity.EMERGENCY,
            emergency,
            lambda item: item.loss_of_consciousness,
        ),
        _draft_rule(
            "DEV-BREATHING-001",
            SafetySeverity.EMERGENCY,
            emergency,
            lambda item: item.severe_breathing_difficulty,
        ),
        _draft_rule(
            "DEV-HEAVY-BLEEDING-001",
            SafetySeverity.URGENT,
            urgent,
            lambda item: item.heavy_bleeding,
        ),
        _draft_rule(
            "DEV-SEVERE-PAIN-001",
            SafetySeverity.URGENT,
            urgent,
            lambda item: item.severe_abdominal_pain,
        ),
        _draft_rule(
            "DEV-REDUCED-MOVEMENT-001",
            SafetySeverity.URGENT,
            urgent,
            lambda item: item.reduced_fetal_movement,
        ),
        _draft_rule(
            "DEV-HEADACHE-VISION-001",
            SafetySeverity.URGENT,
            urgent,
            lambda item: item.severe_headache and item.vision_changes,
        ),
    )
