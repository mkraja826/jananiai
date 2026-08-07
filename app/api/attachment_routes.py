from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.attachments.dependencies import AttachmentUploadRepositoryDependency
from app.attachments.models import (
    AttachmentSummary,
    AttachmentUploadIntent,
    AttachmentUploadIntentRequest,
)
from app.auth import CurrentUserDependency
from app.config import Settings, get_settings
from app.persistence import SupabasePersistenceError

router = APIRouter(prefix="/v1/attachments", tags=["attachments"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def _enforce_data_mode(*, synthetic: bool, settings: Settings) -> None:
    if not synthetic and not settings.allow_real_patient_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real patient data is not enabled for this Janani environment",
        )


@router.post(
    "/upload-intents",
    response_model=AttachmentUploadIntent,
    status_code=status.HTTP_201_CREATED,
)
async def request_attachment_upload(
    payload: AttachmentUploadIntentRequest,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: AttachmentUploadRepositoryDependency,
) -> AttachmentUploadIntent:
    _enforce_data_mode(synthetic=payload.synthetic, settings=settings)
    try:
        return await repository.request_upload(user, payload)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/upload-intents/{intent_id}/finalize",
    response_model=AttachmentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def finalize_attachment_upload(
    intent_id: UUID,
    user: CurrentUserDependency,
    repository: AttachmentUploadRepositoryDependency,
) -> AttachmentSummary:
    try:
        return await repository.finalize_upload(user, intent_id)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
