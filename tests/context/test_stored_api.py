from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.routes import get_audit_recorder
from app.auth import AuthenticatedUser, get_current_user
from app.config import Settings
from app.context import ContextAssemblyInput, TaskType
from app.domain import (
    ConsentEvent,
    ConsentPurpose,
    ConsentSnapshot,
    ConsentStatus,
    PregnancyRecord,
)
from app.main import app, create_app
from app.persistence.dependencies import get_user_context_repository
from app.persistence.models import StoredContextRequest
from app.safety.engine import SafetyEngine
from app.safety.rules import build_development_rules

USER_ID = UUID("00000000-0000-0000-0000-000000000555")


class FakeStoredRepository:
    def __init__(self) -> None:
        self.safety_events = 0
        self.context_events = 0

    async def load_context(
        self,
        user: AuthenticatedUser,
        request: StoredContextRequest,
    ) -> ContextAssemblyInput:
        assert user.user_id == USER_ID
        return ContextAssemblyInput(
            is_synthetic=True,
            task=request.task,
            language=request.language,
            user_question=request.user_question,
            consents=ConsentSnapshot(
                events=[
                    ConsentEvent(
                        purpose=ConsentPurpose.CARE_SUPPORT,
                        status=ConsentStatus.GRANTED,
                        policy_version="synthetic-v1",
                    ),
                    ConsentEvent(
                        purpose=ConsentPurpose.AI_PROCESSING,
                        status=ConsentStatus.GRANTED,
                        policy_version="synthetic-v1",
                    ),
                ]
            ),
            pregnancy=PregnancyRecord(gestational_week=24),
            safety_input=request.safety_input,
            max_context_chars=request.max_context_chars,
        )

    async def record_safety_event(self, user, event) -> None:
        assert user.user_id == USER_ID
        self.safety_events += 1

    async def record_context_event(self, user, event) -> None:
        assert user.user_id == USER_ID
        self.context_events += 1


def verified_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=USER_ID,
        access_token=SecretStr("synthetic-verified-token"),
        synthetic=False,
    )


def test_stored_context_endpoint_loads_records_server_side() -> None:
    repository = FakeStoredRepository()
    recorder = get_audit_recorder()
    recorder.clear()

    async def override_user() -> AuthenticatedUser:
        return verified_user()

    def override_repository() -> FakeStoredRepository:
        return repository

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_user_context_repository] = override_repository
    try:
        response = TestClient(app).post(
            "/v1/context/assemble-stored",
            json={
                "task": "nutrition",
                "user_question": "What synthetic food guidance applies?",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_user_context_repository, None)

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert repository.safety_events == 1
    assert repository.context_events == 1


def test_staging_context_endpoint_requires_bearer_authentication() -> None:
    settings = Settings(
        environment="staging",
        auth_required=True,
        supabase_url="https://synthetic-project.supabase.co",
        supabase_publishable_key="sb_publishable_synthetic",
    )
    engine = SafetyEngine(build_development_rules(), "staging-test", allow_unapproved=False)
    application = create_app(settings=settings, safety_engine=engine)

    response = TestClient(application).post(
        "/v1/context/assemble",
        json={
            "task": TaskType.NUTRITION.value,
            "user_question": "Synthetic protected question",
            "consents": {"events": []},
            "pregnancy": {"gestational_week": 24},
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer authentication is required"
