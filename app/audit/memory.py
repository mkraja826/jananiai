from threading import Lock

from app.audit.models import SafetyAuditEvent


class InMemoryAuditRecorder:
    """Development-only recorder. Production will use a durable backend implementation."""

    def __init__(self) -> None:
        self._events: list[SafetyAuditEvent] = []
        self._lock = Lock()

    def record_safety_event(self, event: SafetyAuditEvent) -> None:
        with self._lock:
            self._events.append(event.model_copy(deep=True))

    def snapshot(self) -> tuple[SafetyAuditEvent, ...]:
        with self._lock:
            return tuple(event.model_copy(deep=True) for event in self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
