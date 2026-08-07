import asyncio
from datetime import UTC, datetime
from uuid import UUID

from pydantic import SecretStr

from app.auth.models import AuthenticatedUser
from app.pregnancy.models import (
    ObservationKind,
    PregnancyCompletionCreate,
    PregnancyCompletionType,
    PregnancyObservationCreate,
)
from app.pregnancy.repository import SupabasePregnancyRepository

USER_ID = UUID("00000000-0000-0000-0000-000000000821")
PREGNANCY_ID = UUID("00000000-0000-0000-0000-000000000822")
COMPLETION_ID = UUID("00000000-0000-0000-0000-000000000825")


class FakeRestClient:
    def __init__(self) -> None:
        self.user = AuthenticatedUser(
            user_id=USER_ID,
            access_token=SecretStr("synthetic-token"),
        )
        self.select_calls: list[tuple[str, dict]] = []
        self.insert_calls: list[tuple[str, dict]] = []
        self.rpc_calls: list[tuple[str, dict]] = []

    async def select(self, table: str, *, params=None) -> list[dict]:
        params = dict(params or {})
        self.select_calls.append((table, params))
        if table == "pregnancies":
            if params.get("select") == "id":
                return [{"id": str(PREGNANCY_ID)}]
            return [
                {
                    "id": str(PREGNANCY_ID),
                    "user_id": str(USER_ID),
                    "gestational_week": 20,
                    "estimated_due_date": "2026-12-20",
                    "dating_source": "clinician_estimated_due_date",
                    "dating_confirmed": True,
                    "known_conditions": [],
                    "clinician_restrictions": [],
                    "status": "active",
                    "synthetic": True,
                    "created_at": "2026-08-01T00:00:00+00:00",
                    "updated_at": "2026-08-07T00:00:00+00:00",
                }
            ]
        if table in {
            "pregnancy_observations",
            "pregnancy_encounters",
            "appointment_records",
            "attachment_records",
            "pregnancy_completion_events",
        }:
            return []
        raise AssertionError(f"Unexpected table {table}")

    async def insert(self, table: str, payload: dict) -> list[dict]:
        self.insert_calls.append((table, payload))
        if table == "pregnancy_observations":
            return [
                {
                    "id": "00000000-0000-0000-0000-000000000823",
                    **payload,
                    "created_at": "2026-08-07T10:00:00+00:00",
                }
            ]
        raise AssertionError(f"Unexpected insert table {table}")

    async def rpc(self, function_name: str, payload: dict):
        self.rpc_calls.append((function_name, payload))
        if function_name == "record_janani_pregnancy_completion":
            return {
                "id": str(COMPLETION_ID),
                "pregnancy_id": str(PREGNANCY_ID),
                "occurred_at": payload["p_occurred_at"],
                "completion_type": payload["p_completion_type"],
                "source": payload["p_source"],
                "confirmed": payload["p_confirmed"],
                "note": payload["p_note"],
                "supersedes_completion_event_id": payload[
                    "p_supersedes_completion_event_id"
                ],
                "synthetic": payload["p_synthetic"],
                "created_at": "2026-08-07T10:00:01+00:00",
            }
        raise AssertionError(f"Unexpected RPC {function_name}")


def authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=USER_ID,
        access_token=SecretStr("synthetic-token"),
    )


def test_repository_filters_timeline_reads_by_user_and_pregnancy() -> None:
    client = FakeRestClient()
    repository = SupabasePregnancyRepository(client)

    timeline = asyncio.run(repository.get_timeline(authenticated_user()))

    assert timeline.pregnancy.pregnancy_id == PREGNANCY_ID
    timeline_calls = [
        (table, params) for table, params in client.select_calls if table != "pregnancies"
    ]
    assert len(timeline_calls) == 5
    for _, params in timeline_calls:
        assert params["user_id"] == f"eq.{USER_ID}"
        assert params["pregnancy_id"] == f"eq.{PREGNANCY_ID}"


def test_repository_creates_typed_observation_after_owner_check() -> None:
    client = FakeRestClient()
    repository = SupabasePregnancyRepository(client)
    payload = PregnancyObservationCreate(
        pregnancy_id=PREGNANCY_ID,
        kind=ObservationKind.WEIGHT,
        observed_at=datetime(2026, 8, 7, 9, tzinfo=UTC),
        weight_kg=62.5,
    )

    observation = asyncio.run(repository.create_observation(authenticated_user(), payload))

    assert observation.weight_kg == 62.5
    assert client.insert_calls[0][0] == "pregnancy_observations"
    assert client.insert_calls[0][1]["user_id"] == str(USER_ID)


def test_repository_records_completion_through_owner_scoped_rpc() -> None:
    client = FakeRestClient()
    repository = SupabasePregnancyRepository(client)
    payload = PregnancyCompletionCreate(
        pregnancy_id=PREGNANCY_ID,
        occurred_at=datetime(2026, 8, 7, 9, tzinfo=UTC),
        completion_type=PregnancyCompletionType.DELIVERY,
        confirmed=True,
        note="Synthetic delivery record",
    )

    completion = asyncio.run(repository.record_completion(authenticated_user(), payload))

    assert completion.completion_event_id == COMPLETION_ID
    assert completion.completion_type is PregnancyCompletionType.DELIVERY
    assert client.rpc_calls[0][0] == "record_janani_pregnancy_completion"
    assert client.rpc_calls[0][1]["p_pregnancy_id"] == str(PREGNANCY_ID)
