import asyncio
from datetime import UTC, datetime
from uuid import UUID

from pydantic import SecretStr

from app.attachments import AttachmentIntegrityStatus, ConfirmationStatus
from app.audit import ContextAssemblyAuditEvent, SafetyAuditEvent
from app.auth.models import AuthenticatedUser
from app.context import ContextAssemblyStatus, TaskType
from app.persistence.models import StoredContextRequest
from app.persistence.repository import SupabaseUserContextRepository
from app.safety.models import SafetySeverity

USER_ID = UUID("00000000-0000-0000-0000-000000000444")
PREGNANCY_ID = UUID("00000000-0000-0000-0000-000000000445")
ATTACHMENT_ID = UUID("00000000-0000-0000-0000-000000000446")
EXTRACTION_ID = UUID("00000000-0000-0000-0000-000000000447")


class FakeRestClient:
    def __init__(self) -> None:
        self.user = AuthenticatedUser(
            user_id=USER_ID,
            access_token=SecretStr("synthetic-token"),
        )
        self.rpc_calls: list[tuple[str, dict]] = []

    async def select(self, table: str, *, params=None) -> list[dict]:
        rows = {
            "user_health_profiles": [
                {
                    "user_id": str(USER_ID),
                    "preferred_language": "en",
                    "dietary_preference": "vegetarian",
                    "height_cm": 165,
                    "allergies": ["synthetic allergy"],
                }
            ],
            "pregnancies": [
                {
                    "id": str(PREGNANCY_ID),
                    "gestational_week": 24,
                    "estimated_due_date": "2026-11-20",
                    "known_conditions": ["synthetic anaemia"],
                    "weight_kg": 63,
                    "clinician_restrictions": [],
                }
            ],
            "consent_events": [
                {
                    "id": "00000000-0000-0000-0000-000000000448",
                    "purpose": "care_support",
                    "status": "granted",
                    "policy_version": "synthetic-v1",
                    "occurred_at": "2026-08-04T00:00:00+00:00",
                },
                {
                    "id": "00000000-0000-0000-0000-000000000449",
                    "purpose": "ai_processing",
                    "status": "granted",
                    "policy_version": "synthetic-v1",
                    "occurred_at": "2026-08-04T00:00:01+00:00",
                },
                {
                    "id": "00000000-0000-0000-0000-000000000450",
                    "purpose": "attachment_processing",
                    "status": "granted",
                    "policy_version": "synthetic-v1",
                    "occurred_at": "2026-08-04T00:00:02+00:00",
                },
            ],
            "medication_records": [
                {
                    "id": "00000000-0000-0000-0000-000000000451",
                    "name": "Synthetic medication",
                    "dose_text": "Synthetic dose",
                    "schedule_text": "Synthetic schedule",
                    "source": "clinician_entered",
                    "confirmed": True,
                    "active": True,
                    "recorded_at": "2026-08-04T00:00:00+00:00",
                }
            ],
            "appointment_records": [],
            "attachment_records": [
                {
                    "id": str(ATTACHMENT_ID),
                    "kind": "lab_report",
                    "mime_type": "application/pdf",
                    "storage_object_path": f"{USER_ID}/synthetic-report.pdf",
                    "extraction_status": "completed",
                    "confirmation_status": "confirmed",
                    "integrity_status": "verified",
                    "integrity_verified_at": "2026-08-04T00:00:00+00:00",
                    "content_sha256": "a" * 64,
                }
            ],
            "attachment_extractions": [
                {
                    "id": str(EXTRACTION_ID),
                    "attachment_id": str(ATTACHMENT_ID),
                    "extracted_text": "Synthetic confirmed report text",
                    "confidence": 0.98,
                    "created_at": "2026-08-04T00:00:00+00:00",
                }
            ],
        }
        return rows[table]

    async def insert(self, table: str, payload: dict) -> list[dict]:
        return [payload]

    async def rpc(self, function_name: str, payload: dict):
        self.rpc_calls.append((function_name, payload))
        if function_name == "request_janani_account_deletion":
            return {
                "request_id": "00000000-0000-0000-0000-000000000499",
                "status": "pending",
            }
        return None


def authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=USER_ID,
        access_token=SecretStr("synthetic-token"),
    )


def test_repository_loads_confirmed_user_owned_context() -> None:
    repository = SupabaseUserContextRepository(FakeRestClient())
    request = StoredContextRequest(
        task=TaskType.REPORT_EXPLANATION,
        user_question="Explain the selected synthetic report",
        requested_attachment_ids=[ATTACHMENT_ID],
    )

    context = asyncio.run(repository.load_context(authenticated_user(), request))

    assert context.pregnancy is not None
    assert context.pregnancy.pregnancy_id == PREGNANCY_ID
    assert context.profile is not None
    assert context.profile.dietary_preference.value == "vegetarian"
    assert len(context.medications) == 1
    assert len(context.attachments) == 1
    assert context.attachments[0].confirmation_status is ConfirmationStatus.CONFIRMED
    assert context.attachments[0].integrity_status is AttachmentIntegrityStatus.VERIFIED
    assert context.attachments[0].eligible_for_context is True


def test_repository_audit_rpcs_exclude_raw_health_content() -> None:
    client = FakeRestClient()
    repository = SupabaseUserContextRepository(client)
    user = authenticated_user()
    safety_event = SafetyAuditEvent(
        event_id=UUID("00000000-0000-0000-0000-000000000460"),
        ruleset_version="synthetic-rules",
        triggered_rule_ids=[],
        severity=SafetySeverity.ROUTINE,
        blocks_llm=False,
        synthetic=True,
    )
    context_event = ContextAssemblyAuditEvent(
        safety_event_id=safety_event.event_id,
        task=TaskType.REPORT_EXPLANATION.value,
        status=ContextAssemblyStatus.READY.value,
        selected_attachment_ids=[ATTACHMENT_ID],
        excluded_item_count=0,
        synthetic=True,
        created_at=datetime.now(UTC),
    )

    asyncio.run(repository.record_safety_event(user, safety_event))
    asyncio.run(repository.record_context_event(user, context_event))

    combined = repr(client.rpc_calls)
    assert "Synthetic confirmed report text" not in combined
    assert "Explain the selected synthetic report" not in combined
    assert "p_selected_attachment_ids" in combined


def test_repository_requests_idempotent_account_deletion_workflow() -> None:
    repository = SupabaseUserContextRepository(FakeRestClient())

    deletion = asyncio.run(repository.request_account_deletion())

    assert deletion.status.value == "pending"
    assert deletion.request_id == UUID("00000000-0000-0000-0000-000000000499")
