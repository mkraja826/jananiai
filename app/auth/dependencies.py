from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr

from app.auth.models import AuthenticatedUser
from app.auth.verifier import (
    AuthenticationError,
    AuthenticationServiceUnavailable,
    SupabaseAuthVerifier,
)
from app.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_auth_verifier(
    supabase_url: str,
    publishable_key: str,
    timeout_seconds: float,
) -> SupabaseAuthVerifier:
    return SupabaseAuthVerifier(
        supabase_url=supabase_url,
        publishable_key=publishable_key,
        timeout_seconds=timeout_seconds,
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    if credentials is None:
        if settings.auth_required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthenticatedUser(
            user_id=settings.synthetic_user_id,
            access_token=SecretStr("synthetic-development-token"),
            role="synthetic",
            synthetic=True,
        )

    if not settings.supabase_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured",
        )

    assert settings.supabase_publishable_key is not None
    verifier = get_auth_verifier(
        settings.normalized_supabase_url,
        settings.supabase_publishable_key.get_secret_value(),
        settings.supabase_request_timeout_seconds,
    )

    try:
        return await verifier.verify(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthenticationServiceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]
