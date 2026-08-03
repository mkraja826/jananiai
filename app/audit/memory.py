from threading import Lock

from app.audit.models import ContextAssemblyAuditEvent, SafetyAuditEvent


class InMemoryAuditRecorder:
    """Development-only recorder. Production will use a durable backend implementation."""

    def __init__(self) -> None:
        self._safety_events: list[SafetyAuditEvent] = []
        self._context_events: list[ContextAssemblyAuditEvent] = []
        self._lock = Lock()

    def record_safety_event(self, event: SafetyAuditEvent) -> None:
        with self._lock:
            self._safety_events.append(event.model_copy(deep=True))

    def record_context_event(self, event: ContextAssemblyAuditEvent) -> None:
        with self._lock:
            self._context_events.append(event.model_copy(deep=True))

    def snapshot(self) -> tuple[SafetyAuditEvent, ...]:
        with self._lock:
            return tuple(event.model_copy(deep=True) for event in self._safety_events)

    def snapshot_context(self) -> tuple[ContextAssemblyAuditEvent, ...]:
        with self._lock:
            return tuple(event.model_copy(deep=True) for event in self._context_events)

    def clear(self) -> None:
        with self._lock:
            self._safety_events.clear()
            self._context_events.clear()
