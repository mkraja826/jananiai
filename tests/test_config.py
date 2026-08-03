import pytest
from pydantic import ValidationError

from app.config import Settings


def test_free_first_mode_rejects_real_patient_data() -> None:
    with pytest.raises(ValidationError):
        Settings(free_first_mode=True, allow_real_patient_data=True)


def test_free_first_mode_rejects_non_mock_provider() -> None:
    with pytest.raises(ValidationError):
        Settings(free_first_mode=True, llm_provider="hosted-provider")


def test_development_mode_allows_draft_rules_for_synthetic_tests() -> None:
    settings = Settings(environment="development", free_first_mode=True)

    assert settings.allow_unapproved_safety_rules is True


def test_production_mode_never_allows_draft_rules() -> None:
    settings = Settings(environment="production", free_first_mode=True)

    assert settings.allow_unapproved_safety_rules is False
