# Reviewer Administration and Safety Validation

Status: engineering controls implemented with synthetic validation only.

This document defines the trusted administration boundary for clinical reviewers and the minimum executable validation-dataset contract for every deterministic safety rule. Neither control constitutes clinical approval.

## Reviewer authority boundary

Reviewer administration is disabled by default. When enabled, it requires:

- normal Supabase authentication;
- a verified user access token;
- a trusted `janani_governance_roles` claim stored in Supabase `app_metadata`;
- the `reviewer_admin` role for reviewer lifecycle operations;
- a backend-only Supabase service-role key;
- service-role-only database RPCs.

User-editable metadata is never used for governance authorization. Bearer tokens, trusted app metadata, and the service-role key are excluded from response serialization and log-safe object representations.

The mobile application and browser client must never receive the service-role key. Governance routes call Supabase only from the trusted backend process.

## Governance roles

The current backend role vocabulary is:

- `reviewer_admin`: may invoke reviewer onboarding, reverification, and deactivation routes;
- `safety_release_manager`: reserved for controlled candidate, release, and ruleset operations;
- `auditor`: reserved for read-only governance review.

Unknown roles, non-string values, malformed claims, and missing required roles fail closed.

## Reviewer onboarding

A reviewer onboarding request requires:

- an immutable reviewer display identity;
- reviewer role;
- license jurisdiction and opaque license reference;
- credential verification and expiry timestamps;
- conflict-of-interest attestation and timestamp;
- attestation-policy version;
- an opaque evidence reference;
- a substantive administrative reason;
- the authenticated governance administrator identity.

The evidence reference must point to controlled evidence storage. Raw license scans, identity documents, or sensitive reviewer records must not be placed in source control, normal application logs, analytics events, or governance API responses.

A reviewer may optionally be linked to an existing Supabase user identity. That linkage does not itself grant governance-administration authority.

## Reverification

Credential and conflict-of-interest evidence may be renewed only through the controlled reverification RPC. Direct table updates are denied by a database trigger.

Reverification preserves immutable reviewer identity fields and records an append-only event containing:

- reviewer aggregate ID;
- governance administrator user ID;
- attestation version;
- prior and new credential-expiry timestamps;
- administrative reason.

An inactive reviewer cannot be reverified. Re-onboarding or another explicitly reviewed lifecycle procedure is required.

## Deactivation

Reviewer deactivation requires a substantive reason and records the administrator, timestamp, and reason. It is rejected when the reviewer has an approval attached to an active clinical release. The active release or ruleset must first be safely retired or rolled back.

This prevents removing the credential basis of an actively deployed safety rule while leaving that rule active.

Repeated deactivation fails closed. Direct mutation of reviewer lifecycle fields remains blocked.

## Audit history

Reviewer administration adds immutable governance events:

- `reviewer_onboarded`;
- `reviewer_reverified`;
- `reviewer_deactivated`.

Events use the reviewer as the aggregate and include the authenticated governance administrator's user ID. End-user roles cannot read reviewer tables or invoke management RPCs.

## HTTP API

The protected backend routes are:

- `POST /v1/governance/reviewers`;
- `POST /v1/governance/reviewers/{reviewer_id}/reverify`;
- `POST /v1/governance/reviewers/{reviewer_id}/deactivate`.

When the administration API is disabled, these routes return not found. When enabled, authentication and trusted `reviewer_admin` authorization are mandatory.

## Executable validation datasets

Every development rule must have at least one case in each required category:

1. **True positive** — the exact structured predicate triggers its target rule.
2. **True negative** — nearby or absent inputs do not trigger the target rule.
3. **Boundary** — the rule behaves deterministically at a supported gestational-week endpoint.
4. **Interaction** — multiple simultaneous predicates retain all matching rule IDs and select the highest severity.
5. **Regression** — previously dangerous behavior remains blocked, including free text attempting to trigger deterministic rules without structured fields.

The current development dataset contains 35 synthetic cases: five categories for each of seven development rules.

## Case expectations

Each case binds:

- a unique case ID;
- one target rule ID;
- category;
- synthetic structured input;
- exact triggered state;
- expected severity;
- exact triggered-rule set;
- expected LLM-blocking state;
- rationale.

Triggered cases must block LLM processing. Non-triggered cases cannot declare triggered rule IDs. Interaction cases require multiple expected rule IDs. Regression cases must explicitly document the ignored free-text input.

The dataset contract rejects:

- duplicate case IDs;
- missing development rules;
- missing categories for any rule;
- real-data payloads;
- invalid expectations;
- unsupported boundary weeks.

## Validation runner

The runner executes every case against a supplied deterministic safety engine and compares:

- whether a warning triggered;
- highest severity;
- exact triggered-rule set;
- whether LLM processing is blocked.

It produces per-case mismatch details and per-rule case counts. A dataset passes only when every case passes.

Passing these synthetic datasets proves engineering consistency only. It does not establish sensitivity, specificity, clinical validity, local standard-of-care alignment, or safe patient use.

## Remaining clinical gates

Before any rule may become clinically approved or active for real users:

- authorised reviewer onboarding policy must be approved;
- actual reviewer credentials must be verified outside source control;
- conflict-of-interest procedures must be operational;
- placeholder sources must be replaced with current exact-section references;
- every predicate, severity, applicability boundary, and escalation message must receive clinical approval;
- Telugu wording must receive qualified language and clinical review;
- datasets must be expanded with clinician-authored positive, negative, boundary, interaction, regression, ambiguity, missing-data, and adversarial examples;
- expected results must be signed off independently of the implementation team;
- an isolated hosted-staging rehearsal must pass;
- incident response and emergency rollback must be rehearsed;
- legal, privacy, security, and clinical launch gates must pass.

All current rules and datasets remain synthetic, development-only, and prohibited from real clinical use.
