"""Executable synthetic validation datasets for deterministic safety rules.

These contracts do not clinically validate a rule. They enforce engineering
coverage for expected positives, negatives, boundaries, interactions, and
regressions before a candidate can be considered for clinician review.
"""

from collections import Counter, defaultdict
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.safety.engine import SafetyEngine
from app.safety.models import SafetySeverity, SymptomAssessmentRequest
from app.safety.rules import DEVELOPMENT_RULESET_VERSION, build_development_rules


class ValidationCaseCategory(StrEnum):
    TRUE_POSITIVE = "true_positive"
    TRUE_NEGATIVE = "true_negative"
    BOUNDARY = "boundary"
    INTERACTION = "interaction"
    REGRESSION = "regression"


REQUIRED_CASE_CATEGORIES = frozenset(ValidationCaseCategory)


class FrozenValidationModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SafetyValidationExpectation(FrozenValidationModel):
    triggered: bool
    severity: SafetySeverity
    exact_rule_ids: tuple[str, ...] = ()
    blocks_llm: bool

    @model_validator(mode="after")
    def validate_expectation(self) -> "SafetyValidationExpectation":
        if self.triggered and not self.exact_rule_ids:
            raise ValueError("Triggered expectations require at least one rule ID")
        if not self.triggered and self.exact_rule_ids:
            raise ValueError("Non-triggered expectations cannot contain rule IDs")
        if len(set(self.exact_rule_ids)) != len(self.exact_rule_ids):
            raise ValueError("Expected rule IDs must be unique")
        if self.triggered and not self.blocks_llm:
            raise ValueError("Triggered safety expectations must block the LLM")
        return self


class SafetyValidationCase(FrozenValidationModel):
    case_id: Annotated[str, Field(min_length=5, max_length=160)]
    target_rule_id: Annotated[str, Field(min_length=3, max_length=120)]
    category: ValidationCaseCategory
    payload: SymptomAssessmentRequest
    expected: SafetyValidationExpectation
    rationale: Annotated[str, Field(min_length=20, max_length=1000)]

    @model_validator(mode="after")
    def validate_case(self) -> "SafetyValidationCase":
        if not self.payload.is_synthetic:
            raise ValueError("Safety validation cases must use synthetic data")
        if (
            self.category is ValidationCaseCategory.TRUE_POSITIVE
            and self.target_rule_id not in self.expected.exact_rule_ids
        ):
            raise ValueError("True-positive cases must trigger their target rule")
        if (
            self.category is ValidationCaseCategory.BOUNDARY
            and self.payload.gestational_week not in {0, 45}
        ):
            raise ValueError("Boundary cases must use gestational week 0 or 45")
        if (
            self.category is ValidationCaseCategory.INTERACTION
            and len(self.expected.exact_rule_ids) < 2
        ):
            raise ValueError("Interaction cases must expect at least two rules")
        if self.category is ValidationCaseCategory.REGRESSION and not self.payload.notes:
            raise ValueError("Regression cases must document the ignored free-text input")
        return self


