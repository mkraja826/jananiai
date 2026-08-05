from functools import lru_cache
from typing import Literal
from uuid import UUID

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with free-first safety and authentication guards."""

    model_config = SettingsConfigDict(
        env_prefix="JANANI_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Janani AI"
    environment: Literal["development", "test", "staging", "production"] = "development"
    free_first_mode: bool = True
    allow_real_patient_data: bool = False
    llm_provider: str = "mock"
    log_level: str = "INFO"

    auth_required: bool = False
    supabase_url: str | None = None
    supabase_publishable_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_request_timeout_seconds: float = 8.0
    synthetic_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")

    governance_admin_api_enabled: bool = False

    @model_validator(mode="after")
    def enforce_runtime_restrictions(self) -> "Settings":
        if self.free_first_mode and self.allow_real_patient_data:
            raise ValueError("Real patient data is prohibited while free-first mode is enabled")
        if self.free_first_mode and self.llm_provider != "mock":
            raise ValueError("Only the mock LLM provider is allowed in free-first mode")
        if self.supabase_request_timeout_seconds <= 0:
            raise ValueError("Supabase request timeout must be positive")

        protected_environment = self.environment in {"staging", "production"}
        if protected_environment and not self.auth_required:
            raise ValueError("Authentication must be required in staging and production")
        if protected_environment and not self.supabase_configured:
            raise ValueError(
                "Supabase URL and publishable key are required in staging and production"
            )

        if self.governance_admin_api_enabled:
            if not self.auth_required:
                raise ValueError("Governance administration requires authentication")
            if not self.supabase_configured:
                raise ValueError("Governance administration requires Supabase configuration")
            if not self.supabase_service_role_configured:
                raise ValueError(
                    "Governance administration requires a backend-only Supabase service-role key"
                )
        return self

    @property
    def allow_unapproved_safety_rules(self) -> bool:
        return self.environment in {"development", "test"} and self.free_first_mode

    @property
    def supabase_configured(self) -> bool:
        return bool(
            self.supabase_url
            and self.supabase_url.strip()
            and self.supabase_publishable_key
            and self.supabase_publishable_key.get_secret_value().strip()
        )

    @property
    def supabase_service_role_configured(self) -> bool:
        return bool(
            self.supabase_service_role_key
            and self.supabase_service_role_key.get_secret_value().strip()
        )

    @property
    def normalized_supabase_url(self) -> str:
        if not self.supabase_url:
            raise ValueError("Supabase URL is not configured")
        return self.supabase_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
