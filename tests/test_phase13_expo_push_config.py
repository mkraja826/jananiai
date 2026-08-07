import pytest
from pydantic import ValidationError

from app.config import Settings


def worker_settings(**overrides) -> Settings:
    values = {
        "environment": "development",
        "auth_required": True,
        "supabase_url": "https://synthetic-project.supabase.co",
        "supabase_publishable_key": "sb_publishable_synthetic",
        "supabase_service_role_key": "synthetic-service-role",
        "reminder_worker_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_reminder_worker_defaults_to_network_free_mock_transport() -> None:
    settings = worker_settings()

    assert settings.reminder_worker_transport == "mock"
    assert settings.expo_push_configured is False


def test_expo_worker_requires_backend_push_access_token() -> None:
    with pytest.raises(ValidationError, match="Expo reminder transport requires"):
        worker_settings(reminder_worker_transport="expo")


def test_expo_worker_accepts_secret_backend_configuration() -> None:
    settings = worker_settings(
        reminder_worker_transport="expo",
        expo_push_access_token="synthetic-expo-secret",
        expo_push_timeout_seconds=5,
    )

    assert settings.reminder_worker_transport == "expo"
    assert settings.expo_push_configured is True
    assert settings.expo_push_access_token is not None
    assert settings.expo_push_access_token.get_secret_value() == "synthetic-expo-secret"
    assert "synthetic-expo-secret" not in repr(settings)


def test_expo_push_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="Expo push timeout must be positive"):
        Settings(expo_push_timeout_seconds=0)


def test_production_worker_remains_blocked_even_with_expo_credentials() -> None:
    with pytest.raises(ValidationError, match="Production reminder worker remains blocked"):
        worker_settings(
            environment="production",
            reminder_worker_transport="expo",
            expo_push_access_token="synthetic-expo-secret",
        )
