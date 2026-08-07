import asyncio
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.attachments import (
    AttachmentCaptureSource,
    AttachmentIntegrityStatus,
    AttachmentKind,
    AttachmentRecord,
    ConfirmationStatus,
    ExtractionStatus,
)
from app.audit import ContextAssemblyAuditEvent, SafetyAuditEvent
from app.auth.models import AuthenticatedUser
from app.context import ContextAssemblyInput
from app.domain import (
    AppointmentRecord,
    ConsentEvent,
    ConsentPurpose,
    ConsentSnapshot,
    ConsentStatus,
    DietaryPreference,
    MedicationRecord,
    MedicationSource,
    PregnancyRecord,
    UserHealthProfile,
)
from app.persistence.client import SupabaseUserRestClient
from app.persistence.models import (
    AccountDeletionRequest,
    DeletionRequestStatus,
    StoredContextRequest,
)


class UserContextRepository(Protocol):
    async def load_context(
        self,
        user: AuthenticatedUser,
        request: StoredContextRequest,
    ) -> ContextAssemblyInput:
        """Load one user's minimal context through RLS."""
        ...

    async def record_safety_event(
        self,
        user: AuthenticatedUser,
        event: SafetyAuditEvent,
    ) -> None:
        """Persist a privacy-minimised safety event."""
        ...

    async def record_context_event(
        self,
        user: AuthenticatedUser,
        event: ContextAssemblyAuditEvent,
    ) -> None:
        """Persist a privacy-minimised context-selection event."""
        ...

    async def request_account_deletion(self) -> AccountDeletionRequest:
        """Create or return the caller's deletion workflow record."""
        ...


