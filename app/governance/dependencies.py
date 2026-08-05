from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth import CurrentUserDependency
from app.config import Settings, get_settings
from app.governance.authorization import (
    GovernanceAuthorizationError,
    require_governance_roles,
)
from app.governance.models import GovernanceAdminRole, GovernancePrincipal
from app.governance.repository import (
    GovernanceAdminRepository,
    SupabaseGovernanceAdminRepository,
)


@lru_cache
def get_supabase_governance_repository(
    supabase_url: str,
    service_role_key: str,
    timeout_seconds: float,
) -> SupabaseGovernanceAdminRepository:
    return SupabaseGovernanceAdminRepository(
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        timeout_seconds=timeout_seconds,
    )


def get_governance_admin_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GovernanceAdminRepository:
    if not settings.governance_admin_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Governance administration API is disabled",
        )
    if not settings.supabase_service_role_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Governance administration persistence is not configured",
        )

    assert settings.supabase_service_role_key is not None
    return get_supabase_governance_repository(
        settings.normalized_supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
        settings.supabase_request_timeout_seconds,
    )


def get_reviewer_admin_principal(
    user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> GovernancePrincipal:
    if not settings.governance_admin_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Governance administration API is disabled",
        )
    try:
        return require_governance_roles(
            user,
            {GovernanceAdminRole.REVIEWER_ADMIN},
        )
    except GovernanceAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


GovernanceAdminRepositoryDependency = Annotated[
    GovernanceAdminRepository,
    Depends(get_governance_admin_repository),
]
ReviewerAdminPrincipalDependency = Annotated[
    GovernancePrincipal,
    Depends(get_reviewer_admin_principal),
]
