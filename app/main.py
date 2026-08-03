from fastapi import FastAPI

from app import __version__
from app.api.routes import router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Safety-first Janani AI backend. Development builds accept synthetic data only "
            "and are not clinically ready."
        ),
    )
    application.include_router(router)
    return application


app = create_app()
