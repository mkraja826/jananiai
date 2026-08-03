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
def get_auth_verifier() -> SupabaseAuthVerifier | None:
    settings = get_settings()
    if not settings.supabase_configured:
        return None
    assert settings.supabase_publishable_key is not None
    return SupabaseAuthVerifier(
        supabase_url=settings.normalized_supabase_url,
        publishable_key=settings.supabase_publishable_key.get_secret_value(),
        timeout_seconds=settings.supabase_request_timeout_seconds,
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

    verifier = get_auth_verifier()
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured",
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
