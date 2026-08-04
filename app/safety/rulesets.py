"""Atomic clinical-safety ruleset governance.

A ruleset is the deployable unit for deterministic warning rules. Individual
releases may be clinically approved, but production activation happens only as
one complete, content-bound ruleset transition.
"""

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.safety.governance import ReleaseStatus, SafetyRuleRelease


class RulesetStatus(StrEnum):
    APPROVED = "approved"
    ACTIVE = "active"
    EXPIRED = "expired"
    RETIRED = "retired"
    ROLLED_BACK = "rolled_back"


class FrozenRulesetModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SafetyRulesetMember(FrozenRulesetModel):
    rule_id: Annotated[str, Field(min_length=3, max_length=120)]
    release_id: UUID
    candidate_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SafetyRulesetRelease(FrozenRulesetModel):
    ruleset_id: UUID = Field(default_factory=uuid4)
    version: Annotated[str, Field(min_length=1, max_length=80)]
    status: RulesetStatus
    required_rule_ids: Annotated[tuple[str, ...], Field(min_length=1)]
    members: Annotated[tuple[SafetyRulesetMember, ...], Field(min_length=1)]
    manifest_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    approved_at: datetime
    activates_at: datetime
    expires_at: datetime
    supersedes_ruleset_id: UUID | None = None
    terminal_reason: str | None = None

    @staticmethod
    def calculate_manifest_digest(
        version: str,
        required_rule_ids: tuple[str, ...],
        members: tuple[SafetyRulesetMember, ...],
    ) -> str:
        payload = {
            "version": version,
            "required_rule_ids": sorted(required_rule_ids),
            "members": [
                member.model_dump(mode="json")
                for member in sorted(members, key=lambda item: item.rule_id)
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @model_validator(mode="after")
    def validate_ruleset(self) -> "SafetyRulesetRelease":
        timestamps = (self.approved_at, self.activates_at, self.expires_at)
        if any(value.utcoffset() is None for value in timestamps):
            raise ValueError("Ruleset timestamps must include timezone information")
        if self.activates_at < self.approved_at:
            raise ValueError("Ruleset activation cannot precede approval")
        if self.expires_at <= self.activates_at:
            raise ValueError("Ruleset expiry must follow activation")

        required = set(self.required_rule_ids)
        member_rule_ids = {member.rule_id for member in self.members}
        if len(required) != len(self.required_rule_ids):
            raise ValueError("Required rule IDs must be unique")
        if len(member_rule_ids) != len(self.members):
            raise ValueError("Ruleset members must contain unique rule IDs")
        release_ids = {member.release_id for member in self.members}
        if len(release_ids) != len(self.members):
            raise ValueError("Ruleset members must contain unique release IDs")
        if member_rule_ids != required:
            raise ValueError("Ruleset members must exactly match required rule IDs")

        expected_digest = self.calculate_manifest_digest(
            self.version,
            self.required_rule_ids,
            self.members,
        )
        if self.manifest_digest != expected_digest:
            raise ValueError("Ruleset manifest digest does not match its content")
        return self


class RulesetTransition(FrozenRulesetModel):
    active_ruleset: SafetyRulesetRelease
    active_releases: tuple[SafetyRuleRelease, ...]
    prior_ruleset: SafetyRulesetRelease | None = None
    prior_releases: tuple[SafetyRuleRelease, ...] = ()


class SafetyRulesetGovernanceService:
    def approve_ruleset(
        self,
        releases: tuple[SafetyRuleRelease, ...],
        *,
        version: str,
        required_rule_ids: tuple[str, ...],
        approved_at: datetime | None = None,
        activates_at: datetime | None = None,
        expires_at: datetime | None = None,
        supersedes_ruleset_id: UUID | None = None,
    ) -> SafetyRulesetRelease:
        checked_at = approved_at or datetime.now(UTC)
        activation_time = activates_at or checked_at
        if not releases:
            raise ValueError("A ruleset requires at least one approved release")

        release_by_rule = {release.rule_id: release for release in releases}
        if len(release_by_rule) != len(releases):
            raise ValueError("A ruleset cannot contain duplicate rule IDs")
        release_ids = {release.release_id for release in releases}
        if len(release_ids) != len(releases):
            raise ValueError("A ruleset cannot contain duplicate release IDs")

        required = set(required_rule_ids)
        if len(required) != len(required_rule_ids):
            raise ValueError("Required rule IDs must be unique")
        if set(release_by_rule) != required:
            raise ValueError("Approved releases must exactly match required rule IDs")
        if any(release.status is not ReleaseStatus.APPROVED for release in releases):
            raise ValueError("Every ruleset member must be an approved release")

        maximum_expiry = min(release.expires_at for release in releases)
        requested_expiry = expires_at or maximum_expiry
        if requested_expiry <= activation_time:
            raise ValueError("Ruleset expiry must follow activation")
        for release in releases:
            if release.activates_at > activation_time:
                raise ValueError("A member release is not eligible at ruleset activation")
            if release.expires_at < requested_expiry:
                raise ValueError("A member release expires before the ruleset")

        members = tuple(
            SafetyRulesetMember(
                rule_id=release.rule_id,
                release_id=release.release_id,
                candidate_digest=release.candidate_digest,
            )
            for release in sorted(releases, key=lambda item: item.rule_id)
        )
        ordered_required = tuple(sorted(required_rule_ids))
        digest = SafetyRulesetRelease.calculate_manifest_digest(
            version,
            ordered_required,
            members,
        )
        return SafetyRulesetRelease(
            version=version,
            status=RulesetStatus.APPROVED,
            required_rule_ids=ordered_required,
            members=members,
            manifest_digest=digest,
            approved_at=checked_at,
            activates_at=activation_time,
            expires_at=requested_expiry,
            supersedes_ruleset_id=supersedes_ruleset_id,
        )

    def activate_ruleset(
        self,
        ruleset: SafetyRulesetRelease,
        releases: tuple[SafetyRuleRelease, ...],
        *,
        active_ruleset: SafetyRulesetRelease | None = None,
        active_releases: tuple[SafetyRuleRelease, ...] = (),
        activated_at: datetime | None = None,
        reason: str = "Superseded by an atomic ruleset activation",
    ) -> RulesetTransition:
        checked_at = activated_at or datetime.now(UTC)
        if ruleset.status is not RulesetStatus.APPROVED:
            raise ValueError("Only approved rulesets may be activated")
        if not (ruleset.activates_at <= checked_at < ruleset.expires_at):
            raise ValueError("Ruleset is outside its activation window")

        allowed_statuses = {ReleaseStatus.APPROVED}
        if active_ruleset is not None:
            if active_ruleset.status is not RulesetStatus.ACTIVE:
                raise ValueError("The prior ruleset must be active")
            self._validate_manifest(
                active_ruleset,
                active_releases,
                checked_at,
                {ReleaseStatus.ACTIVE},
            )
            allowed_statuses.add(ReleaseStatus.ACTIVE)
        elif active_releases:
            raise ValueError("Active releases require an active ruleset")

        self._validate_manifest(ruleset, releases, checked_at, allowed_statuses)
        replacement_ids = {member.release_id for member in ruleset.members}

        activated_releases = tuple(
            release.model_copy(update={"status": ReleaseStatus.ACTIVE, "terminal_reason": None})
            for release in sorted(releases, key=lambda item: item.rule_id)
        )
        retired_releases = tuple(
            release.model_copy(update={"status": ReleaseStatus.RETIRED, "terminal_reason": reason})
            for release in sorted(active_releases, key=lambda item: item.rule_id)
            if release.release_id not in replacement_ids
        )
        retired_ruleset = (
            active_ruleset.model_copy(
                update={"status": RulesetStatus.RETIRED, "terminal_reason": reason}
            )
            if active_ruleset is not None
            else None
        )
        active = ruleset.model_copy(
            update={"status": RulesetStatus.ACTIVE, "terminal_reason": None}
        )
        return RulesetTransition(
            active_ruleset=active,
            active_releases=activated_releases,
            prior_ruleset=retired_ruleset,
            prior_releases=retired_releases,
        )

    def rollback_ruleset(
        self,
        active_ruleset: SafetyRulesetRelease,
        active_releases: tuple[SafetyRuleRelease, ...],
        replacement_ruleset: SafetyRulesetRelease,
        replacement_releases: tuple[SafetyRuleRelease, ...],
        reason: str,
        *,
        rolled_back_at: datetime | None = None,
    ) -> RulesetTransition:
        checked_at = rolled_back_at or datetime.now(UTC)
        if len(reason.strip()) < 3:
            raise ValueError("Rollback reason is required")
        if active_ruleset.status is not RulesetStatus.ACTIVE:
            raise ValueError("Only an active ruleset may be rolled back")
        if replacement_ruleset.status not in {
            RulesetStatus.APPROVED,
            RulesetStatus.RETIRED,
        }:
            raise ValueError("Rollback replacement must be an approved prior ruleset")
        if not (replacement_ruleset.activates_at <= checked_at < replacement_ruleset.expires_at):
            raise ValueError("Rollback replacement is outside its activation window")

        self._validate_manifest(
            active_ruleset,
            active_releases,
            checked_at,
            {ReleaseStatus.ACTIVE},
        )
        self._validate_manifest(
            replacement_ruleset,
            replacement_releases,
            checked_at,
            {
                ReleaseStatus.APPROVED,
                ReleaseStatus.RETIRED,
                ReleaseStatus.ACTIVE,
            },
        )

        replacement_ids = {member.release_id for member in replacement_ruleset.members}
        rolled_back_releases = tuple(
            release.model_copy(
                update={"status": ReleaseStatus.ROLLED_BACK, "terminal_reason": reason}
            )
            for release in sorted(active_releases, key=lambda item: item.rule_id)
            if release.release_id not in replacement_ids
        )
        restored_releases = tuple(
            release.model_copy(update={"status": ReleaseStatus.ACTIVE, "terminal_reason": None})
            for release in sorted(replacement_releases, key=lambda item: item.rule_id)
        )
        rolled_back = active_ruleset.model_copy(
            update={"status": RulesetStatus.ROLLED_BACK, "terminal_reason": reason}
        )
        restored = replacement_ruleset.model_copy(
            update={"status": RulesetStatus.ACTIVE, "terminal_reason": None}
        )
        return RulesetTransition(
            active_ruleset=restored,
            active_releases=restored_releases,
            prior_ruleset=rolled_back,
            prior_releases=rolled_back_releases,
        )

    def _validate_manifest(
        self,
        ruleset: SafetyRulesetRelease,
        releases: tuple[SafetyRuleRelease, ...],
        checked_at: datetime,
        allowed_statuses: set[ReleaseStatus],
    ) -> None:
        release_by_id = {release.release_id: release for release in releases}
        if len(release_by_id) != len(releases):
            raise ValueError("Release registry contains duplicate identities")
        member_ids = {member.release_id for member in ruleset.members}
        if set(release_by_id) != member_ids:
            raise ValueError("Release registry does not exactly match the ruleset manifest")

        for member in ruleset.members:
            release = release_by_id[member.release_id]
            if release.rule_id != member.rule_id:
                raise ValueError("Ruleset member rule ID does not match its release")
            if release.candidate_digest != member.candidate_digest:
                raise ValueError("Ruleset member digest does not match its release")
            if release.status not in allowed_statuses:
                raise ValueError("Ruleset member release has an invalid lifecycle status")
            if not (release.activates_at <= checked_at < release.expires_at):
                raise ValueError("Ruleset member release is outside its activation window")
