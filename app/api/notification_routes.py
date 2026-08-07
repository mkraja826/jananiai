from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import CurrentUserDependency
from app.config import Settings, get_settings
from app.notifications.dependencies import NotificationDeviceRepositoryDependency
from app.notifications.models import (
    NotificationDevice,
    NotificationDeviceOverview,
    NotificationDeviceRegistrationRequest,
)
from app.persistence import SupabasePersistenceError

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def _enforce_data_mode(*, synthetic: bool, settings: Settings) -> None:
    if not synthetic and not settings.allow_real_patient_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real patient data is not enabled for this Janani environment",
        )


@router.get("/devices", response_model=NotificationDeviceOverview)
async def list_notification_devices(
    user: CurrentUserDependency,
    repository: NotificationDeviceRepositoryDependency,
) -> NotificationDeviceOverview:
    try:
        return await repository.list_devices(user)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/devices",
    response_model=NotificationDevice,
    status_code=status.HTTP_201_CREATED,
)
async def register_notification_device(
    payload: NotificationDeviceRegistrationRequest,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: NotificationDeviceRepositoryDependency,
) -> NotificationDevice:
    _enforce_data_mode(synthetic=payload.synthetic, settings=settings)
    try:
        return await repository.register_device(user, payload)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/devices/{device_id}/revoke", response_model=NotificationDevice)
async def revoke_notification_device(
    device_id: UUID,
    user: CurrentUserDependency,
    repository: NotificationDeviceRepositoryDependency,
) -> NotificationDevice:
    try:
        return await repository.revoke_device(user, device_id)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
