import asyncio
from datetime import UTC, datetime
from uuid import UUID

from pydantic import SecretStr

from app.attachments import AttachmentKind, AttachmentRegistration
from app.auth.models import AuthenticatedUser
from app.pregnancy.models import ObservationKind, PregnancyObservationCreate
from app.pregnancy.repository import SupabasePregnancyRepository

USER_ID = UUID("00000000-0000-0000-0000-000000000821")
PREGNANCY_ID = UUID("00000000-0000-0000-0000-000000000822")


class FakeRestClient:
    def __init__(self) -> None:
        self.user = AuthenticatedUser(
            user_id=USER_ID,
            access_token=SecretStr("synthetic-token"),
        )
        self.select_calls: list[tuple[str, dict]] = []
        self.insert_calls: list[tuple[str, dict]] = []

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
        if table == "attachment_records":
            return [
                {
                    "id": "00000000-0000-0000-0000-000000000824",
                    **payload,
                    "extraction_status": "not_started",
                    "confirmation_status": "unconfirmed",
                    "created_at": "2026-08-07T10:00:00+00:00",
                }
            ]
        raise AssertionError(f"Unexpected insert table {table}")


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
    assert len(timeline_calls) == 4
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


def test_attachment_registration_requires_owner_storage_prefix() -> None:
    repository = SupabasePregnancyRepository(FakeRestClient())
    payload = AttachmentRegistration(
        pregnancy_id=PREGNANCY_ID,
        kind=AttachmentKind.LAB_REPORT,
        mime_type="application/pdf",
        storage_object_path=f"{USER_ID}/synthetic-report.pdf",
        content_sha256="B" * 64,
    )

    attachment = asyncio.run(repository.register_attachment(authenticated_user(), payload))

    assert attachment.content_sha256 == "b" * 64
    assert attachment.storage_object_path.startswith(f"{USER_ID}/")
