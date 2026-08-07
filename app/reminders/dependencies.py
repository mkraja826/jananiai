from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth import CurrentUserDependency
from app.config import Settings, get_settings
from app.persistence.client import SupabaseUserRestClient
from app.reminders.repository import ReminderRepository, SupabaseReminderRepository


async def get_reminder_repository(
    user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[ReminderRepository]:
    if user.synthetic:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stored reminder services require configured Supabase authentication",
        )
    if not settings.supabase_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase persistence is not configured",
        )

    assert settings.supabase_publishable_key is not None
    client = SupabaseUserRestClient(
        supabase_url=settings.normalized_supabase_url,
        publishable_key=settings.supabase_publishable_key.get_secret_value(),
        user=user,
        timeout_seconds=settings.supabase_request_timeout_seconds,
    )
    try:
        yield SupabaseReminderRepository(client)
    finally:
        await client.aclose()


ReminderRepositoryDependency = Annotated[
    ReminderRepository,
    Depends(get_reminder_repository),
]
