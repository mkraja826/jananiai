from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import CurrentUserDependency
from app.config import Settings, get_settings
from app.persistence import SupabasePersistenceError
from app.reminders.dependencies import ReminderRepositoryDependency
from app.reminders.models import (
    AppointmentReminderSchedule,
    AppointmentReminderScheduleCreate,
    MedicationReminderSchedule,
    MedicationReminderScheduleCreate,
    ReminderDeliveryOverview,
    ReminderOverview,
    ReminderResponse,
    ReminderResponseCreate,
)

router = APIRouter(prefix="/v1/reminders", tags=["reminders"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def _enforce_data_mode(*, synthetic: bool, settings: Settings) -> None:
    if not synthetic and not settings.allow_real_patient_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real patient data is not enabled for this Janani environment",
        )


@router.get("", response_model=ReminderOverview)
async def list_reminders(
    user: CurrentUserDependency,
    repository: ReminderRepositoryDependency,
) -> ReminderOverview:
    try:
        return await repository.list_reminders(user)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/deliveries", response_model=ReminderDeliveryOverview)
async def list_reminder_deliveries(
    user: CurrentUserDependency,
    repository: ReminderRepositoryDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ReminderDeliveryOverview:
    try:
        return await repository.list_deliveries(user, limit=limit)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/deliveries/{delivery_id}/responses",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_reminder_response(
    delivery_id: UUID,
    payload: ReminderResponseCreate,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: ReminderRepositoryDependency,
) -> ReminderResponse:
    _enforce_data_mode(synthetic=payload.synthetic, settings=settings)
    try:
        return await repository.record_response(user, delivery_id, payload)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/medications",
    response_model=MedicationReminderSchedule,
    status_code=status.HTTP_201_CREATED,
)
async def create_medication_reminder(
    payload: MedicationReminderScheduleCreate,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: ReminderRepositoryDependency,
) -> MedicationReminderSchedule:
    _enforce_data_mode(synthetic=payload.synthetic, settings=settings)
    try:
        return await repository.create_medication_reminder(user, payload)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/appointments",
    response_model=AppointmentReminderSchedule,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment_reminder(
    payload: AppointmentReminderScheduleCreate,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: ReminderRepositoryDependency,
) -> AppointmentReminderSchedule:
    _enforce_data_mode(synthetic=payload.synthetic, settings=settings)
    try:
        return await repository.create_appointment_reminder(user, payload)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/medications/{reminder_id}/disable", response_model=MedicationReminderSchedule)
async def disable_medication_reminder(
    reminder_id: UUID,
    user: CurrentUserDependency,
    repository: ReminderRepositoryDependency,
) -> MedicationReminderSchedule:
    try:
        return await repository.disable_medication_reminder(user, reminder_id)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/appointments/{reminder_id}/disable", response_model=AppointmentReminderSchedule)
async def disable_appointment_reminder(
    reminder_id: UUID,
    user: CurrentUserDependency,
    repository: ReminderRepositoryDependency,
) -> AppointmentReminderSchedule:
    try:
        return await repository.disable_appointment_reminder(user, reminder_id)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
