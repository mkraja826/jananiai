from app.attachments.models import (
    AttachmentRecord,
    ConfirmationStatus,
    ExtractionStatus,
)


class InvalidAttachmentTransition(ValueError):
    """Raised when an attachment workflow skips a required state."""


class AttachmentWorkflow:
    """Pure state transitions for extraction and user confirmation."""

    def start_extraction(self, record: AttachmentRecord) -> AttachmentRecord:
        if record.extraction_status not in {
            ExtractionStatus.NOT_STARTED,
            ExtractionStatus.FAILED,
        }:
            raise InvalidAttachmentTransition(
                "Extraction can only start from not-started or failed"
            )
        return record.model_copy(
            update={
                "extraction_status": ExtractionStatus.PROCESSING,
                "confirmation_status": ConfirmationStatus.UNCONFIRMED,
                "extracted_text": None,
                "extraction_confidence": None,
            }
        )

    def complete_extraction(
        self,
        record: AttachmentRecord,
        *,
        extracted_text: str,
        confidence: float | None,
    ) -> AttachmentRecord:
        if record.extraction_status is not ExtractionStatus.PROCESSING:
            raise InvalidAttachmentTransition("Only processing attachments can complete extraction")
        return AttachmentRecord(
            **record.model_dump(
                exclude={
                    "extraction_status",
                    "confirmation_status",
                    "extracted_text",
                    "extraction_confidence",
                }
            ),
            extraction_status=ExtractionStatus.COMPLETED,
            confirmation_status=ConfirmationStatus.UNCONFIRMED,
            extracted_text=extracted_text,
            extraction_confidence=confidence,
        )

    def fail_extraction(self, record: AttachmentRecord) -> AttachmentRecord:
        if record.extraction_status is not ExtractionStatus.PROCESSING:
            raise InvalidAttachmentTransition("Only processing attachments can fail extraction")
        return record.model_copy(
            update={
                "extraction_status": ExtractionStatus.FAILED,
                "confirmation_status": ConfirmationStatus.UNCONFIRMED,
                "extracted_text": None,
                "extraction_confidence": None,
            }
        )

    def confirm(self, record: AttachmentRecord) -> AttachmentRecord:
        if record.extraction_status is not ExtractionStatus.COMPLETED:
            raise InvalidAttachmentTransition("Only completed extraction can be confirmed")
        return record.model_copy(update={"confirmation_status": ConfirmationStatus.CONFIRMED})

    def reject(self, record: AttachmentRecord) -> AttachmentRecord:
        if record.extraction_status is not ExtractionStatus.COMPLETED:
            raise InvalidAttachmentTransition("Only completed extraction can be rejected")
        return record.model_copy(update={"confirmation_status": ConfirmationStatus.REJECTED})
