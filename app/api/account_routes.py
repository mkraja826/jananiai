from fastapi import APIRouter, HTTPException

from app.auth import CurrentUserDependency
from app.persistence import AccountDeletionRequest, SupabasePersistenceError
from app.persistence.dependencies import UserContextRepositoryDependency

router = APIRouter(prefix="/v1/account", tags=["account"])


@router.post("/deletion-request", response_model=AccountDeletionRequest)
async def request_account_deletion(
    _user: CurrentUserDependency,
    repository: UserContextRepositoryDependency,
) -> AccountDeletionRequest:
    """Create or return the caller's pending account-deletion request."""

    try:
        return await repository.request_account_deletion()
    except SupabasePersistenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
