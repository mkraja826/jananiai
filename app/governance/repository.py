from typing import Protocol
from uuid import UUID

import httpx

from app.governance.models import (
    GovernancePrincipal,
    ReviewerAdministrationResult,
    ReviewerCredentialReverificationRequest,
    ReviewerDeactivationRequest,
    ReviewerOnboardingRequest,
)


class GovernanceAdministrationError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class GovernanceAdminRepository(Protocol):
    async def onboard_reviewer(
        self,
        principal: GovernancePrincipal,
        request: ReviewerOnboardingRequest,
    ) -> ReviewerAdministrationResult: ...

    async def reverify_reviewer(
        self,
        principal: GovernancePrincipal,
        reviewer_id: UUID,
        request: ReviewerCredentialReverificationRequest,
    ) -> ReviewerAdministrationResult: ...

    async def deactivate_reviewer(
        self,
        principal: GovernancePrincipal,
        reviewer_id: UUID,
        request: ReviewerDeactivationRequest,
    ) -> ReviewerAdministrationResult: ...


class SupabaseGovernanceAdminRepository:
    """Calls service-role-only RPCs from the trusted backend boundary."""

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        timeout_seconds: float = 8.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not service_role_key.strip():
            raise ValueError("Service-role key is required")
        self._supabase_url = supabase_url.rstrip("/")
        self._service_role_key = service_role_key
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def onboard_reviewer(
        self,
        principal: GovernancePrincipal,
        request: ReviewerOnboardingRequest,
    ) -> ReviewerAdministrationResult:
        reviewer_id = await self._call_rpc(
            "onboard_janani_clinical_reviewer",
            {
                "p_actor_user_id": str(principal.user_id),
                "p_reviewer_user_id": (
                    str(request.reviewer_user_id) if request.reviewer_user_id else None
                ),
                "p_display_name": request.display_name,
                "p_role": request.reviewer_role.value,
                "p_license_jurisdiction": request.license_jurisdiction,
                "p_license_reference": request.license_reference,
                "p_credential_verified_at": request.credential_verified_at.isoformat(),
                "p_credential_expires_at": request.credential_expires_at.isoformat(),
                "p_conflict_of_interest_attested_at": (
                    request.conflict_of_interest_attested_at.isoformat()
                ),
                "p_attestation_version": request.attestation_version,
                "p_evidence_reference": request.evidence_reference,
                "p_reason": request.reason,
            },
        )
        return ReviewerAdministrationResult(
            reviewer_id=reviewer_id,
            active=True,
            action="onboarded",
        )

    async def reverify_reviewer(
        self,
        principal: GovernancePrincipal,
        reviewer_id: UUID,
        request: ReviewerCredentialReverificationRequest,
    ) -> ReviewerAdministrationResult:
        returned_id = await self._call_rpc(
            "reverify_janani_clinical_reviewer",
            {
                "p_actor_user_id": str(principal.user_id),
                "p_reviewer_id": str(reviewer_id),
                "p_credential_verified_at": request.credential_verified_at.isoformat(),
                "p_credential_expires_at": request.credential_expires_at.isoformat(),
                "p_conflict_of_interest_attested_at": (
                    request.conflict_of_interest_attested_at.isoformat()
                ),
                "p_attestation_version": request.attestation_version,
                "p_evidence_reference": request.evidence_reference,
                "p_reason": request.reason,
            },
        )
        return ReviewerAdministrationResult(
            reviewer_id=returned_id,
            active=True,
            action="reverified",
        )

    async def deactivate_reviewer(
        self,
        principal: GovernancePrincipal,
        reviewer_id: UUID,
        request: ReviewerDeactivationRequest,
    ) -> ReviewerAdministrationResult:
        returned_id = await self._call_rpc(
            "deactivate_janani_clinical_reviewer",
            {
                "p_actor_user_id": str(principal.user_id),
                "p_reviewer_id": str(reviewer_id),
                "p_reason": request.reason,
            },
        )
        return ReviewerAdministrationResult(
            reviewer_id=returned_id,
            active=False,
            action="deactivated",
        )

    async def _call_rpc(self, function_name: str, payload: dict[str, object]) -> UUID:
        try:
            response = await self._client.post(
                f"{self._supabase_url}/rest/v1/rpc/{function_name}",
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.RequestError as exc:
            raise GovernanceAdministrationError(
                "Governance persistence service could not be reached"
            ) from exc

        if response.status_code in {401, 403}:
            raise GovernanceAdministrationError(
                "Governance operation was denied",
                status_code=403,
            )
        if response.status_code == 404:
            raise GovernanceAdministrationError(
                "Governance record or RPC was not found",
                status_code=404,
            )
        if response.status_code == 409:
            raise GovernanceAdministrationError(
                "Governance operation conflicts with an existing record",
                status_code=409,
            )
        if response.status_code >= 500:
            raise GovernanceAdministrationError(
                "Governance persistence service failed",
                status_code=502,
            )
        if response.status_code >= 400:
            raise GovernanceAdministrationError(
                "Governance operation was rejected",
                status_code=400,
            )

        try:
            return UUID(str(response.json()))
        except (TypeError, ValueError) as exc:
            raise GovernanceAdministrationError(
                "Governance persistence returned an invalid response"
            ) from exc
