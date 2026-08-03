from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.attachments import (
    AttachmentKind,
    AttachmentRecord,
    ConfirmationStatus,
    ExtractionStatus,
)
from app.context.models import ContextAssemblyInput, TaskType
from app.domain import (
    ConsentEvent,
    ConsentPurpose,
    ConsentSnapshot,
    ConsentStatus,
    UserHealthProfile,
)


def test_latest_consent_event_controls_current_status() -> None:
    now = datetime.now(UTC)
    snapshot = ConsentSnapshot(
        events=[
            ConsentEvent(
                purpose=ConsentPurpose.AI_PROCESSING,
                status=ConsentStatus.GRANTED,
                policy_version="1.0",
                occurred_at=now,
            ),
            ConsentEvent(
                purpose=ConsentPurpose.AI_PROCESSING,
                status=ConsentStatus.REVOKED,
                policy_version="1.0",
                occurred_at=now + timedelta(seconds=1),
            ),
        ]
    )

    assert snapshot.is_granted(ConsentPurpose.AI_PROCESSING) is False
    assert snapshot.require(ConsentPurpose.AI_PROCESSING) == [ConsentPurpose.AI_PROCESSING]


def test_confirmed_attachment_requires_completed_extraction() -> None:
    with pytest.raises(ValidationError, match="completed extraction"):
        AttachmentRecord(
            kind=AttachmentKind.LAB_REPORT,
            mime_type="application/pdf",
            storage_object_path="synthetic-user/report.pdf",
            extraction_status=ExtractionStatus.PROCESSING,
            confirmation_status=ConfirmationStatus.CONFIRMED,
        )


def test_completed_attachment_requires_text() -> None:
    with pytest.raises(ValidationError, match="requires extracted text"):
        AttachmentRecord(
            kind=AttachmentKind.LAB_REPORT,
            mime_type="application/pdf",
            storage_object_path="synthetic-user/report.pdf",
            extraction_status=ExtractionStatus.COMPLETED,
        )


def test_synthetic_context_rejects_real_marked_nested_record() -> None:
    with pytest.raises(ValidationError, match="marked as real data"):
        ContextAssemblyInput(
            task=TaskType.NUTRITION,
            user_question="Create synthetic nutrition context",
            consents=ConsentSnapshot(),
            profile=UserHealthProfile(synthetic=False),
        )
