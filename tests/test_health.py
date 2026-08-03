from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_free_first_mode() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["free_first_mode"] is True


def test_readiness_is_not_clinical() -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["service_ready"] is True
    assert body["clinical_ready"] is False
    assert body["synthetic_data_only"] is True
    assert body["llm_provider"] == "mock"


def test_real_patient_payload_is_rejected() -> None:
    response = client.post(
        "/v1/safety/evaluate",
        json={"is_synthetic": False, "heavy_bleeding": True},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Real patient data is prohibited in free-first mode"
