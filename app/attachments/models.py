from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AttachmentKind(StrEnum):
    LAB_REPORT = "lab_report"
    ULTRASOUND_REPORT = "ultrasound_report"
    PRESCRIPTION = "prescription"
    DISCHARGE_SUMMARY = "discharge_summary"
    OTHER_DOCUMENT = "other_document"


class ExtractionStatus(StrEnum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfirmationStatus(StrEnum):
    UNCONFIRMED = "unconfirmed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class AttachmentRecord(BaseModel):
    """Private attachment metadata. Signed URLs and binary content are never LLM context."""

    attachment_id: UUID = Field(default_factory=uuid4)
    kind: AttachmentKind
    mime_type: str = Field(min_length=1, max_length=150)
    storage_object_path: str = Field(min_length=1, max_length=500)
    extraction_status: ExtractionStatus = ExtractionStatus.NOT_STARTED
    confirmation_status: ConfirmationStatus = ConfirmationStatus.UNCONFIRMED
    extracted_text: str | None = Field(default=None, max_length=20_000)
    extraction_confidence: Annotated[float | None, Field(ge=0, le=1)] = None
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_extraction_state(self) -> "AttachmentRecord":
        if self.extraction_status is ExtractionStatus.COMPLETED and not self.extracted_text:
            raise ValueError("Completed extraction requires extracted text")
        if self.confirmation_status is ConfirmationStatus.CONFIRMED:
            if self.extraction_status is not ExtractionStatus.COMPLETED:
                raise ValueError("Confirmed attachments require completed extraction")
            if not self.extracted_text:
                raise ValueError("Confirmed attachments require extracted text")
        return self

    @property
    def eligible_for_context(self) -> bool:
        return (
            self.extraction_status is ExtractionStatus.COMPLETED
            and self.confirmation_status is ConfirmationStatus.CONFIRMED
            and bool(self.extracted_text)
        )
