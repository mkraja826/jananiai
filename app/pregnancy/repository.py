import asyncio
from typing import Protocol
from uuid import UUID

from app.attachments import (
    AttachmentCaptureSource,
    AttachmentIntegrityStatus,
    AttachmentKind,
    AttachmentSummary,
    ConfirmationStatus,
    ExtractionStatus,
)
from app.auth.models import AuthenticatedUser
from app.domain import AppointmentRecord
from app.persistence.client import SupabasePersistenceError, SupabaseUserRestClient
from app.pregnancy.models import (
    EncounterType,
    ObservationKind,
    PregnancyCompletionCreate,
    PregnancyCompletionEvent,
    PregnancyCompletionType,
    PregnancyDatingSource,
    PregnancyEncounter,
    PregnancyEncounterCreate,
    PregnancyEpisode,
    PregnancyObservation,
    PregnancyObservationCreate,
    PregnancyStatus,
    PregnancyTimeline,
    RecordSource,
)
from app.pregnancy.service import build_pregnancy_timeline


class PregnancyRepository(Protocol):
    async def get_active_episode(self, user: AuthenticatedUser) -> PregnancyEpisode: ...

    async def create_observation(
        self,
        user: AuthenticatedUser,
        payload: PregnancyObservationCreate,
    ) -> PregnancyObservation: ...

    async def create_encounter(
        self,
        user: AuthenticatedUser,
        payload: PregnancyEncounterCreate,
    ) -> PregnancyEncounter: ...

    async def record_completion(
        self,
        user: AuthenticatedUser,
        payload: PregnancyCompletionCreate,
    ) -> PregnancyCompletionEvent: ...

    async def get_timeline(self, user: AuthenticatedUser) -> PregnancyTimeline: ...