class SupabaseUserContextRepository:
    """Loads and writes user-owned records through PostgREST and database RPCs."""

    def __init__(self, client: SupabaseUserRestClient) -> None:
        self._client = client

    async def load_context(
        self,
        user: AuthenticatedUser,
        request: StoredContextRequest,
    ) -> ContextAssemblyInput:
        self._ensure_identity(user)

        profile_rows, pregnancy_rows, consent_rows = await asyncio.gather(
            self._client.select(
                "user_health_profiles",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "limit": "1",
                },
            ),
            self._client.select(
                "pregnancies",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "status": "eq.active",
                    "order": "updated_at.desc",
                    "limit": "1",
                },
            ),
            self._client.select(
                "consent_events",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "order": "occurred_at.asc",
                },
            ),
        )

        pregnancy_id = pregnancy_rows[0]["id"] if pregnancy_rows else None
        medication_rows, appointment_rows, attachment_rows = await asyncio.gather(
            self._load_medications(user.user_id, pregnancy_id),
            self._load_appointments(user.user_id, pregnancy_id),
            self._load_attachments(
                user.user_id,
                pregnancy_id,
                request.requested_attachment_ids,
            ),
        )
        attachments = await self._map_attachments(attachment_rows, request.is_synthetic)

        return ContextAssemblyInput(
            is_synthetic=request.is_synthetic,
            task=request.task,
            language=request.language,
            user_question=request.user_question,
            consents=self._map_consents(consent_rows, request.is_synthetic),
            profile=(
                self._map_profile(profile_rows[0], request.is_synthetic) if profile_rows else None
            ),
            pregnancy=(
                self._map_pregnancy(pregnancy_rows[0], request.is_synthetic)
                if pregnancy_rows
                else None
            ),
            medications=[
                self._map_medication(row, request.is_synthetic) for row in medication_rows
            ],
            appointments=[
                self._map_appointment(row, request.is_synthetic) for row in appointment_rows
            ],
            attachments=attachments,
            approved_knowledge=[],
            requested_attachment_ids=request.requested_attachment_ids,
            requested_medication_ids=request.requested_medication_ids,
            safety_input=request.safety_input,
            max_context_chars=request.max_context_chars,
        )

    async def append_consent_event(
        self,
        user: AuthenticatedUser,
        event: ConsentEvent,
    ) -> ConsentEvent:
        self._ensure_identity(user)
        rows = await self._client.insert(
            "consent_events",
            {
                "id": str(event.event_id),
                "user_id": str(user.user_id),
                "purpose": event.purpose.value,
                "status": event.status.value,
                "policy_version": event.policy_version,
                "occurred_at": event.occurred_at.isoformat(),
                "metadata": {"synthetic": event.synthetic},
            },
        )
        return self._map_consent(rows[0], event.synthetic)

    async def record_safety_event(
        self,
        user: AuthenticatedUser,
        event: SafetyAuditEvent,
    ) -> None:
        self._ensure_identity(user)
        await self._client.rpc(
            "record_janani_safety_event",
            {
                "p_request_id": str(event.event_id),
                "p_ruleset_version": event.ruleset_version,
                "p_triggered_rule_ids": event.triggered_rule_ids,
                "p_severity": event.severity.value,
                "p_blocks_llm": event.blocks_llm,
                "p_synthetic": event.synthetic,
            },
        )

    async def record_context_event(
        self,
        user: AuthenticatedUser,
        event: ContextAssemblyAuditEvent,
    ) -> None:
        self._ensure_identity(user)
        await self._client.rpc(
            "record_janani_context_event",
            {
                "p_event_id": str(event.event_id),
                "p_task": event.task,
                "p_status": event.status,
                "p_safety_event_id": str(event.safety_event_id),
                "p_selected_medication_ids": [str(item) for item in event.selected_medication_ids],
                "p_selected_appointment_ids": [
                    str(item) for item in event.selected_appointment_ids
                ],
                "p_selected_attachment_ids": [str(item) for item in event.selected_attachment_ids],
                "p_selected_knowledge_ids": event.selected_knowledge_ids,
                "p_excluded_item_count": event.excluded_item_count,
                "p_schema_version": event.schema_version,
                "p_synthetic": event.synthetic,
            },
        )

    async def confirm_attachment_extraction(
        self,
        *,
        attachment_id: UUID,
        extraction_id: UUID,
        confirmation: ConfirmationStatus,
    ) -> None:
        if confirmation not in {ConfirmationStatus.CONFIRMED, ConfirmationStatus.REJECTED}:
            raise ValueError("Attachment confirmation must be confirmed or rejected")
        await self._client.rpc(
            "confirm_janani_attachment_extraction",
            {
                "p_attachment_id": str(attachment_id),
                "p_extraction_id": str(extraction_id),
                "p_confirmation": confirmation.value,
            },
        )

    async def request_account_deletion(self) -> AccountDeletionRequest:
        payload = await self._client.rpc("request_janani_account_deletion", {})
        if not isinstance(payload, dict):
            raise ValueError("Deletion request RPC returned an invalid response")
        return AccountDeletionRequest(
            request_id=UUID(payload["request_id"]),
            status=DeletionRequestStatus(payload["status"]),
        )

    async def _load_medications(
        self,
        user_id: UUID,
        pregnancy_id: str | None,
    ) -> list[dict]:
        params = {
            "select": "*",
            "user_id": f"eq.{user_id}",
            "order": "recorded_at.desc",
            "limit": "100",
        }
        if pregnancy_id:
            params["pregnancy_id"] = f"eq.{pregnancy_id}"
        return await self._client.select("medication_records", params=params)

    async def _load_appointments(
        self,
        user_id: UUID,
        pregnancy_id: str | None,
    ) -> list[dict]:
        params = {
            "select": "*",
            "user_id": f"eq.{user_id}",
            "order": "scheduled_at.desc",
            "limit": "100",
        }
        if pregnancy_id:
            params["pregnancy_id"] = f"eq.{pregnancy_id}"
        return await self._client.select("appointment_records", params=params)

    async def _load_attachments(
        self,
        user_id: UUID,
        pregnancy_id: str | None,
        requested_ids: Sequence[UUID],
    ) -> list[dict]:
        params = {
            "select": "*",
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "limit": "30",
        }
        if pregnancy_id:
            params["pregnancy_id"] = f"eq.{pregnancy_id}"
        if requested_ids:
            identifiers = ",".join(str(item) for item in requested_ids)
            params["id"] = f"in.({identifiers})"
        return await self._client.select("attachment_records", params=params)

    async def _map_attachments(
        self,
        rows: list[dict],
        synthetic: bool,
    ) -> list[AttachmentRecord]:
        if not rows:
            return []
        identifiers = ",".join(str(row["id"]) for row in rows)
        extraction_rows = await self._client.select(
            "attachment_extractions",
            params={
                "select": "*",
                "attachment_id": f"in.({identifiers})",
                "order": "created_at.desc",
            },
        )
        latest: dict[str, dict] = {}
        for extraction in extraction_rows:
            latest.setdefault(str(extraction["attachment_id"]), extraction)

        attachments: list[AttachmentRecord] = []
        for row in rows:
            extraction = latest.get(str(row["id"]))
            extraction_status = ExtractionStatus(row["extraction_status"])
            confirmation_status = ConfirmationStatus(row["confirmation_status"])
            integrity_status = AttachmentIntegrityStatus(row.get("integrity_status", "unverified"))
            extracted_text = extraction.get("extracted_text") if extraction else None
            confidence = extraction.get("confidence") if extraction else None

            if extraction_status is ExtractionStatus.COMPLETED and not extracted_text:
                extraction_status = ExtractionStatus.FAILED
                confirmation_status = ConfirmationStatus.UNCONFIRMED

            attachments.append(
                AttachmentRecord(
                    attachment_id=UUID(row["id"]),
                    pregnancy_id=(UUID(row["pregnancy_id"]) if row.get("pregnancy_id") else None),
                    kind=AttachmentKind(row["kind"]),
                    mime_type=row["mime_type"],
                    storage_object_path=row["storage_object_path"],
                    extraction_status=extraction_status,
                    confirmation_status=confirmation_status,
                    integrity_status=integrity_status,
                    integrity_verified_at=row.get("integrity_verified_at"),
                    document_date=row.get("document_date"),
                    display_label=row.get("display_label"),
                    capture_source=AttachmentCaptureSource(
                        row.get("capture_source", "file_upload")
                    ),
                    file_size_bytes=row.get("file_size_bytes"),
                    content_sha256=row.get("content_sha256"),
                    extracted_text=extracted_text,
                    extraction_confidence=confidence,
                    synthetic=synthetic,
                )
            )
        return attachments

    def _map_consents(self, rows: list[dict], synthetic: bool) -> ConsentSnapshot:
        return ConsentSnapshot(events=[self._map_consent(row, synthetic) for row in rows])

    def _map_consent(self, row: dict, synthetic: bool) -> ConsentEvent:
        return ConsentEvent(
            event_id=UUID(row["id"]),
            purpose=ConsentPurpose(row["purpose"]),
            status=ConsentStatus(row["status"]),
            policy_version=row["policy_version"],
            occurred_at=row["occurred_at"],
            synthetic=synthetic,
        )

    def _map_profile(self, row: dict, synthetic: bool) -> UserHealthProfile:
        return UserHealthProfile(
            profile_id=UUID(row["user_id"]),
            height_cm=row.get("height_cm"),
            dietary_preference=DietaryPreference(row["dietary_preference"]),
            allergies=row.get("allergies") or [],
            preferred_language=row["preferred_language"],
            synthetic=synthetic,
        )

    def _map_pregnancy(self, row: dict, synthetic: bool) -> PregnancyRecord:
        return PregnancyRecord(
            pregnancy_id=UUID(row["id"]),
            gestational_week=row["gestational_week"],
            estimated_due_date=row.get("estimated_due_date"),
            known_conditions=row.get("known_conditions") or [],
            weight_kg=row.get("weight_kg"),
            clinician_restrictions=row.get("clinician_restrictions") or [],
            synthetic=synthetic,
        )

    def _map_medication(self, row: dict, synthetic: bool) -> MedicationRecord:
        return MedicationRecord(
            medication_id=UUID(row["id"]),
            name=row["name"],
            dose_text=row.get("dose_text"),
            schedule_text=row.get("schedule_text"),
            source=MedicationSource(row["source"]),
            confirmed=row["confirmed"],
            active=row["active"],
            recorded_at=row["recorded_at"],
            synthetic=synthetic,
        )

    def _map_appointment(self, row: dict, synthetic: bool) -> AppointmentRecord:
        return AppointmentRecord(
            appointment_id=UUID(row["id"]),
            scheduled_at=row["scheduled_at"],
            purpose=row.get("purpose"),
            status=row["status"],
            notes=row.get("notes"),
            synthetic=synthetic,
        )

    def _ensure_identity(self, user: AuthenticatedUser) -> None:
        if user.user_id != self._client.user.user_id:
            raise ValueError("Repository identity does not match the authenticated user")
