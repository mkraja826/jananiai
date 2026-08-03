from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with free-first safety guards."""

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

    @model_validator(mode="after")
    def enforce_free_first_restrictions(self) -> "Settings":
        if self.free_first_mode and self.allow_real_patient_data:
            raise ValueError("Real patient data is prohibited while free-first mode is enabled")
        if self.free_first_mode and self.llm_provider != "mock":
            raise ValueError("Only the mock LLM provider is allowed in free-first mode")
        return self

    @property
    def allow_unapproved_safety_rules(self) -> bool:
        return self.environment in {"development", "test"} and self.free_first_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
