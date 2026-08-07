"""Attachment metadata, upload integrity, extraction, and confirmation-state services."""

from app.attachments.models import (
    ALLOWED_ATTACHMENT_MIME_TYPES,
    MAX_ATTACHMENT_FILE_SIZE_BYTES,
    AttachmentCaptureSource,
    AttachmentIntegrityStatus,
    AttachmentKind,
    AttachmentRecord,
    AttachmentRegistration,
    AttachmentSummary,
    AttachmentUploadIntent,
    AttachmentUploadIntentRequest,
    AttachmentUploadIntentStatus,
    ConfirmationStatus,
    ExtractionStatus,
)
from app.attachments.service import AttachmentWorkflow, InvalidAttachmentTransition

__all__ = [
    "ALLOWED_ATTACHMENT_MIME_TYPES",
    "MAX_ATTACHMENT_FILE_SIZE_BYTES",
    "AttachmentCaptureSource",
    "AttachmentIntegrityStatus",
    "AttachmentKind",
    "AttachmentRecord",
    "AttachmentRegistration",
    "AttachmentSummary",
    "AttachmentUploadIntent",
    "AttachmentUploadIntentRequest",
    "AttachmentUploadIntentStatus",
    "AttachmentWorkflow",
    "ConfirmationStatus",
    "ExtractionStatus",
    "InvalidAttachmentTransition",
]
