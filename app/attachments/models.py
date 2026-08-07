from datetime import date, datetime
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


class AttachmentCaptureSource(StrEnum):
    CAMERA = "camera"
    FILE_UPLOAD = "file_upload"
    SCAN_IMPORT = "scan_import"
    OTHER = "other"


class ExtractionStatus(StrEnum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfirmationStatus(StrEnum):
    UNCONFIRMED = "unconfirmed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class AttachmentRegistration(BaseModel):
    pregnancy_id: UUID | None = None
    kind: AttachmentKind
    mime_type: str = Field(min_length=1, max_length=150)
    storage_object_path: str = Field(min_length=1, max_length=500)
    document_date: date | None = None
    display_label: str | None = Field(default=None, min_length=1, max_length=120)
    capture_source: AttachmentCaptureSource = AttachmentCaptureSource.FILE_UPLOAD
    file_size_bytes: Annotated[int | None, Field(gt=0)] = None
    content_sha256: str | None = Field(default=None, pattern="^[0-9a-fA-F]{64}$")
    synthetic: bool = True


class AttachmentSummary(BaseModel):
    """Attachment metadata safe for timelines; extracted report text is deliberately absent."""

    attachment_id: UUID = Field(default_factory=uuid4)
    pregnancy_id: UUID | None = None
    kind: AttachmentKind
    mime_type: str = Field(min_length=1, max_length=150)
    storage_object_path: str = Field(min_length=1, max_length=500)
    extraction_status: ExtractionStatus = ExtractionStatus.NOT_STARTED
    confirmation_status: ConfirmationStatus = ConfirmationStatus.UNCONFIRMED
    document_date: date | None = None
    display_label: str | None = Field(default=None, min_length=1, max_length=120)
    capture_source: AttachmentCaptureSource = AttachmentCaptureSource.FILE_UPLOAD
    file_size_bytes: Annotated[int | None, Field(gt=0)] = None
    content_sha256: str | None = Field(default=None, pattern="^[0-9a-fA-F]{64}$")
    created_at: datetime | None = None
    synthetic: bool = True


class AttachmentRecord(AttachmentSummary):
    """Private attachment plus confirmed extraction content for controlled AI context only."""

    extracted_text: str | None = Field(default=None, max_length=20_000)
    extraction_confidence: Annotated[float | None, Field(ge=0, le=1)] = None

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
