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


def test_context_request_records_selection_ids_without_raw_content() -> None:
    recorder = get_audit_recorder()
    recorder.clear()

    response = client.post(
        "/v1/context/assemble",
        json={
            "is_synthetic": True,
            "task": "nutrition",
            "user_question": "Sensitive synthetic question that must not enter the audit event",
            "consents": {
                "events": [
                    {
                        "purpose": "care_support",
                        "status": "granted",
                        "policy_version": "synthetic-test-v1",
                    },
                    {
                        "purpose": "ai_processing",
                        "status": "granted",
                        "policy_version": "synthetic-test-v1",
                    },
                ]
            },
            "pregnancy": {"gestational_week": 20},
            "approved_knowledge": [
                {
                    "chunk_id": "SYNTHETIC-AUDIT-KNOWLEDGE",
                    "source_title": "Synthetic source",
                    "content": "Sensitive synthetic content that must not enter the audit event",
                    "citation_label": "Synthetic citation",
                    "approved": True,
                    "review_valid": True,
                }
            ],
        },
    )

    assert response.status_code == 200
    context_events = recorder.snapshot_context()
    assert len(context_events) == 1

    event_dump = context_events[0].model_dump()
    assert event_dump["selected_knowledge_ids"] == ["SYNTHETIC-AUDIT-KNOWLEDGE"]
    assert "user_question" not in event_dump
    assert "content" not in event_dump
    assert "extracted_text" not in event_dump
    assert "prompt" not in event_dump
    assert "response" not in event_dump


def test_rejected_real_data_request_is_not_recorded() -> None:
    recorder = get_audit_recorder()
    recorder.clear()

    response = client.post(
        "/v1/safety/evaluate",
        json={"is_synthetic": False, "heavy_bleeding": True},
    )

    assert response.status_code == 403
    assert recorder.snapshot() == ()
    assert recorder.snapshot_context() == ()
