from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def granted_consent(purpose: str) -> dict[str, str | bool]:
    return {
        "purpose": purpose,
        "status": "granted",
        "policy_version": "synthetic-test-v1",
        "synthetic": True,
    }


def test_context_api_builds_typed_request_without_calling_llm() -> None:
    response = client.post(
        "/v1/context/assemble",
        json={
            "is_synthetic": True,
            "task": "nutrition",
            "language": "en",
            "user_question": "What synthetic nutrition guidance applies?",
            "consents": {
                "events": [
                    granted_consent("care_support"),
                    granted_consent("ai_processing"),
                ]
            },
            "pregnancy": {
                "gestational_week": 20,
                "known_conditions": ["synthetic anaemia"],
                "synthetic": True,
            },
            "approved_knowledge": [
                {
                    "chunk_id": "SYNTHETIC-KNOWLEDGE-API",
                    "source_title": "Synthetic approved source",
                    "content": "Synthetic approved content",
                    "citation_label": "Synthetic section",
                    "approved": True,
                    "review_valid": True,
                }
            ],
            "safety_input": {"is_synthetic": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["llm_request"]["schema_version"] == "1.0"
    assert body["llm_request"]["task"] == "nutrition"
    assert body["llm_request"]["synthetic_data_only"] is True
    assert body["llm_request"]["selected_context"]["pregnancy"]["gestational_week"] == 20
    assert "provider" not in body["llm_request"]


def test_context_api_returns_safety_block_without_llm_request() -> None:
    response = client.post(
        "/v1/context/assemble",
        json={
            "is_synthetic": True,
            "task": "general_question",
            "user_question": "Synthetic warning-sign question",
            "consents": {"events": []},
            "pregnancy": {"gestational_week": 20, "synthetic": True},
            "safety_input": {"is_synthetic": True, "heavy_bleeding": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked_by_safety"
    assert body["llm_request"] is None
    assert body["safety_decision"]["blocks_llm"] is True


def test_context_api_rejects_real_data_in_free_first_mode() -> None:
    response = client.post(
        "/v1/context/assemble",
        json={
            "is_synthetic": False,
            "task": "nutrition",
            "user_question": "Real-data request must be rejected",
            "consents": {"events": []},
            "safety_input": {"is_synthetic": False},
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Real patient data is prohibited in free-first mode"
