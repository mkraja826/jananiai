from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.context.models import TaskType
from app.safety.models import SymptomAssessmentRequest


class StoredContextRequest(BaseModel):
    """Small client request; health context is loaded server-side through RLS."""

    is_synthetic: bool = True
    task: TaskType
    language: Literal["en", "te"] = "en"
    user_question: str = Field(min_length=1, max_length=2_000)
    requested_attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)
    requested_medication_ids: list[UUID] = Field(default_factory=list, max_length=20)
    safety_input: SymptomAssessmentRequest = Field(default_factory=SymptomAssessmentRequest)
    max_context_chars: int = Field(default=16_000, ge=2_000, le=80_000)


class DeletionRequestStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AccountDeletionRequest(BaseModel):
    request_id: UUID
    status: DeletionRequestStatus
