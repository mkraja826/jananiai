from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ConsentPurpose(StrEnum):
    CARE_SUPPORT = "care_support"
    AI_PROCESSING = "ai_processing"
    ATTACHMENT_PROCESSING = "attachment_processing"
    MODEL_IMPROVEMENT = "model_improvement"
    RESEARCH = "research"


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    REVOKED = "revoked"


class ConsentEvent(BaseModel):
    """Append-only consent event; later events supersede earlier events per purpose."""

    event_id: UUID = Field(default_factory=uuid4)
    purpose: ConsentPurpose
    status: ConsentStatus
    policy_version: str = Field(min_length=1, max_length=50)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    synthetic: bool = True


class ConsentSnapshot(BaseModel):
    events: list[ConsentEvent] = Field(default_factory=list)

    def status_for(self, purpose: ConsentPurpose) -> ConsentStatus | None:
        matching = [event for event in self.events if event.purpose is purpose]
        if not matching:
            return None
        latest = max(matching, key=lambda event: event.occurred_at)
        return latest.status

    def is_granted(self, purpose: ConsentPurpose) -> bool:
        return self.status_for(purpose) is ConsentStatus.GRANTED

    def require(self, *purposes: ConsentPurpose) -> list[ConsentPurpose]:
        return [purpose for purpose in purposes if not self.is_granted(purpose)]
