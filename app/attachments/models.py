from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_ATTACHMENT_FILE_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_ATTACHMENT_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


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


class AttachmentIntegrityStatus(StrEnum):
    UNVERIFIED = "unverified"
    PENDING_WORKER_HASH = "pending_worker_hash"
    VERIFIED = "verified"
    MISMATCH = "mismatch"


class AttachmentUploadIntentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AttachmentRegistration(BaseModel):
    """Legacy synthetic registration contract retained only for compatibility tests."""

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


class AttachmentUploadIntentRequest(BaseModel):
    pregnancy_id: UUID | None = None
    kind: AttachmentKind
    mime_type: str = Field(min_length=1, max_length=150)
    file_size_bytes: Annotated[int, Field(gt=0, le=MAX_ATTACHMENT_FILE_SIZE_BYTES)]
    content_sha256: str = Field(pattern="^[0-9a-fA-F]{64}$")
    document_date: date | None = None
    display_label: str | None = Field(default=None, min_length=1, max_length=120)
    capture_source: AttachmentCaptureSource = AttachmentCaptureSource.FILE_UPLOAD
    synthetic: bool = True

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in ALLOWED_ATTACHMENT_MIME_TYPES:
            raise ValueError("Unsupported attachment MIME type")
        return normalized

    @field_validator("content_sha256")
    @classmethod
    def normalize_sha256(cls, value: str) -> str:
        return value.lower()


class AttachmentUploadIntent(AttachmentUploadIntentRequest):
    intent_id: UUID
    bucket: str = "janani-private"
    storage_object_path: str = Field(min_length=1, max_length=500)
    status: AttachmentUploadIntentStatus = AttachmentUploadIntentStatus.PENDING
    expires_at: datetime
    created_at: datetime | None = None


class AttachmentSummary(BaseModel):
    """Attachment metadata safe for timelines; extracted report text is deliberately absent."""

    attachment_id: UUID = Field(default_factory=uuid4)
    pregnancy_id: UUID | None = None
    kind: AttachmentKind
    mime_type: str = Field(min_length=1, max_length=150)
    storage_object_path: str = Field(min_length=1, max_length=500)
    extraction_status: ExtractionStatus = ExtractionStatus.NOT_STARTED
    confirmation_status: ConfirmationStatus = ConfirmationStatus.UNCONFIRMED
    integrity_status: AttachmentIntegrityStatus = AttachmentIntegrityStatus.UNVERIFIED
    integrity_verified_at: datetime | None = None
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
            and self.integrity_status is AttachmentIntegrityStatus.VERIFIED
            and bool(self.extracted_text)
        )
