# Atomic Deterministic Safety Rulesets

Status: engineering control implemented with synthetic validation only.

This document defines how Janani AI groups individually reviewed deterministic warning-rule releases into one deployable safety ruleset. A single rule release is never the production deployment unit.

## Safety objective

Production must never observe a partially upgraded, partially rolled-back, or internally inconsistent warning-rule collection. Every activation and rollback must either commit the complete expected ruleset or make no change.

This control does not make any current warning rule clinically approved. All existing candidate wording and sources remain development-only until authorised clinical review is complete.

## Deployment unit

A ruleset release contains:

- a unique ruleset ID and version;
- the complete list of required rule IDs;
- exactly one eligible clinical release for every required rule ID;
- the release ID and candidate-content digest for every member;
- an immutable SHA-256 manifest digest;
- approval, activation, and expiry timestamps;
- an optional superseded-ruleset reference;
- lifecycle status and terminal reason.

The required rule IDs and actual members must be equal as sets. Missing members, extra members, repeated rule IDs, repeated release IDs, changed content digests, and expired releases are rejected.

## Lifecycle

### Approval

Ruleset approval is permitted only when every member release:

- exists;
- has status `approved`;
- matches the expected rule ID and content digest;
- covers the complete requested ruleset activation window;
- appears exactly once;
- belongs to the complete required-rule manifest.

Approval stores an immutable ruleset row, immutable member rows, and a `ruleset_approved` governance event.

### First activation

When no ruleset is active, activation succeeds only when no individual clinical release is already active. This blocks unmanaged release drift.

The transaction validates the complete manifest, activates every member release, activates the ruleset, records release and ruleset events, and performs a final exact-active-set consistency check before commit.

### Replacement

When replacing an active ruleset, the transaction:

1. Locks the target ruleset, current active ruleset, and affected releases.
2. Verifies that the current active-release set exactly matches the current ruleset manifest.
3. Verifies the complete target manifest and activation windows.
4. Retires current releases that are not members of the target ruleset.
5. Activates every target release.
6. Retires the previous ruleset and activates the target ruleset.
7. Records immutable release and ruleset governance events.
8. Rechecks the exact active-release set before commit.

Any failure rolls back the whole transaction.

### Rollback

Rollback requires one active ruleset and one complete prior ruleset with status `approved` or `retired`. The prior ruleset and every member release must still be within their activation windows and retain the originally bound rule IDs and candidate digests.

The transaction marks replaced active releases and the active ruleset as `rolled_back`, restores the complete prior release set, activates the prior ruleset, records immutable events, and performs the same final consistency check.

## Database controls

The Supabase schema provides:

- private `clinical_safety_rulesets` and `clinical_safety_ruleset_members` tables;
- one-active-ruleset uniqueness enforcement;
- immutable manifest and membership fields;
- service-role-only approval, activation, and rollback functions;
- no direct access for `anon` or `authenticated` roles;
- active-release drift detection;
- transactional final-state checks;
- governance events for ruleset approval, activation, retirement, and rollback;
- explicit PostgREST schema refresh in isolated integration validation.

The approval transaction uses a locked `public, extensions` search path because Supabase installs the `pgcrypto` hashing function in the `extensions` schema.

## API boundary

End-user tokens cannot call ruleset-management RPCs or read ruleset governance tables. Only a trusted backend using the service role may invoke these operations. The service-role credential must never be present in the mobile application, browser client, logs, repository, or analytics events.

The public PostgREST approval function accepts JSON-native named parameters and delegates to the strongly typed internal transaction. Activation and rollback remain named, service-role-only RPCs.

## Verified synthetic scenarios

The local Supabase integration suite verifies:

- end-user denial for ruleset tables and RPCs;
- PostgREST discovery of approval, activation, and rollback RPCs;
- rejection of incomplete required-rule manifests;
- approval of two complete synthetic rule generations;
- first atomic activation;
- complete replacement of the first generation by the second;
- exact active-release membership after replacement;
- rollback of the second generation;
- exact restoration of the first generation;
- ruleset lifecycle states after replacement and rollback;
- immutable ruleset membership;
- immutable governance-event coverage.

## Fail-closed conditions

Activation or rollback is rejected when any of the following is true:

- a required rule is absent or an unexpected rule is present;
- rule IDs or release IDs are duplicated;
- a release or ruleset is outside its activation window;
- a member digest differs from the reviewed candidate digest;
- a member has an invalid lifecycle state;
- the database contains an active release outside the active ruleset;
- the active ruleset references a release that is not active;
- the replacement ruleset is incomplete or expired;
- the final exact-active-set check fails;
- the caller is not the service role.

## Remaining launch gates

Atomic deployment is an engineering prerequisite, not clinical authorisation. Real-user activation remains blocked until all of the following are complete:

- verified authorised reviewer administration outside source control;
- approved conflict-of-interest and clinical operating procedures;
- current, exact-section clinical sources for every rule;
- rule-specific rationale and applicability review;
- English and Telugu escalation-wording approval;
- positive, negative, boundary, interaction, and regression datasets;
- isolated hosted-staging validation;
- incident response and emergency rollback rehearsal;
- documented production access controls and audit review;
- final clinical, privacy, legal, and security sign-off.
