from collections.abc import Iterable

from app.auth.models import AuthenticatedUser
from app.governance.models import GovernanceAdminRole, GovernancePrincipal

GOVERNANCE_ROLES_CLAIM = "janani_governance_roles"


class GovernanceAuthorizationError(Exception):
    """Raised when trusted app metadata does not authorize governance access."""


def governance_roles_from_user(user: AuthenticatedUser) -> frozenset[GovernanceAdminRole]:
    raw_roles = user.app_metadata.get(GOVERNANCE_ROLES_CLAIM, [])
    if not isinstance(raw_roles, list):
        raise GovernanceAuthorizationError("Governance roles claim must be a list")

    roles: set[GovernanceAdminRole] = set()
    for raw_role in raw_roles:
        if not isinstance(raw_role, str):
            raise GovernanceAuthorizationError("Governance role values must be strings")
        try:
            roles.add(GovernanceAdminRole(raw_role))
        except ValueError as exc:
            raise GovernanceAuthorizationError(
                f"Unknown governance role in trusted app metadata: {raw_role}"
            ) from exc
    return frozenset(roles)


def require_governance_roles(
    user: AuthenticatedUser,
    required_roles: Iterable[GovernanceAdminRole],
) -> GovernancePrincipal:
    required = frozenset(required_roles)
    if not required:
        raise ValueError("At least one governance role must be required")

    roles = governance_roles_from_user(user)
    missing = required - roles
    if missing:
        missing_names = sorted(role.value for role in missing)
        raise GovernanceAuthorizationError(f"Missing required governance roles: {missing_names}")
    return GovernancePrincipal(
        user_id=user.user_id,
        email=user.email,
        roles=roles,
    )
