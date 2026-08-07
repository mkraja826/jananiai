from typing import Protocol
from uuid import UUID

from app.attachments.models import (
    AttachmentCaptureSource,
    AttachmentIntegrityStatus,
    AttachmentKind,
    AttachmentSummary,
    AttachmentUploadIntent,
    AttachmentUploadIntentRequest,
    AttachmentUploadIntentStatus,
    ConfirmationStatus,
    ExtractionStatus,
)
from app.auth.models import AuthenticatedUser
from app.persistence.client import SupabasePersistenceError, SupabaseUserRestClient


class AttachmentUploadRepository(Protocol):
    async def request_upload(
        self,
        user: AuthenticatedUser,
        payload: AttachmentUploadIntentRequest,
    ) -> AttachmentUploadIntent: ...

    async def finalize_upload(
        self,
        user: AuthenticatedUser,
        intent_id: UUID,
    ) -> AttachmentSummary: ...


class SupabaseAttachmentUploadRepository:
    """One-time owner-scoped attachment upload handshake backed by Supabase RPCs."""

    def __init__(self, client: SupabaseUserRestClient) -> None:
        self._client = client

    async def request_upload(
        self,
        user: AuthenticatedUser,
        payload: AttachmentUploadIntentRequest,
    ) -> AttachmentUploadIntent:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "request_janani_attachment_upload",
            {
                "p_pregnancy_id": str(payload.pregnancy_id) if payload.pregnancy_id else None,
                "p_kind": payload.kind.value,
                "p_mime_type": payload.mime_type,
                "p_file_size_bytes": payload.file_size_bytes,
                "p_content_sha256": payload.content_sha256,
                "p_document_date": payload.document_date.isoformat() if payload.document_date else None,
                "p_display_label": payload.display_label,
                "p_capture_source": payload.capture_source.value,
                "p_synthetic": payload.synthetic,
            },
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Upload-intent RPC returned an invalid response")
        return self._map_intent(data)

    async def finalize_upload(
        self,
        user: AuthenticatedUser,
        intent_id: UUID,
    ) -> AttachmentSummary:
        self._ensure_identity(user)
        data = await self._client.rpc(
            "finalize_janani_attachment_upload",
            {"p_intent_id": str(intent_id)},
        )
        if not isinstance(data, dict):
            raise SupabasePersistenceError("Upload-finalization RPC returned an invalid response")
        return self._map_attachment(data)

    def _map_intent(self, row: dict) -> AttachmentUploadIntent:
        return AttachmentUploadIntent(
            intent_id=UUID(row["id"]),
            pregnancy_id=UUID(row["pregnancy_id"]) if row.get("pregnancy_id") else None,
            kind=AttachmentKind(row["kind"]),
            mime_type=row["mime_type"],
            file_size_bytes=row["file_size_bytes"],
            content_sha256=row["content_sha256"],
            document_date=row.get("document_date"),
            display_label=row.get("display_label"),
            capture_source=AttachmentCaptureSource(row["capture_source"]),
            synthetic=bool(row.get("synthetic", True)),
            bucket=row.get("bucket_id", "janani-private"),
            storage_object_path=row["storage_object_path"],
            status=AttachmentUploadIntentStatus(row.get("status", "pending")),
            expires_at=row["expires_at"],
            created_at=row.get("created_at"),
        )

    def _map_attachment(self, row: dict) -> AttachmentSummary:
        return AttachmentSummary(
            attachment_id=UUID(row["id"]),
            pregnancy_id=UUID(row["pregnancy_id"]) if row.get("pregnancy_id") else None,
            kind=AttachmentKind(row["kind"]),
            mime_type=row["mime_type"],
            storage_object_path=row["storage_object_path"],
            extraction_status=ExtractionStatus(row.get("extraction_status", "not_started")),
            confirmation_status=ConfirmationStatus(row.get("confirmation_status", "unconfirmed")),
            integrity_status=AttachmentIntegrityStatus(
                row.get("integrity_status", "pending_worker_hash")
            ),
            integrity_verified_at=row.get("integrity_verified_at"),
            document_date=row.get("document_date"),
            display_label=row.get("display_label"),
            capture_source=AttachmentCaptureSource(row.get("capture_source", "file_upload")),
            file_size_bytes=row.get("file_size_bytes"),
            content_sha256=row.get("content_sha256"),
            created_at=row.get("created_at"),
            synthetic=bool(row.get("synthetic", True)),
        )

    def _ensure_identity(self, user: AuthenticatedUser) -> None:
        if user.user_id != self._client.user.user_id:
            raise ValueError("Repository identity does not match the authenticated user")