class SupabasePregnancyRepository:
    """RLS-scoped structured pregnancy record access; no clinical interpretation occurs here."""

    def __init__(self, client: SupabaseUserRestClient) -> None:
        self._client = client

    async def get_active_episode(self, user: AuthenticatedUser) -> PregnancyEpisode:
        self._ensure_identity(user)
        rows = await self._client.select(
            "pregnancies",
            params={
                "select": "*",
                "user_id": f"eq.{user.user_id}",
                "status": "eq.active",
                "order": "updated_at.desc",
                "limit": "1",
            },
        )
        if not rows:
            raise SupabasePersistenceError("No active pregnancy episode was found", status_code=404)
        return self._map_episode(rows[0])

    async def create_observation(
        self,
        user: AuthenticatedUser,
        payload: PregnancyObservationCreate,
    ) -> PregnancyObservation:
        self._ensure_identity(user)
        await self._require_owned_pregnancy(user.user_id, payload.pregnancy_id)
        if payload.source_attachment_id is not None:
            await self._require_owned_attachment(
                user.user_id,
                payload.pregnancy_id,
                payload.source_attachment_id,
            )
        if payload.supersedes_observation_id is not None:
            await self._require_owned_record(
                "pregnancy_observations",
                user.user_id,
                payload.pregnancy_id,
                payload.supersedes_observation_id,
            )

        rows = await self._client.insert(
            "pregnancy_observations",
            {
                "user_id": str(user.user_id),
                "pregnancy_id": str(payload.pregnancy_id),
                "kind": payload.kind.value,
                "observed_at": payload.observed_at.isoformat(),
                "source": payload.source.value,
                "confirmed": payload.confirmed,
                "weight_kg": payload.weight_kg,
                "systolic_mm_hg": payload.systolic_mm_hg,
                "diastolic_mm_hg": payload.diastolic_mm_hg,
                "label": payload.label,
                "value_text": payload.value_text,
                "unit": payload.unit,
                "source_attachment_id": (
                    str(payload.source_attachment_id) if payload.source_attachment_id else None
                ),
                "supersedes_observation_id": (
                    str(payload.supersedes_observation_id)
                    if payload.supersedes_observation_id
                    else None
                ),
                "synthetic": payload.synthetic,
            },
        )
        return self._map_observation(rows[0])

    async def create_encounter(
        self,
        user: AuthenticatedUser,
        payload: PregnancyEncounterCreate,
    ) -> PregnancyEncounter:
        self._ensure_identity(user)
        await self._require_owned_pregnancy(user.user_id, payload.pregnancy_id)
        if payload.source_attachment_id is not None:
            await self._require_owned_attachment(
                user.user_id,
                payload.pregnancy_id,
                payload.source_attachment_id,
            )
        if payload.supersedes_encounter_id is not None:
            await self._require_owned_record(
                "pregnancy_encounters",
                user.user_id,
                payload.pregnancy_id,
                payload.supersedes_encounter_id,
            )

        rows = await self._client.insert(
            "pregnancy_encounters",
            {
                "user_id": str(user.user_id),
                "pregnancy_id": str(payload.pregnancy_id),
                "occurred_at": payload.occurred_at.isoformat(),
                "encounter_type": payload.encounter_type.value,
                "summary": payload.summary,
                "next_follow_up_at": (
                    payload.next_follow_up_at.isoformat() if payload.next_follow_up_at else None
                ),
                "source": payload.source.value,
                "confirmed": payload.confirmed,
                "source_attachment_id": (
                    str(payload.source_attachment_id) if payload.source_attachment_id else None
                ),
                "supersedes_encounter_id": (
                    str(payload.supersedes_encounter_id)
                    if payload.supersedes_encounter_id
                    else None
                ),
                "synthetic": payload.synthetic,
            },
        )
        return self._map_encounter(rows[0])

    async def record_completion(
        self,
        user: AuthenticatedUser,
        payload: PregnancyCompletionCreate,
    ) -> PregnancyCompletionEvent:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "record_janani_pregnancy_completion",
            {
                "p_pregnancy_id": str(payload.pregnancy_id),
                "p_occurred_at": payload.occurred_at.isoformat(),
                "p_completion_type": payload.completion_type.value,
                "p_source": payload.source.value,
                "p_confirmed": payload.confirmed,
                "p_note": payload.note,
                "p_supersedes_completion_event_id": (
                    str(payload.supersedes_completion_event_id)
                    if payload.supersedes_completion_event_id
                    else None
                ),
                "p_synthetic": payload.synthetic,
            },
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Pregnancy completion RPC returned an invalid response")
        return self._map_completion(data)

    async def get_timeline(self, user: AuthenticatedUser) -> PregnancyTimeline:
        pregnancy = await self._get_latest_episode(user)
        pregnancy_id = pregnancy.pregnancy_id
        observations, encounters, appointments, attachments, completions = await asyncio.gather(
            self._client.select(
                "pregnancy_observations",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "pregnancy_id": f"eq.{pregnancy_id}",
                    "order": "observed_at.desc",
                    "limit": "200",
                },
            ),
            self._client.select(
                "pregnancy_encounters",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "pregnancy_id": f"eq.{pregnancy_id}",
                    "order": "occurred_at.desc",
                    "limit": "100",
                },
            ),
            self._client.select(
                "appointment_records",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "pregnancy_id": f"eq.{pregnancy_id}",
                    "order": "scheduled_at.desc",
                    "limit": "100",
                },
            ),
            self._client.select(
                "attachment_records",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "pregnancy_id": f"eq.{pregnancy_id}",
                    "order": "created_at.desc",
                    "limit": "100",
                },
            ),
            self._client.select(
                "pregnancy_completion_events",
                params={
                    "select": "*",
                    "user_id": f"eq.{user.user_id}",
                    "pregnancy_id": f"eq.{pregnancy_id}",
                    "order": "occurred_at.desc",
                    "limit": "20",
                },
            ),
        )
        return build_pregnancy_timeline(
            pregnancy=pregnancy,
            observations=[self._map_observation(row) for row in observations],
            encounters=[self._map_encounter(row) for row in encounters],
            appointments=[self._map_appointment(row) for row in appointments],
            attachments=[
                self._map_attachment_summary(row, bool(row.get("synthetic", True)))
                for row in attachments
            ],
            completions=[self._map_completion(row) for row in completions],
        )

    async def _get_latest_episode(self, user: AuthenticatedUser) -> PregnancyEpisode:
        self._ensure_identity(user)
        rows = await self._client.select(
            "pregnancies",
            params={
                "select": "*",
                "user_id": f"eq.{user.user_id}",
                "order": "updated_at.desc",
                "limit": "1",
            },
        )
        if not rows:
            raise SupabasePersistenceError("No pregnancy episode was found", status_code=404)
        return self._map_episode(rows[0])

    async def _require_owned_pregnancy(self, user_id: UUID, pregnancy_id: UUID) -> None:
        rows = await self._client.select(
            "pregnancies",
            params={
                "select": "id",
                "id": f"eq.{pregnancy_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        if not rows:
            raise SupabasePersistenceError("Pregnancy episode was not found", status_code=404)

    async def _require_owned_attachment(
        self,
        user_id: UUID,
        pregnancy_id: UUID,
        attachment_id: UUID,
    ) -> None:
        rows = await self._client.select(
            "attachment_records",
            params={
                "select": "id",
                "id": f"eq.{attachment_id}",
                "user_id": f"eq.{user_id}",
                "pregnancy_id": f"eq.{pregnancy_id}",
                "limit": "1",
            },
        )
        if not rows:
            raise SupabasePersistenceError("Source attachment was not found", status_code=404)

    async def _require_owned_record(
        self,
        table: str,
        user_id: UUID,
        pregnancy_id: UUID,
        record_id: UUID,
    ) -> None:
        rows = await self._client.select(
            table,
            params={
                "select": "id",
                "id": f"eq.{record_id}",
                "user_id": f"eq.{user_id}",
                "pregnancy_id": f"eq.{pregnancy_id}",
                "limit": "1",
            },
        )
        if not rows:
            raise SupabasePersistenceError("Superseded record was not found", status_code=404)

    def _map_episode(self, row: dict) -> PregnancyEpisode:
        return PregnancyEpisode(
            pregnancy_id=UUID(row["id"]),
            gestational_week=row["gestational_week"],
            estimated_due_date=row.get("estimated_due_date"),
            last_menstrual_period=row.get("last_menstrual_period"),
            dating_source=PregnancyDatingSource(row.get("dating_source", "unknown")),
            dating_confirmed=bool(row.get("dating_confirmed", False)),
            known_conditions=row.get("known_conditions") or [],
            weight_kg=row.get("weight_kg"),
            clinician_restrictions=row.get("clinician_restrictions") or [],
            status=PregnancyStatus(row.get("status", "active")),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            completed_at=row.get("completed_at"),
            synthetic=bool(row.get("synthetic", True)),
        )

    def _map_observation(self, row: dict) -> PregnancyObservation:
        return PregnancyObservation(
            observation_id=UUID(row["id"]),
            pregnancy_id=UUID(row["pregnancy_id"]),
            kind=ObservationKind(row["kind"]),
            observed_at=row["observed_at"],
            source=RecordSource(row["source"]),
            confirmed=row["confirmed"],
            weight_kg=row.get("weight_kg"),
            systolic_mm_hg=row.get("systolic_mm_hg"),
            diastolic_mm_hg=row.get("diastolic_mm_hg"),
            label=row.get("label"),
            value_text=row.get("value_text"),
            unit=row.get("unit"),
            source_attachment_id=(
                UUID(row["source_attachment_id"]) if row.get("source_attachment_id") else None
            ),
            supersedes_observation_id=(
                UUID(row["supersedes_observation_id"])
                if row.get("supersedes_observation_id")
                else None
            ),
            created_at=row.get("created_at"),
            synthetic=bool(row.get("synthetic", True)),
        )

    def _map_encounter(self, row: dict) -> PregnancyEncounter:
        return PregnancyEncounter(
            encounter_id=UUID(row["id"]),
            pregnancy_id=UUID(row["pregnancy_id"]),
            occurred_at=row["occurred_at"],
            encounter_type=EncounterType(row["encounter_type"]),
            summary=row.get("summary"),
            next_follow_up_at=row.get("next_follow_up_at"),
            source=RecordSource(row["source"]),
            confirmed=row["confirmed"],
            source_attachment_id=(
                UUID(row["source_attachment_id"]) if row.get("source_attachment_id") else None
            ),
            supersedes_encounter_id=(
                UUID(row["supersedes_encounter_id"]) if row.get("supersedes_encounter_id") else None
            ),
            created_at=row.get("created_at"),
            synthetic=bool(row.get("synthetic", True)),
        )

    def _map_completion(self, row: dict) -> PregnancyCompletionEvent:
        return PregnancyCompletionEvent(
            completion_event_id=UUID(row["id"]),
            pregnancy_id=UUID(row["pregnancy_id"]),
            occurred_at=row["occurred_at"],
            completion_type=PregnancyCompletionType(row["completion_type"]),
            source=RecordSource(row["source"]),
            confirmed=bool(row.get("confirmed", False)),
            note=row.get("note"),
            supersedes_completion_event_id=(
                UUID(row["supersedes_completion_event_id"])
                if row.get("supersedes_completion_event_id")
                else None
            ),
            synthetic=bool(row.get("synthetic", True)),
            created_at=row.get("created_at"),
        )

    def _map_attachment_summary(self, row: dict, synthetic: bool) -> AttachmentSummary:
        return AttachmentSummary(
            attachment_id=UUID(row["id"]),
            pregnancy_id=UUID(row["pregnancy_id"]) if row.get("pregnancy_id") else None,
            kind=AttachmentKind(row["kind"]),
            mime_type=row["mime_type"],
            storage_object_path=row["storage_object_path"],
            extraction_status=ExtractionStatus(row.get("extraction_status", "not_started")),
            confirmation_status=ConfirmationStatus(row.get("confirmation_status", "unconfirmed")),
            integrity_status=AttachmentIntegrityStatus(row.get("integrity_status", "unverified")),
            integrity_verified_at=row.get("integrity_verified_at"),
            document_date=row.get("document_date"),
            display_label=row.get("display_label"),
            capture_source=AttachmentCaptureSource(row.get("capture_source", "file_upload")),
            file_size_bytes=row.get("file_size_bytes"),
            content_sha256=row.get("content_sha256"),
            created_at=row.get("created_at"),
            synthetic=synthetic,
        )

    def _map_appointment(self, row: dict) -> AppointmentRecord:
        return AppointmentRecord(
            appointment_id=UUID(row["id"]),
            scheduled_at=row["scheduled_at"],
            purpose=row.get("purpose"),
            status=row["status"],
            notes=row.get("notes"),
            synthetic=bool(row.get("synthetic", True)),
        )

    def _ensure_identity(self, user: AuthenticatedUser) -> None:
        if user.user_id != self._client.user.user_id:
            raise ValueError("Repository identity does not match the authenticated user")
