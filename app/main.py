from fastapi import FastAPI

from app import __version__
from app.api.context_routes import router as context_router
from app.api.routes import get_safety_engine, router
from app.config import Settings, get_settings
from app.safety.engine import SafetyEngine


def validate_runtime_readiness(settings: Settings, engine: SafetyEngine) -> None:
    """Block production startup unless a clinician-approved safety ruleset is active."""

    if settings.environment == "production" and not engine.clinical_ready:
        raise RuntimeError(
            "Production startup blocked: no current clinician-approved safety ruleset is active"
        )


def create_app(
    settings: Settings | None = None,
    safety_engine: SafetyEngine | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    runtime_engine = safety_engine or get_safety_engine()
    validate_runtime_readiness(runtime_settings, runtime_engine)

    application = FastAPI(
        title=runtime_settings.app_name,
        version=__version__,
        description=(
            "Safety-first Janani AI backend. Development builds accept synthetic data only "
            "and are not clinically ready."
        ),
    )
    application.include_router(router)
    application.include_router(context_router)

    if safety_engine is not None:

        def runtime_engine_dependency() -> SafetyEngine:
            return runtime_engine

        application.dependency_overrides[get_safety_engine] = runtime_engine_dependency

    return application


app = create_app()
