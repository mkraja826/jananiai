import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.safety.governance import ReleaseStatus, ReviewerRole, SafetyRuleRelease
from app.safety.rulesets import (
    RulesetStatus,
    SafetyRulesetGovernanceService,
    SafetyRulesetMember,
    SafetyRulesetRelease,
)

NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)


def release(
    rule_id: str,
    *,
    release_id: UUID | None = None,
    digest: str | None = None,
    status: ReleaseStatus = ReleaseStatus.APPROVED,
    activates_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> SafetyRuleRelease:
    return SafetyRuleRelease(
        release_id=release_id or uuid4(),
        candidate_id=uuid4(),
        rule_id=rule_id,
        rule_version="1.0.0",
        candidate_digest=digest or hashlib.sha256(rule_id.encode()).hexdigest(),
        approval_review_ids=(uuid4(), uuid4()),
        reviewer_ids=(uuid4(), uuid4()),
        reviewer_roles=(ReviewerRole.OBSTETRICIAN, ReviewerRole.CLINICAL_SAFETY),
        status=status,
        approved_at=NOW - timedelta(days=1),
        activates_at=activates_at or NOW - timedelta(hours=1),
        expires_at=expires_at or NOW + timedelta(days=90),
    )


def approved_ruleset(
    service: SafetyRulesetGovernanceService,
    releases: tuple[SafetyRuleRelease, ...],
    *,
    version: str = "ruleset-1",
) -> SafetyRulesetRelease:
    return service.approve_ruleset(
        releases,
        version=version,
        required_rule_ids=tuple(item.rule_id for item in releases),
        approved_at=NOW - timedelta(minutes=30),
        activates_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(days=30),
    )


def test_approval_builds_deterministic_complete_manifest() -> None:
    service = SafetyRulesetGovernanceService()
    releases = (release("RULE-B"), release("RULE-A"))

    first = service.approve_ruleset(
        releases,
        version="2026.08.04",
        required_rule_ids=("RULE-B", "RULE-A"),
        approved_at=NOW - timedelta(minutes=5),
        activates_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )
    second = service.approve_ruleset(
        tuple(reversed(releases)),
        version="2026.08.04",
        required_rule_ids=("RULE-A", "RULE-B"),
        approved_at=NOW - timedelta(minutes=5),
        activates_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )

    assert first.status is RulesetStatus.APPROVED
    assert first.required_rule_ids == ("RULE-A", "RULE-B")
    assert tuple(member.rule_id for member in first.members) == ("RULE-A", "RULE-B")
    assert first.manifest_digest == second.manifest_digest


def test_approval_rejects_partial_duplicate_or_ineligible_members() -> None:
    service = SafetyRulesetGovernanceService()
    rule_a = release("RULE-A")
    rule_b = release("RULE-B")

    with pytest.raises(ValueError, match="at least one"):
        service.approve_ruleset((), version="empty", required_rule_ids=())
    with pytest.raises(ValueError, match="exactly match"):
        service.approve_ruleset(
            (rule_a,),
            version="partial",
            required_rule_ids=("RULE-A", "RULE-B"),
            approved_at=NOW,
        )
    with pytest.raises(ValueError, match="Required rule IDs must be unique"):
        service.approve_ruleset(
            (rule_a, rule_b),
            version="duplicate-required",
            required_rule_ids=("RULE-A", "RULE-A"),
            approved_at=NOW,
        )
    with pytest.raises(ValueError, match="duplicate rule IDs"):
        service.approve_ruleset(
            (rule_a, release("RULE-A")),
            version="duplicate-rule",
            required_rule_ids=("RULE-A",),
            approved_at=NOW,
        )
    with pytest.raises(ValueError, match="duplicate release IDs"):
        service.approve_ruleset(
            (rule_a, release("RULE-B", release_id=rule_a.release_id)),
            version="duplicate-release",
            required_rule_ids=("RULE-A", "RULE-B"),
            approved_at=NOW,
        )
    with pytest.raises(ValueError, match="approved release"):
        service.approve_ruleset(
            (rule_a.model_copy(update={"status": ReleaseStatus.ACTIVE}), rule_b),
            version="wrong-status",
            required_rule_ids=("RULE-A", "RULE-B"),
            approved_at=NOW,
        )
    with pytest.raises(ValueError, match="not eligible"):
        service.approve_ruleset(
            (release("RULE-A", activates_at=NOW + timedelta(days=1)),),
            version="future-member",
            required_rule_ids=("RULE-A",),
            approved_at=NOW,
            activates_at=NOW,
            expires_at=NOW + timedelta(days=2),
        )
    with pytest.raises(ValueError, match="expires before"):
        service.approve_ruleset(
            (release("RULE-A", expires_at=NOW + timedelta(days=1)),),
            version="short-member",
            required_rule_ids=("RULE-A",),
            approved_at=NOW,
            activates_at=NOW,
            expires_at=NOW + timedelta(days=2),
        )


def test_first_activation_is_all_or_nothing() -> None:
    service = SafetyRulesetGovernanceService()
    releases = (release("RULE-A"), release("RULE-B"))
    ruleset = approved_ruleset(service, releases)

    transition = service.activate_ruleset(ruleset, releases, activated_at=NOW)

    assert transition.active_ruleset.status is RulesetStatus.ACTIVE
    assert {item.status for item in transition.active_releases} == {ReleaseStatus.ACTIVE}
    assert transition.prior_ruleset is None
    assert transition.prior_releases == ()

    with pytest.raises(ValueError, match="exactly match"):
        service.activate_ruleset(ruleset, releases[:1], activated_at=NOW)
    with pytest.raises(ValueError, match="Active releases require"):
        service.activate_ruleset(
            ruleset,
            releases,
            active_releases=transition.active_releases,
            activated_at=NOW,
        )


def test_atomic_replacement_retires_the_complete_prior_bundle() -> None:
    service = SafetyRulesetGovernanceService()
    first_releases = (release("RULE-A"), release("RULE-B"))
    first_ruleset = approved_ruleset(service, first_releases, version="ruleset-1")
    first_active = service.activate_ruleset(first_ruleset, first_releases, activated_at=NOW)

    second_releases = (release("RULE-A"), release("RULE-B"))
    second_ruleset = approved_ruleset(service, second_releases, version="ruleset-2")
    transition = service.activate_ruleset(
        second_ruleset,
        second_releases,
        active_ruleset=first_active.active_ruleset,
        active_releases=first_active.active_releases,
        activated_at=NOW,
        reason="Synthetic ruleset replacement",
    )

    assert transition.active_ruleset.status is RulesetStatus.ACTIVE
    assert transition.prior_ruleset is not None
    assert transition.prior_ruleset.status is RulesetStatus.RETIRED
    assert len(transition.prior_releases) == 2
    assert {item.status for item in transition.prior_releases} == {ReleaseStatus.RETIRED}
    assert {item.status for item in transition.active_releases} == {ReleaseStatus.ACTIVE}


def test_atomic_rollback_restores_the_complete_prior_bundle() -> None:
    service = SafetyRulesetGovernanceService()
    first_releases = (release("RULE-A"), release("RULE-B"))
    first_ruleset = approved_ruleset(service, first_releases, version="ruleset-1")
    first_active = service.activate_ruleset(first_ruleset, first_releases, activated_at=NOW)

    second_releases = (release("RULE-A"), release("RULE-B"))
    second_ruleset = approved_ruleset(service, second_releases, version="ruleset-2")
    second_active = service.activate_ruleset(
        second_ruleset,
        second_releases,
        active_ruleset=first_active.active_ruleset,
        active_releases=first_active.active_releases,
        activated_at=NOW,
    )
    assert second_active.prior_ruleset is not None

    rollback = service.rollback_ruleset(
        second_active.active_ruleset,
        second_active.active_releases,
        second_active.prior_ruleset,
        second_active.prior_releases,
        "Synthetic regression rollback",
        rolled_back_at=NOW + timedelta(minutes=1),
    )

    assert rollback.active_ruleset.status is RulesetStatus.ACTIVE
    assert rollback.active_ruleset.version == "ruleset-1"
    assert rollback.prior_ruleset is not None
    assert rollback.prior_ruleset.status is RulesetStatus.ROLLED_BACK
    assert {item.status for item in rollback.active_releases} == {ReleaseStatus.ACTIVE}
    assert {item.status for item in rollback.prior_releases} == {ReleaseStatus.ROLLED_BACK}


def test_manifest_and_lifecycle_validation_fail_closed() -> None:
    service = SafetyRulesetGovernanceService()
    releases = (release("RULE-A"), release("RULE-B"))
    ruleset = approved_ruleset(service, releases)

    invalid_member = SafetyRulesetMember(
        rule_id="RULE-A",
        release_id=releases[0].release_id,
        candidate_digest="f" * 64,
    )
    with pytest.raises(ValidationError, match="digest"):
        SafetyRulesetRelease(
            ruleset_id=ruleset.ruleset_id,
            version=ruleset.version,
            status=ruleset.status,
            required_rule_ids=ruleset.required_rule_ids,
            members=(invalid_member, ruleset.members[1]),
            manifest_digest=ruleset.manifest_digest,
            approved_at=ruleset.approved_at,
            activates_at=ruleset.activates_at,
            expires_at=ruleset.expires_at,
        )

    tampered_ruleset = ruleset.model_copy(
        update={
            "members": (
                ruleset.members[0].model_copy(update={"candidate_digest": "f" * 64}),
                ruleset.members[1],
            )
        }
    )
    with pytest.raises(ValueError, match="digest does not match"):
        service.activate_ruleset(tampered_ruleset, releases, activated_at=NOW)

    with pytest.raises(ValueError, match="Only approved rulesets"):
        service.activate_ruleset(
            ruleset.model_copy(update={"status": RulesetStatus.RETIRED}),
            releases,
            activated_at=NOW,
        )
    with pytest.raises(ValueError, match="activation window"):
        service.activate_ruleset(
            ruleset.model_copy(update={"expires_at": NOW}),
            releases,
            activated_at=NOW,
        )


def test_rollback_rejects_invalid_state_reason_window_and_registry() -> None:
    service = SafetyRulesetGovernanceService()
    releases = (release("RULE-A"), release("RULE-B"))
    ruleset = approved_ruleset(service, releases)
    active = service.activate_ruleset(ruleset, releases, activated_at=NOW)
    replacement = ruleset.model_copy(update={"status": RulesetStatus.RETIRED})
    retired_releases = tuple(
        item.model_copy(update={"status": ReleaseStatus.RETIRED}) for item in active.active_releases
    )

    with pytest.raises(ValueError, match="reason"):
        service.rollback_ruleset(
            active.active_ruleset,
            active.active_releases,
            replacement,
            retired_releases,
            "x",
            rolled_back_at=NOW,
        )
    with pytest.raises(ValueError, match="Only an active"):
        service.rollback_ruleset(
            active.active_ruleset.model_copy(update={"status": RulesetStatus.RETIRED}),
            active.active_releases,
            replacement,
            retired_releases,
            "Synthetic rollback",
            rolled_back_at=NOW,
        )
    with pytest.raises(ValueError, match="approved prior"):
        service.rollback_ruleset(
            active.active_ruleset,
            active.active_releases,
            replacement.model_copy(update={"status": RulesetStatus.ACTIVE}),
            retired_releases,
            "Synthetic rollback",
            rolled_back_at=NOW,
        )
    with pytest.raises(ValueError, match="activation window"):
        service.rollback_ruleset(
            active.active_ruleset,
            active.active_releases,
            replacement.model_copy(update={"expires_at": NOW}),
            retired_releases,
            "Synthetic rollback",
            rolled_back_at=NOW,
        )
    with pytest.raises(ValueError, match="exactly match"):
        service.rollback_ruleset(
            active.active_ruleset,
            active.active_releases,
            replacement,
            retired_releases[:1],
            "Synthetic rollback",
            rolled_back_at=NOW,
        )