class SafetyRuleValidationDataset(FrozenValidationModel):
    dataset_version: Annotated[str, Field(min_length=1, max_length=80)]
    ruleset_version: Annotated[str, Field(min_length=1, max_length=80)]
    cases: Annotated[tuple[SafetyValidationCase, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_dataset(self) -> "SafetyRuleValidationDataset":
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("Validation case IDs must be unique")

        expected_rule_ids = {rule.metadata.rule_id for rule in build_development_rules()}
        actual_rule_ids = {case.target_rule_id for case in self.cases}
        if actual_rule_ids != expected_rule_ids:
            raise ValueError("Validation dataset must cover every development rule exactly")

        categories_by_rule: dict[str, set[ValidationCaseCategory]] = defaultdict(set)
        for case in self.cases:
            categories_by_rule[case.target_rule_id].add(case.category)
        for rule_id in expected_rule_ids:
            missing = REQUIRED_CASE_CATEGORIES - categories_by_rule[rule_id]
            if missing:
                missing_names = sorted(category.value for category in missing)
                raise ValueError(
                    f"Rule {rule_id} is missing validation categories: {missing_names}"
                )
        return self


class SafetyValidationCaseResult(FrozenValidationModel):
    case_id: str
    target_rule_id: str
    category: ValidationCaseCategory
    passed: bool
    mismatches: tuple[str, ...] = ()


class SafetyValidationReport(FrozenValidationModel):
    dataset_version: str
    ruleset_version: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    results: tuple[SafetyValidationCaseResult, ...]
    cases_by_rule: dict[str, int]

    @property
    def all_passed(self) -> bool:
        return self.failed_cases == 0 and self.total_cases > 0


class SafetyValidationRunner:
    def run(
        self,
        dataset: SafetyRuleValidationDataset,
        engine: SafetyEngine,
    ) -> SafetyValidationReport:
        results = tuple(self._run_case(case, engine) for case in dataset.cases)
        passed = sum(result.passed for result in results)
        counts = Counter(case.target_rule_id for case in dataset.cases)
        return SafetyValidationReport(
            dataset_version=dataset.dataset_version,
            ruleset_version=dataset.ruleset_version,
            total_cases=len(results),
            passed_cases=passed,
            failed_cases=len(results) - passed,
            results=results,
            cases_by_rule=dict(sorted(counts.items())),
        )

    def _run_case(
        self,
        case: SafetyValidationCase,
        engine: SafetyEngine,
    ) -> SafetyValidationCaseResult:
        decision = engine.evaluate(case.payload)
        mismatches: list[str] = []
        if decision.triggered is not case.expected.triggered:
            mismatches.append(
                f"triggered expected {case.expected.triggered} but got {decision.triggered}"
            )
        if decision.severity is not case.expected.severity:
            mismatches.append(
                "severity expected "
                f"{case.expected.severity.value} but got {decision.severity.value}"
            )
        if set(decision.triggered_rule_ids) != set(case.expected.exact_rule_ids):
            expected_ids = sorted(case.expected.exact_rule_ids)
            actual_ids = sorted(decision.triggered_rule_ids)
            mismatches.append(
                f"triggered rule IDs expected {expected_ids} but got {actual_ids}"
            )
        if decision.blocks_llm is not case.expected.blocks_llm:
            mismatches.append(
                f"blocks_llm expected {case.expected.blocks_llm} but got {decision.blocks_llm}"
            )
        return SafetyValidationCaseResult(
            case_id=case.case_id,
            target_rule_id=case.target_rule_id,
            category=case.category,
            passed=not mismatches,
            mismatches=tuple(mismatches),
        )


def _routine_expectation() -> SafetyValidationExpectation:
    return SafetyValidationExpectation(
        triggered=False,
        severity=SafetySeverity.ROUTINE,
        exact_rule_ids=(),
        blocks_llm=False,
    )


def _triggered_expectation(
    severity: SafetySeverity,
    *rule_ids: str,
) -> SafetyValidationExpectation:
    return SafetyValidationExpectation(
        triggered=True,
        severity=severity,
        exact_rule_ids=tuple(rule_ids),
        blocks_llm=True,
    )


def _payload(**updates: object) -> SymptomAssessmentRequest:
    values: dict[str, object] = {
        "is_synthetic": True,
        "gestational_week": 20,
    }
    values.update(updates)
    return SymptomAssessmentRequest(**values)


def build_development_validation_dataset() -> SafetyRuleValidationDataset:
    """Return five executable synthetic cases for every development rule."""

    definitions = (
        ("DEV-SEIZURE-001", "seizure", SafetySeverity.EMERGENCY),
        (
            "DEV-LOSS-CONSCIOUSNESS-001",
            "loss_of_consciousness",
            SafetySeverity.EMERGENCY,
        ),
        (
            "DEV-BREATHING-001",
            "severe_breathing_difficulty",
            SafetySeverity.EMERGENCY,
        ),
        ("DEV-HEAVY-BLEEDING-001", "heavy_bleeding", SafetySeverity.URGENT),
        ("DEV-SEVERE-PAIN-001", "severe_abdominal_pain", SafetySeverity.URGENT),
        (
            "DEV-REDUCED-MOVEMENT-001",
            "reduced_fetal_movement",
            SafetySeverity.URGENT,
        ),
    )
    cases: list[SafetyValidationCase] = []

    for index, (rule_id, field_name, severity) in enumerate(definitions):
        slug = rule_id.lower()
        trigger = {field_name: True}
        boundary_week = 0 if index % 2 == 0 else 45
        if severity is SafetySeverity.EMERGENCY:
            interaction_updates = {**trigger, "heavy_bleeding": True}
            interaction_ids = (rule_id, "DEV-HEAVY-BLEEDING-001")
            interaction_severity = SafetySeverity.EMERGENCY
        else:
            interaction_updates = {**trigger, "seizure": True}
            interaction_ids = ("DEV-SEIZURE-001", rule_id)
            interaction_severity = SafetySeverity.EMERGENCY

        cases.extend(
            (
                SafetyValidationCase(
                    case_id=f"{slug}-true-positive",
                    target_rule_id=rule_id,
                    category=ValidationCaseCategory.TRUE_POSITIVE,
                    payload=_payload(**trigger),
                    expected=_triggered_expectation(severity, rule_id),
                    rationale=(
                        "The target structured boolean is true and must trigger "
                        "exactly its rule."
                    ),
                ),
                SafetyValidationCase(
                    case_id=f"{slug}-true-negative",
                    target_rule_id=rule_id,
                    category=ValidationCaseCategory.TRUE_NEGATIVE,
                    payload=_payload(),
                    expected=_routine_expectation(),
                    rationale=(
                        "All structured warning inputs are false and no configured "
                        "rule should trigger."
                    ),
                ),
                SafetyValidationCase(
                    case_id=f"{slug}-boundary",
                    target_rule_id=rule_id,
                    category=ValidationCaseCategory.BOUNDARY,
                    payload=_payload(gestational_week=boundary_week, **trigger),
                    expected=_triggered_expectation(severity, rule_id),
                    rationale=(
                        "The structured warning must remain deterministic at a "
                        "supported pregnancy-week boundary."
                    ),
                ),
                SafetyValidationCase(
                    case_id=f"{slug}-interaction",
                    target_rule_id=rule_id,
                    category=ValidationCaseCategory.INTERACTION,
                    payload=_payload(**interaction_updates),
                    expected=_triggered_expectation(
                        interaction_severity,
                        *interaction_ids,
                    ),
                    rationale=(
                        "Concurrent warning inputs must preserve every matching rule "
                        "and select the highest severity."
                    ),
                ),
                SafetyValidationCase(
                    case_id=f"{slug}-regression-free-text",
                    target_rule_id=rule_id,
                    category=ValidationCaseCategory.REGRESSION,
                    payload=_payload(
                        notes=(
                            f"Synthetic note mentions {field_name} but the structured "
                            "field is false."
                        )
                    ),
                    expected=_routine_expectation(),
                    rationale=(
                        "Free text must never trigger a deterministic warning without "
                        "its structured boolean."
                    ),
                ),
            )
        )

    headache_rule = "DEV-HEADACHE-VISION-001"
    headache_slug = headache_rule.lower()
    headache_trigger = {"severe_headache": True, "vision_changes": True}
    cases.extend(
        (
            SafetyValidationCase(
                case_id=f"{headache_slug}-true-positive",
                target_rule_id=headache_rule,
                category=ValidationCaseCategory.TRUE_POSITIVE,
                payload=_payload(**headache_trigger),
                expected=_triggered_expectation(
                    SafetySeverity.URGENT,
                    headache_rule,
                ),
                rationale=(
                    "Both structured fields are required and together must trigger "
                    "the combined rule."
                ),
            ),
            SafetyValidationCase(
                case_id=f"{headache_slug}-true-negative",
                target_rule_id=headache_rule,
                category=ValidationCaseCategory.TRUE_NEGATIVE,
                payload=_payload(severe_headache=True, vision_changes=False),
                expected=_routine_expectation(),
                rationale=(
                    "A severe headache without the paired vision-change flag must "
                    "not trigger this combined rule."
                ),
            ),
            SafetyValidationCase(
                case_id=f"{headache_slug}-boundary",
                target_rule_id=headache_rule,
                category=ValidationCaseCategory.BOUNDARY,
                payload=_payload(gestational_week=45, **headache_trigger),
                expected=_triggered_expectation(
                    SafetySeverity.URGENT,
                    headache_rule,
                ),
                rationale=(
                    "The combined structured warning remains deterministic at the "
                    "upper supported week boundary."
                ),
            ),
            SafetyValidationCase(
                case_id=f"{headache_slug}-interaction",
                target_rule_id=headache_rule,
                category=ValidationCaseCategory.INTERACTION,
                payload=_payload(**headache_trigger, seizure=True),
                expected=_triggered_expectation(
                    SafetySeverity.EMERGENCY,
                    "DEV-SEIZURE-001",
                    headache_rule,
                ),
                rationale=(
                    "The urgent combined rule and emergency seizure rule must both "
                    "be retained with emergency severity."
                ),
            ),
            SafetyValidationCase(
                case_id=f"{headache_slug}-regression-free-text",
                target_rule_id=headache_rule,
                category=ValidationCaseCategory.REGRESSION,
                payload=_payload(
                    notes=(
                        "Synthetic note says severe headache and vision changes while "
                        "both structured flags are false."
                    )
                ),
                expected=_routine_expectation(),
                rationale=(
                    "Combined warning words in free text must not bypass the "
                    "structured two-field predicate."
                ),
            ),
        )
    )

    return SafetyRuleValidationDataset(
        dataset_version="dev-validation-2026-08-05.1",
        ruleset_version=DEVELOPMENT_RULESET_VERSION,
        cases=tuple(cases),
    )
