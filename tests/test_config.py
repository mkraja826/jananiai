import pytest
from pydantic import ValidationError

from app.config import Settings


def protected_settings(environment: str = "production") -> Settings:
    return Settings(
        environment=environment,
        free_first_mode=True,
        auth_required=True,
        supabase_url="https://synthetic-project.supabase.co",
        supabase_publishable_key="sb_publishable_synthetic",
    )


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
    settings = protected_settings()

    assert settings.allow_unapproved_safety_rules is False


def test_staging_requires_authentication() -> None:
    with pytest.raises(ValidationError, match="Authentication must be required"):
        Settings(environment="staging", auth_required=False)


def test_protected_environment_requires_supabase_configuration() -> None:
    with pytest.raises(ValidationError, match="Supabase URL and publishable key"):
        Settings(environment="production", auth_required=True)


def test_supabase_configuration_uses_publishable_key_only() -> None:
    settings = protected_settings()

    assert settings.supabase_configured is True
    assert settings.normalized_supabase_url == "https://synthetic-project.supabase.co"
