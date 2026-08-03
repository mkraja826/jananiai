from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app import __version__
from app.config import Settings, get_settings
from app.safety.engine import SafetyEngine
from app.safety.models import ReadinessResponse, SafetyDecision, SymptomAssessmentRequest
from app.safety.rules import DEVELOPMENT_RULESET_VERSION, build_development_rules

router = APIRouter()


@lru_cache
def get_safety_engine() -> SafetyEngine:
    settings = get_settings()
    return SafetyEngine(
        rules=build_development_rules(),
        ruleset_version=DEVELOPMENT_RULESET_VERSION,
        allow_unapproved=settings.allow_unapproved_safety_rules,
    )


SettingsDependency = Annotated[Settings, Depends(get_settings)]
SafetyEngineDependency = Annotated[SafetyEngine, Depends(get_safety_engine)]


@router.get("/health")
def health(settings: SettingsDependency) -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
        "free_first_mode": settings.free_first_mode,
    }


@router.get("/ready", response_model=ReadinessResponse)
def readiness(
    settings: SettingsDependency,
    engine: SafetyEngineDependency,
) -> ReadinessResponse:
    return ReadinessResponse(
        service_ready=True,
        clinical_ready=engine.clinical_ready,
        synthetic_data_only=not settings.allow_real_patient_data,
        llm_provider=settings.llm_provider,
        reasons=engine.readiness_reasons,
    )


@router.post("/v1/safety/evaluate", response_model=SafetyDecision)
def evaluate_safety(
    payload: SymptomAssessmentRequest,
    settings: SettingsDependency,
    engine: SafetyEngineDependency,
) -> SafetyDecision:
    if settings.free_first_mode and not payload.is_synthetic:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real patient data is prohibited in free-first mode",
        )
    return engine.evaluate(payload)
