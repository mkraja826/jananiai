from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.attachments import AttachmentRegistration, AttachmentSummary
from app.auth import CurrentUserDependency
from app.config import Settings, get_settings
from app.persistence import SupabasePersistenceError
from app.pregnancy.dependencies import PregnancyRepositoryDependency
from app.pregnancy.models import (
    PregnancyEncounter,
    PregnancyEncounterCreate,
    PregnancyEpisode,
    PregnancyObservation,
    PregnancyObservationCreate,
    PregnancyTimeline,
)

router = APIRouter(prefix="/v1/pregnancy", tags=["pregnancy"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def _enforce_data_mode(*, synthetic: bool, settings: Settings) -> None:
    if not synthetic and not settings.allow_real_patient_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real patient data is not enabled for this Janani environment",
        )


@router.get("/active", response_model=PregnancyEpisode)
async def get_active_pregnancy(
    user: CurrentUserDependency,
    repository: PregnancyRepositoryDependency,
) -> PregnancyEpisode:
    try:
        return await repository.get_active_episode(user)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/timeline", response_model=PregnancyTimeline)
async def get_pregnancy_timeline(
    user: CurrentUserDependency,
    repository: PregnancyRepositoryDependency,
) -> PregnancyTimeline:
    try:
        return await repository.get_timeline(user)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/observations",
    response_model=PregnancyObservation,
    status_code=status.HTTP_201_CREATED,
)
async def create_pregnancy_observation(
    payload: PregnancyObservationCreate,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: PregnancyRepositoryDependency,
) -> PregnancyObservation:
    _enforce_data_mode(synthetic=payload.synthetic, settings=settings)
    try:
        return await repository.create_observation(user, payload)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/encounters",
    response_model=PregnancyEncounter,
    status_code=status.HTTP_201_CREATED,
)
async def create_pregnancy_encounter(
    payload: PregnancyEncounterCreate,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: PregnancyRepositoryDependency,
) -> PregnancyEncounter:
    _enforce_data_mode(synthetic=payload.synthetic, settings=settings)
    try:
        return await repository.create_encounter(user, payload)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/attachments/register",
    response_model=AttachmentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def register_pregnancy_attachment(
    payload: AttachmentRegistration,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: PregnancyRepositoryDependency,
) -> AttachmentSummary:
    _enforce_data_mode(synthetic=payload.synthetic, settings=settings)
    try:
        return await repository.register_attachment(user, payload)
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
