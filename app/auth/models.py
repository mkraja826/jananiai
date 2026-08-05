from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AuthenticatedUser(BaseModel):
    """Verified request identity. Secrets and authorization metadata never serialize."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    access_token: SecretStr = Field(exclude=True, repr=False)
    email: str | None = None
    role: str = "authenticated"
    app_metadata: dict[str, Any] = Field(default_factory=dict, exclude=True, repr=False)
    synthetic: bool = False

    @property
    def bearer_token(self) -> str:
        return self.access_token.get_secret_value()
