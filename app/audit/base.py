from typing import Protocol

from app.audit.models import SafetyAuditEvent


class AuditRecorder(Protocol):
    """Storage-agnostic interface for privacy-minimised audit events."""

    def record_safety_event(self, event: SafetyAuditEvent) -> None:
        """Persist one deterministic safety-path event."""
        ...
