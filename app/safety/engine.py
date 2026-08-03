from uuid import uuid4

from app.safety.models import (
    RuleStatus,
    SafetyDecision,
    SafetySeverity,
    SymptomAssessmentRequest,
)
from app.safety.rules import SafetyRule

_SEVERITY_ORDER = {
    SafetySeverity.ROUTINE: 0,
    SafetySeverity.CONTACT_CLINICIAN: 1,
    SafetySeverity.URGENT: 2,
    SafetySeverity.EMERGENCY: 3,
    SafetySeverity.INSUFFICIENT_INFORMATION: 4,
}


class SafetyEngine:
    """Pure deterministic evaluator. It never calls an LLM."""

    def __init__(
        self,
        rules: tuple[SafetyRule, ...],
        ruleset_version: str,
        *,
        allow_unapproved: bool = False,
    ) -> None:
        self._all_rules = rules
        self._ruleset_version = ruleset_version
        self._allow_unapproved = allow_unapproved
        self._eligible_rules = tuple(rule for rule in rules if self._is_eligible(rule))

    def _is_eligible(self, rule: SafetyRule) -> bool:
        if self._allow_unapproved:
            return rule.metadata.status is not RuleStatus.RETIRED
        return rule.metadata.is_clinically_approved

    @property
    def clinical_ready(self) -> bool:
        return bool(self._eligible_rules) and all(
            rule.metadata.is_clinically_approved for rule in self._eligible_rules
        )

    @property
    def readiness_reasons(self) -> list[str]:
        reasons: list[str] = []
        if not self._eligible_rules:
            reasons.append("No eligible safety rules are active")
        if not self.clinical_ready:
            reasons.append("The active ruleset lacks complete clinician approval")
        if self._allow_unapproved:
            reasons.append("Development mode permits draft rules for synthetic tests")
        return reasons

    def evaluate(self, payload: SymptomAssessmentRequest) -> SafetyDecision:
        if not self._eligible_rules:
            return SafetyDecision(
                event_id=uuid4(),
                triggered=False,
                severity=SafetySeverity.INSUFFICIENT_INFORMATION,
                triggered_rule_ids=[],
                message=(
                    "No clinician-approved safety ruleset is active. The system cannot assess "
                    "this information; contact a qualified healthcare professional."
                ),
                blocks_llm=True,
                ruleset_version=self._ruleset_version,
                ruleset_clinically_approved=False,
                development_only=False,
                disclaimer="Janani AI does not diagnose or replace professional medical care.",
            )

        matched = [rule for rule in self._eligible_rules if rule.matches(payload)]
        approved = all(rule.metadata.is_clinically_approved for rule in self._eligible_rules)

        if not matched:
            return SafetyDecision(
                event_id=uuid4(),
                triggered=False,
                severity=SafetySeverity.ROUTINE,
                triggered_rule_ids=[],
                message=(
                    "No configured warning-sign rule was triggered by the structured inputs. "
                    "This does not establish that the situation is safe or replace assessment."
                ),
                blocks_llm=False,
                ruleset_version=self._ruleset_version,
                ruleset_clinically_approved=approved,
                development_only=not approved,
                disclaimer="Janani AI does not diagnose or replace professional medical care.",
            )

        highest = max(matched, key=lambda rule: _SEVERITY_ORDER[rule.metadata.severity])
        return SafetyDecision(
            event_id=uuid4(),
            triggered=True,
            severity=highest.metadata.severity,
            triggered_rule_ids=[rule.metadata.rule_id for rule in matched],
            message=highest.metadata.response_template,
            blocks_llm=True,
            ruleset_version=self._ruleset_version,
            ruleset_clinically_approved=approved,
            development_only=not approved,
            disclaimer="Janani AI does not diagnose or replace professional medical care.",
        )
