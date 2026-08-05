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


def test_supabase_configuration_uses_publishable_key_for_user_paths() -> None:
    settings = protected_settings()

    assert settings.supabase_configured is True
    assert settings.supabase_service_role_configured is False
    assert settings.normalized_supabase_url == "https://synthetic-project.supabase.co"


def test_governance_admin_api_is_disabled_by_default() -> None:
    settings = protected_settings()

    assert settings.governance_admin_api_enabled is False
    assert settings.supabase_service_role_configured is False


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {
                "auth_required": False,
                "supabase_url": "https://synthetic-project.supabase.co",
                "supabase_publishable_key": "sb_publishable_synthetic",
                "supabase_service_role_key": "synthetic-service-role",
            },
            "requires authentication",
        ),
        (
            {
                "auth_required": True,
                "supabase_service_role_key": "synthetic-service-role",
            },
            "requires Supabase configuration",
        ),
        (
            {
                "auth_required": True,
                "supabase_url": "https://synthetic-project.supabase.co",
                "supabase_publishable_key": "sb_publishable_synthetic",
            },
            "backend-only Supabase service-role key",
        ),
    ],
)
def test_governance_admin_api_requires_complete_server_configuration(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(
            environment="development",
            governance_admin_api_enabled=True,
            **overrides,
        )


def test_governance_admin_api_accepts_backend_only_service_role_configuration() -> None:
    settings = Settings(
        environment="development",
        auth_required=True,
        supabase_url="https://synthetic-project.supabase.co/",
        supabase_publishable_key="sb_publishable_synthetic",
        supabase_service_role_key="synthetic-service-role",
        governance_admin_api_enabled=True,
    )

    assert settings.governance_admin_api_enabled
    assert settings.supabase_service_role_configured
    assert settings.normalized_supabase_url == "https://synthetic-project.supabase.co"
    assert "synthetic-service-role" not in repr(settings)
