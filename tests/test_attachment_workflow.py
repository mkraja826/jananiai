import pytest

from app.attachments import (
    AttachmentKind,
    AttachmentRecord,
    AttachmentWorkflow,
    ConfirmationStatus,
    ExtractionStatus,
    InvalidAttachmentTransition,
)


def uploaded_attachment() -> AttachmentRecord:
    return AttachmentRecord(
        kind=AttachmentKind.LAB_REPORT,
        mime_type="application/pdf",
        storage_object_path="00000000-0000-0000-0000-000000000001/report.pdf",
    )


def test_attachment_requires_complete_extraction_before_confirmation() -> None:
    workflow = AttachmentWorkflow()
    uploaded = uploaded_attachment()

    with pytest.raises(InvalidAttachmentTransition):
        workflow.confirm(uploaded)

    processing = workflow.start_extraction(uploaded)
    completed = workflow.complete_extraction(
        processing,
        extracted_text="Synthetic confirmed report text",
        confidence=0.96,
    )
    confirmed = workflow.confirm(completed)

    assert processing.extraction_status is ExtractionStatus.PROCESSING
    assert completed.extraction_status is ExtractionStatus.COMPLETED
    assert completed.confirmation_status is ConfirmationStatus.UNCONFIRMED
    assert confirmed.confirmation_status is ConfirmationStatus.CONFIRMED
    assert confirmed.eligible_for_context is True


def test_failed_extraction_can_restart_but_cannot_enter_context() -> None:
    workflow = AttachmentWorkflow()
    failed = workflow.fail_extraction(workflow.start_extraction(uploaded_attachment()))

    assert failed.extraction_status is ExtractionStatus.FAILED
    assert failed.eligible_for_context is False
    assert workflow.start_extraction(failed).extraction_status is ExtractionStatus.PROCESSING


def test_rejected_extraction_is_not_context_eligible() -> None:
    workflow = AttachmentWorkflow()
    completed = workflow.complete_extraction(
        workflow.start_extraction(uploaded_attachment()),
        extracted_text="Synthetic extraction rejected by the user",
        confidence=0.55,
    )

    rejected = workflow.reject(completed)

    assert rejected.confirmation_status is ConfirmationStatus.REJECTED
    assert rejected.eligible_for_context is False
