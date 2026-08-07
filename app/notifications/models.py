import re
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

_EXPO_PUSH_TOKEN_PATTERN = re.compile(r"^(?:Expo|Exponent)PushToken\[[^\s\]]+\]$")


class NotificationPlatform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"


class NotificationTransportKind(StrEnum):
    MOCK = "mock"
    EXPO = "expo"


def is_valid_expo_push_token(token: str) -> bool:
    return bool(_EXPO_PUSH_TOKEN_PATTERN.fullmatch(token.strip()))


class NotificationDeviceRegistrationRequest(BaseModel):
    installation_id: UUID
    platform: NotificationPlatform
    transport: NotificationTransportKind = NotificationTransportKind.MOCK
    push_token: SecretStr
    synthetic: bool = True

    @field_validator("push_token")
    @classmethod
    def validate_push_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value().strip()
        if len(token) < 8 or len(token) > 4096:
            raise ValueError("push_token must contain 8 to 4096 characters")
        return SecretStr(token)

    @model_validator(mode="after")
    def validate_transport_token(self) -> "NotificationDeviceRegistrationRequest":
        if self.transport is NotificationTransportKind.EXPO:
            if self.platform is NotificationPlatform.WEB:
                raise ValueError("Expo push transport supports Android and iOS only")
            if not is_valid_expo_push_token(self.push_token.get_secret_value()):
                raise ValueError("Expo push transport requires a valid Expo push token")
        return self


class NotificationDevice(BaseModel):
    device_id: UUID
    installation_id: UUID
    platform: NotificationPlatform
    transport: NotificationTransportKind
    active: bool
    synthetic: bool = True
    registered_at: datetime | None = None
    updated_at: datetime | None = None
    revoked_at: datetime | None = None


class NotificationDeviceOverview(BaseModel):
    devices: list[NotificationDevice] = Field(default_factory=list)


class NotificationDestination(BaseModel):
    """Backend-only transport destination. Raw tokens stay secret in repr/serialization."""

    device_id: UUID
    platform: NotificationPlatform
    transport: NotificationTransportKind
    push_token: SecretStr
    synthetic: bool = True


class NotificationEnvelope(BaseModel):
    """Generic non-clinical lock-screen content plus an opaque in-app routing ID."""

    delivery_id: UUID
    title: str = "Janani reminder"
    body: str = "You have a reminder in Janani."

    def transport_data(self) -> dict[str, str]:
        return {"delivery_id": str(self.delivery_id)}


class NotificationTransportDisposition(StrEnum):
    SENT = "sent"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"


class NotificationTransportResult(BaseModel):
    device_id: UUID
    disposition: NotificationTransportDisposition
    failure_code: str | None = Field(default=None, min_length=1, max_length=100)


class ReminderNotificationDispatchResult(BaseModel):
    delivery_id: UUID
    disposition: NotificationTransportDisposition
    destination_count: int = Field(ge=0)
    sent_count: int = Field(ge=0)
    retryable_failure_count: int = Field(ge=0)
    terminal_failure_count: int = Field(ge=0)
