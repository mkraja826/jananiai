from collections import Counter

import pytest
from pydantic import ValidationError

from app.safety.engine import SafetyEngine
from app.safety.models import SafetySeverity, SymptomAssessmentRequest
from app.safety.rules import DEVELOPMENT_RULESET_VERSION, build_development_rules
from app.safety.validation import (
    REQUIRED_CASE_CATEGORIES,
    SafetyRuleValidationDataset,
    SafetyValidationCase,
    SafetyValidationExpectation,
    SafetyValidationRunner,
    ValidationCaseCategory,
    build_development_validation_dataset,
)


def development_engine() -> SafetyEngine:
    return SafetyEngine(
        rules=build_development_rules(),
        ruleset_version=DEVELOPMENT_RULESET_VERSION,
        allow_unapproved=True,
    )


def routine_expectation() -> SafetyValidationExpectation:
    return SafetyValidationExpectation(
        triggered=False,
        severity=SafetySeverity.ROUTINE,
        blocks_llm=False,
    )


def valid_case(**updates: object) -> SafetyValidationCase:
    values: dict[str, object] = {
        "case_id": "DEV-SEIZURE-001-example-case",
        "target_rule_id": "DEV-SEIZURE-001",
        "category": ValidationCaseCategory.TRUE_POSITIVE,
        "payload": SymptomAssessmentRequest(is_synthetic=True, seizure=True),
        "expected": SafetyValidationExpectation(
            triggered=True,
            severity=SafetySeverity.EMERGENCY,
            exact_rule_ids=("DEV-SEIZURE-001",),
            blocks_llm=True,
        ),
        "rationale": "Synthetic positive case used to validate the test contract.",
    }
    values.update(updates)
    return SafetyValidationCase(**values)


def test_development_dataset_covers_every_rule_and_required_category() -> None:
    dataset = build_development_validation_dataset()
    expected_rule_ids = {rule.metadata.rule_id for rule in build_development_rules()}
    counts = Counter(case.target_rule_id for case in dataset.cases)

    assert dataset.dataset_version == "dev-validation-2026-08-05.1"
    assert dataset.ruleset_version == DEVELOPMENT_RULESET_VERSION
    assert len(dataset.cases) == 35
    assert set(counts) == expected_rule_ids
    assert set(counts.values()) == {5}
    for rule_id in expected_rule_ids:
        categories = {case.category for case in dataset.cases if case.target_rule_id == rule_id}
        assert categories == REQUIRED_CASE_CATEGORIES


def test_development_dataset_passes_the_current_deterministic_engine() -> None:
    report = SafetyValidationRunner().run(
        build_development_validation_dataset(),
        development_engine(),
    )

    assert report.all_passed
    assert report.total_cases == 35
    assert report.passed_cases == 35
    assert report.failed_cases == 0
    assert set(report.cases_by_rule.values()) == {5}
    assert all(result.passed and not result.mismatches for result in report.results)


