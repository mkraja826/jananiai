from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pregnancy.dependencies import get_pregnancy_repository
from app.pregnancy.models import (
    PregnancyCompletionCreate,
    PregnancyCompletionEvent,
    PregnancyEncounter,
    PregnancyEncounterCreate,
    PregnancyEpisode,
    PregnancyObservation,
    PregnancyObservationCreate,
    PregnancyTimeline,
)

PREGNANCY_ID = UUID("00000000-0000-0000-0000-000000000831")


class FakePregnancyRepository:
    async def get_active_episode(self, user) -> PregnancyEpisode:
        return PregnancyEpisode(pregnancy_id=PREGNANCY_ID, gestational_week=20)

    async def get_timeline(self, user) -> PregnancyTimeline:
        return PregnancyTimeline(
            pregnancy=PregnancyEpisode(pregnancy_id=PREGNANCY_ID, gestational_week=20)
        )

    async def create_observation(self, user, payload: PregnancyObservationCreate):
        return PregnancyObservation(
            observation_id=UUID("00000000-0000-0000-0000-000000000832"),
            **payload.model_dump(),
        )

    async def create_encounter(self, user, payload: PregnancyEncounterCreate):
        return PregnancyEncounter(
            encounter_id=UUID("00000000-0000-0000-0000-000000000833"),
            **payload.model_dump(),
        )

    async def record_completion(self, user, payload: PregnancyCompletionCreate):
        return PregnancyCompletionEvent(
            completion_event_id=UUID("00000000-0000-0000-0000-000000000834"),
            created_at=datetime(2026, 8, 7, 10, tzinfo=UTC),
            **payload.model_dump(),
        )


def client() -> TestClient:
    settings = Settings(environment="test", free_first_mode=True)
    application = create_app(settings=settings)
    application.dependency_overrides[get_pregnancy_repository] = lambda: FakePregnancyRepository()
    return TestClient(application)


def test_active_episode_and_timeline_are_exposed() -> None:
    test_client = client()

    active = test_client.get("/v1/pregnancy/active")
    timeline = test_client.get("/v1/pregnancy/timeline")

    assert active.status_code == 200
    assert active.json()["pregnancy_id"] == str(PREGNANCY_ID)
    assert timeline.status_code == 200
    assert timeline.json()["items"] == []


def test_synthetic_observation_is_accepted() -> None:
    response = client().post(
        "/v1/pregnancy/observations",
        json={
            "pregnancy_id": str(PREGNANCY_ID),
            "kind": "weight",
            "weight_kg": 62.5,
            "synthetic": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["weight_kg"] == 62.5


def test_synthetic_pregnancy_completion_is_recorded() -> None:
    response = client().post(
        "/v1/pregnancy/complete",
        json={
            "pregnancy_id": str(PREGNANCY_ID),
            "occurred_at": "2026-08-07T09:00:00Z",
            "completion_type": "delivery",
            "confirmed": True,
            "note": "Synthetic delivery record",
            "synthetic": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["completion_type"] == "delivery"


def test_real_health_payload_is_blocked_in_free_first_mode() -> None:
    response = client().post(
        "/v1/pregnancy/observations",
        json={
            "pregnancy_id": str(PREGNANCY_ID),
            "kind": "weight",
            "weight_kg": 62.5,
            "synthetic": False,
        },
    )

    assert response.status_code == 403
    assert "Real patient data" in response.json()["detail"]
