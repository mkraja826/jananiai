"""Attachment metadata and confirmation-state models."""

from app.attachments.models import (
    AttachmentKind,
    AttachmentRecord,
    ConfirmationStatus,
    ExtractionStatus,
)

__all__ = [
    "AttachmentKind",
    "AttachmentRecord",
    "ConfirmationStatus",
    "ExtractionStatus",
]
