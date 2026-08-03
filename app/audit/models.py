from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.safety.models import SafetyDecision, SafetySeverity


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
