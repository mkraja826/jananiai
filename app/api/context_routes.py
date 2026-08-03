from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes import get_audit_recorder, get_safety_engine
from app.audit import AuditRecorder, SafetyAuditEvent
from app.config import Settings, get_settings
from app.context import ContextAssembler, ContextAssemblyInput, ContextAssemblyResponse
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
    safety_engine: SafetyEngineDependency,
    audit_recorder: AuditRecorderDependency,
    assembler: ContextAssemblerDependency,
) -> ContextAssemblyResponse:
    if settings.free_first_mode and not payload.is_synthetic:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real patient data is prohibited in free-first mode",
        )

    safety_decision = safety_engine.evaluate(payload.safety_input)
    audit_recorder.record_safety_event(
        SafetyAuditEvent.from_decision(safety_decision, synthetic=payload.is_synthetic)
    )
    return assembler.assemble(payload, safety_decision)
