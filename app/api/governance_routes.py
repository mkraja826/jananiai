from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.governance.dependencies import (
    GovernanceAdminRepositoryDependency,
    ReviewerAdminPrincipalDependency,
)
from app.governance.models import (
    ReviewerAdministrationResult,
    ReviewerCredentialReverificationRequest,
    ReviewerDeactivationRequest,
    ReviewerOnboardingRequest,
)
from app.governance.repository import GovernanceAdministrationError

router = APIRouter(prefix="/v1/governance/reviewers", tags=["governance"])


@router.post(
    "",
    response_model=ReviewerAdministrationResult,
    status_code=status.HTTP_201_CREATED,
)
async def onboard_reviewer(
    payload: ReviewerOnboardingRequest,
    principal: ReviewerAdminPrincipalDependency,
    repository: GovernanceAdminRepositoryDependency,
) -> ReviewerAdministrationResult:
    try:
        return await repository.onboard_reviewer(principal, payload)
    except GovernanceAdministrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/{reviewer_id}/reverify",
    response_model=ReviewerAdministrationResult,
)
async def reverify_reviewer(
    reviewer_id: UUID,
    payload: ReviewerCredentialReverificationRequest,
    principal: ReviewerAdminPrincipalDependency,
    repository: GovernanceAdminRepositoryDependency,
) -> ReviewerAdministrationResult:
    try:
        return await repository.reverify_reviewer(
            principal,
            reviewer_id,
            payload,
        )
    except GovernanceAdministrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/{reviewer_id}/deactivate",
    response_model=ReviewerAdministrationResult,
)
async def deactivate_reviewer(
    reviewer_id: UUID,
    payload: ReviewerDeactivationRequest,
    principal: ReviewerAdminPrincipalDependency,
    repository: GovernanceAdminRepositoryDependency,
) -> ReviewerAdministrationResult:
    try:
        return await repository.deactivate_reviewer(
            principal,
            reviewer_id,
            payload,
        )
    except GovernanceAdministrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
