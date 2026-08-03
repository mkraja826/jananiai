from typing import Protocol

from app.audit.models import ContextAssemblyAuditEvent, SafetyAuditEvent


class AuditRecorder(Protocol):
    """Storage-agnostic interface for privacy-minimised audit events."""

    def record_safety_event(self, event: SafetyAuditEvent) -> None:
        """Persist one deterministic safety-path event."""
        ...

    def record_context_event(self, event: ContextAssemblyAuditEvent) -> None:
        """Persist one context-selection event without raw health content."""
        ...
