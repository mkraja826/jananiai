from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AuthenticatedUser(BaseModel):
    """Verified request identity. The bearer token is excluded from serialization and repr."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    access_token: SecretStr = Field(exclude=True, repr=False)
    email: str | None = None
    role: str = "authenticated"
    synthetic: bool = False

    @property
    def bearer_token(self) -> str:
        return self.access_token.get_secret_value()
