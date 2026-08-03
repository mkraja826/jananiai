from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes import get_audit_recorder, get_safety_engine
from app.audit import AuditRecorder, ContextAssemblyAuditEvent, SafetyAuditEvent
from app.auth import CurrentUserDependency
from app.config import Settings, get_settings
from app.context import ContextAssembler, ContextAssemblyInput, ContextAssemblyResponse
from app.persistence import StoredContextRequest, SupabasePersistenceError
from app.persistence.dependencies import UserContextRepositoryDependency
from app.safety.engine import SafetyEngine

router = APIRouter(prefix="/v1/context", tags=["context"])


@lru_cache
def get_context_assembler() -> ContextAssembler:
    return ContextAssembler()


SettingsDependency = Annotated[Settings, Depends(get_settings)]
SafetyEngineDependency = Annotated[SafetyEngine, Depends(get_safety_engine)]
AuditRecorderDependency = Annotated[AuditRecorder, Depends(get_audit_recorder)]
ContextAssemblerDependency = Annotated[ContextAssembler, Depends(get_context_assembler)]


@router.post("/assemble", response_model=ContextAssemblyResponse)
def assemble_context(
    payload: ContextAssemblyInput,
    settings: SettingsDependency,
    _user: CurrentUserDependency,
    safety_engine: SafetyEngineDependency,
    audit_recorder: AuditRecorderDependency,
    assembler: ContextAssemblerDependency,
) -> ContextAssemblyResponse:
    """Synthetic direct-input endpoint retained for deterministic development tests."""

    if settings.free_first_mode and not payload.is_synthetic:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real patient data is prohibited in free-first mode",
        )

    safety_decision = safety_engine.evaluate(payload.safety_input)
    safety_event = SafetyAuditEvent.from_decision(
        safety_decision,
        synthetic=payload.is_synthetic,
    )
    audit_recorder.record_safety_event(safety_event)
    response = assembler.assemble(payload, safety_decision)
    audit_recorder.record_context_event(
        ContextAssemblyAuditEvent.from_response(
            response,
            task=payload.task,
            synthetic=payload.is_synthetic,
        )
    )
    return response


@router.post("/assemble-stored", response_model=ContextAssemblyResponse)
async def assemble_stored_context(
    payload: StoredContextRequest,
    settings: SettingsDependency,
    user: CurrentUserDependency,
    repository: UserContextRepositoryDependency,
    safety_engine: SafetyEngineDependency,
    audit_recorder: AuditRecorderDependency,
    assembler: ContextAssemblerDependency,
) -> ContextAssemblyResponse:
    """Load authenticated user records through RLS and assemble minimal model context."""

    if settings.free_first_mode and not payload.is_synthetic:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real patient data is prohibited in free-first mode",
        )

    try:
        context_input = await repository.load_context(user, payload)
        safety_decision = safety_engine.evaluate(context_input.safety_input)
        safety_event = SafetyAuditEvent.from_decision(
            safety_decision,
            synthetic=context_input.is_synthetic,
        )
        await repository.record_safety_event(user, safety_event)
        audit_recorder.record_safety_event(safety_event)

        response = assembler.assemble(context_input, safety_decision)
        context_event = ContextAssemblyAuditEvent.from_response(
            response,
            task=context_input.task,
            synthetic=context_input.is_synthetic,
        )
        await repository.record_context_event(user, context_event)
        audit_recorder.record_context_event(context_event)
        return response
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
