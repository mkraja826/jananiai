import pytest
from pydantic import ValidationError

from app.config import Settings


def test_reminder_worker_is_disabled_by_default() -> None:
    settings = Settings()

    assert settings.reminder_worker_enabled is False
    assert settings.reminder_worker_transport == "mock"
    assert settings.reminder_worker_batch_size == 50
    assert settings.reminder_worker_materialization_lookback_minutes == 15
    assert settings.reminder_worker_materialization_horizon_minutes == 1440


def test_enabled_reminder_worker_requires_backend_supabase_configuration() -> None:
    with pytest.raises(ValidationError, match="service-role key"):
        Settings(reminder_worker_enabled=True)


def test_enabled_reminder_worker_accepts_backend_only_configuration_in_development() -> None:
    settings = Settings(
        reminder_worker_enabled=True,
        supabase_url="http://127.0.0.1:54321/",
        supabase_service_role_key="synthetic-service-role",
    )

    assert settings.reminder_worker_enabled is True
    assert settings.supabase_worker_configured is True
    assert settings.normalized_supabase_url == "http://127.0.0.1:54321"
    assert "synthetic-service-role" not in repr(settings)


def test_reminder_worker_remains_blocked_in_production() -> None:
    with pytest.raises(ValidationError, match="Production reminder worker remains blocked"):
        Settings(
            environment="production",
            auth_required=True,
            supabase_url="https://synthetic-project.supabase.co",
            supabase_publishable_key="sb_publishable_synthetic",
            supabase_service_role_key="synthetic-service-role",
            reminder_worker_enabled=True,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("reminder_worker_batch_size", 0),
        ("reminder_worker_batch_size", 101),
        ("reminder_worker_materialization_lookback_minutes", -1),
        ("reminder_worker_materialization_lookback_minutes", 1441),
        ("reminder_worker_materialization_horizon_minutes", 0),
        ("reminder_worker_materialization_horizon_minutes", 10081),
    ],
)
def test_reminder_worker_bounds_are_validated(field_name: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field_name: value})
