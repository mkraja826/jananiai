from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.safety.models import SafetyDecision, SafetySeverity

if TYPE_CHECKING:
    from app.context.models import ContextAssemblyResponse, TaskType


class SafetyAuditEvent(BaseModel):
    """Minimal event that excludes raw symptoms, notes, prompts, and personal identifiers."""

    event_id: UUID
    ruleset_version: str
    triggered_rule_ids: list[str]
    severity: SafetySeverity
    blocks_llm: bool
    synthetic: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_decision(
        cls,
        decision: SafetyDecision,
        *,
        synthetic: bool,
    ) -> "SafetyAuditEvent":
        return cls(
            event_id=decision.event_id,
            ruleset_version=decision.ruleset_version,
            triggered_rule_ids=decision.triggered_rule_ids,
            severity=decision.severity,
            blocks_llm=decision.blocks_llm,
            synthetic=synthetic,
        )


class ContextAssemblyAuditEvent(BaseModel):
    """Selection audit that deliberately excludes raw content and user questions."""

    event_id: UUID = Field(default_factory=uuid4)
    safety_event_id: UUID
    task: str
    status: str
    selected_medication_ids: list[UUID] = Field(default_factory=list)
    selected_appointment_ids: list[UUID] = Field(default_factory=list)
    selected_attachment_ids: list[UUID] = Field(default_factory=list)
    selected_knowledge_ids: list[str] = Field(default_factory=list)
    excluded_item_count: int = Field(ge=0)
    schema_version: str = "1.0"
    synthetic: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_response(
        cls,
        response: "ContextAssemblyResponse",
        *,
        task: "TaskType",
        synthetic: bool,
    ) -> "ContextAssemblyAuditEvent":
        selected = response.llm_request.selected_context if response.llm_request else None
        return cls(
            safety_event_id=response.safety_decision.event_id,
            task=task.value,
            status=response.status.value,
            selected_medication_ids=(
                [item.medication_id for item in selected.medications] if selected else []
            ),
            selected_appointment_ids=(
                [item.appointment_id for item in selected.appointments] if selected else []
            ),
            selected_attachment_ids=(
                [item.attachment_id for item in selected.attachments] if selected else []
            ),
            selected_knowledge_ids=(
                [item.chunk_id for item in selected.approved_knowledge] if selected else []
            ),
            excluded_item_count=len(response.exclusions),
            schema_version=response.llm_request.schema_version if response.llm_request else "1.0",
            synthetic=synthetic,
        )
