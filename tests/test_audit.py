from fastapi.testclient import TestClient

from app.api.routes import get_audit_recorder
from app.main import app

client = TestClient(app)


def test_safety_request_records_minimal_audit_event() -> None:
    recorder = get_audit_recorder()
    recorder.clear()

    response = client.post(
        "/v1/safety/evaluate",
        json={
            "is_synthetic": True,
            "heavy_bleeding": True,
            "notes": "Synthetic note that must never enter the audit event",
        },
    )

    assert response.status_code == 200
    events = recorder.snapshot()
    assert len(events) == 1

    event = events[0]
    assert event.synthetic is True
    assert event.blocks_llm is True
    assert "DEV-HEAVY-BLEEDING-001" in event.triggered_rule_ids
    assert "notes" not in event.model_dump()
    assert "heavy_bleeding" not in event.model_dump()


def test_rejected_real_data_request_is_not_recorded() -> None:
    recorder = get_audit_recorder()
    recorder.clear()

    response = client.post(
        "/v1/safety/evaluate",
        json={"is_synthetic": False, "heavy_bleeding": True},
    )

    assert response.status_code == 403
    assert recorder.snapshot() == ()