def test_runner_reports_trigger_severity_rule_and_blocking_mismatches() -> None:
    dataset = SafetyRuleValidationDataset(
        dataset_version="mismatch-test",
        ruleset_version=DEVELOPMENT_RULESET_VERSION,
        cases=build_development_validation_dataset().cases,
    )
    unavailable_engine = SafetyEngine(
        rules=(),
        ruleset_version="none",
        allow_unapproved=False,
    )

    report = SafetyValidationRunner().run(dataset, unavailable_engine)
    positive = next(
        result
        for result in report.results
        if result.category is ValidationCaseCategory.TRUE_POSITIVE
    )
    negative = next(
        result
        for result in report.results
        if result.category is ValidationCaseCategory.TRUE_NEGATIVE
    )

    assert not report.all_passed
    assert report.failed_cases == report.total_cases
    assert any("triggered expected" in item for item in positive.mismatches)
    assert any("severity expected" in item for item in positive.mismatches)
    assert any("triggered rule IDs expected" in item for item in positive.mismatches)
    assert not any("blocks_llm expected" in item for item in positive.mismatches)
    assert any("severity expected" in item for item in negative.mismatches)
    assert any("blocks_llm expected" in item for item in negative.mismatches)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "triggered": True,
                "severity": SafetySeverity.URGENT,
                "exact_rule_ids": (),
                "blocks_llm": True,
            },
            "at least one rule ID",
        ),
        (
            {
                "triggered": False,
                "severity": SafetySeverity.ROUTINE,
                "exact_rule_ids": ("DEV-SEIZURE-001",),
                "blocks_llm": False,
            },
            "cannot contain rule IDs",
        ),
        (
            {
                "triggered": True,
                "severity": SafetySeverity.EMERGENCY,
                "exact_rule_ids": ("DEV-SEIZURE-001", "DEV-SEIZURE-001"),
                "blocks_llm": True,
            },
            "must be unique",
        ),
        (
            {
                "triggered": True,
                "severity": SafetySeverity.EMERGENCY,
                "exact_rule_ids": ("DEV-SEIZURE-001",),
                "blocks_llm": False,
            },
            "must block the LLM",
        ),
    ],
)
def test_expectation_validation_fails_closed(payload: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        SafetyValidationExpectation(**payload)


def test_case_requires_synthetic_payload() -> None:
    with pytest.raises(ValidationError, match="must use synthetic data"):
        valid_case(
            payload=SymptomAssessmentRequest(is_synthetic=False, seizure=True),
        )


def test_true_positive_requires_target_rule() -> None:
    with pytest.raises(ValidationError, match="must trigger their target rule"):
        valid_case(
            expected=SafetyValidationExpectation(
                triggered=True,
                severity=SafetySeverity.URGENT,
                exact_rule_ids=("DEV-HEAVY-BLEEDING-001",),
                blocks_llm=True,
            )
        )


def test_boundary_requires_supported_endpoint_week() -> None:
    with pytest.raises(ValidationError, match="week 0 or 45"):
        valid_case(
            category=ValidationCaseCategory.BOUNDARY,
            payload=SymptomAssessmentRequest(
                is_synthetic=True,
                gestational_week=20,
                seizure=True,
            ),
        )


def test_interaction_requires_multiple_expected_rules() -> None:
    with pytest.raises(ValidationError, match="at least two rules"):
        valid_case(category=ValidationCaseCategory.INTERACTION)


def test_regression_requires_ignored_free_text_documentation() -> None:
    with pytest.raises(ValidationError, match="must document"):
        valid_case(
            category=ValidationCaseCategory.REGRESSION,
            payload=SymptomAssessmentRequest(is_synthetic=True),
            expected=routine_expectation(),
        )


def test_dataset_rejects_duplicate_case_ids() -> None:
    dataset = build_development_validation_dataset()
    duplicate = dataset.cases[0].model_copy(
        update={"target_rule_id": dataset.cases[1].target_rule_id}
    )

    with pytest.raises(ValidationError, match="case IDs must be unique"):
        SafetyRuleValidationDataset(
            dataset_version="duplicate-test",
            ruleset_version=dataset.ruleset_version,
            cases=(dataset.cases[0], duplicate, *dataset.cases[2:]),
        )


def test_dataset_requires_every_development_rule() -> None:
    dataset = build_development_validation_dataset()
    reduced = tuple(case for case in dataset.cases if case.target_rule_id != "DEV-SEIZURE-001")

    with pytest.raises(ValidationError, match="cover every development rule"):
        SafetyRuleValidationDataset(
            dataset_version="missing-rule-test",
            ruleset_version=dataset.ruleset_version,
            cases=reduced,
        )


def test_dataset_requires_all_categories_for_each_rule() -> None:
    dataset = build_development_validation_dataset()
    reduced = tuple(
        case
        for case in dataset.cases
        if not (
            case.target_rule_id == "DEV-SEIZURE-001"
            and case.category is ValidationCaseCategory.REGRESSION
        )
    )

    with pytest.raises(ValidationError, match="missing validation categories"):
        SafetyRuleValidationDataset(
            dataset_version="missing-category-test",
            ruleset_version=dataset.ruleset_version,
            cases=reduced,
        )
