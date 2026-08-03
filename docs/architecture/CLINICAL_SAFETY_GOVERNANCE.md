# Clinical Safety Governance

## Status

This architecture is a governance and engineering foundation. It does not make any current warning rule clinically approved, and it does not permit real-patient use.

## Design goal

A deterministic safety rule must not become available to the production engine because a developer changed a status field. Activation requires a versioned candidate, exact-content clinical reviews, two distinct eligible reviewers with different required roles, current source material, a bounded release window, and an immutable audit trail.

## Required reviewer roles

Every releasable candidate requires approval from two distinct identities:

1. `obstetrician`
2. `clinical_safety`

A `language_reviewer` may review English or Telugu wording, but that role cannot replace either required clinical approval.

Reviewer records contain a jurisdiction, license reference, verification time, credential-expiry time, role, and active flag. The workflow rejects reviews or approvals when credentials are inactive, not yet verified, or expired.

No real reviewer identity has been entered in the repository or local test database. Tests use clearly synthetic identities only.

## Candidate immutability

A candidate contains:

- stable rule ID and version
- severity
- structured predicate key
- clinical rationale
- gestational applicability boundaries
- required structured fields
- versioned English and Telugu escalation wording
- source manifest
- optional superseded version
- SHA-256 content digest

The digest excludes database identity, creation time, and workflow status. It includes the content that affects rule meaning. Reviews bind to this digest. Changing rationale, wording, applicability, source material, severity, predicate key, or version requires a new candidate version and new reviews.

Database triggers reject mutation of candidate content after insertion. Only workflow status may change.

## Source controls

Each candidate needs at least one source record containing source identity, publisher, reference, section, review time, and expiry time.

Development candidates use `development_placeholder=true`. The Python workflow and Supabase approval RPC both reject any candidate containing a placeholder source. A release also cannot outlive the earliest source expiry.

This repository does not yet contain clinician-approved medical sources. The seven existing development warning rules are converted only into unapprovable review candidates.

## Review controls

A review records:

- candidate identity
- exact candidate digest
- reviewer identity
- reviewer-role snapshot
- decision: approve, request changes, or reject
- rationale
- review time

Reviews are append-only. Updating or deleting a review is denied by the database.

A release is denied when:

- fewer than two distinct reviewers approved
- the obstetrician role is missing
- the clinical-safety role is missing
- any review for the candidate digest requests changes or rejects
- a review refers to a different candidate or digest
- reviewer credentials are not current
- a source is missing, expired, invalid, or marked as a development placeholder
- release expiry exceeds source or reviewer-credential expiry

## Release lifecycle

The supported lifecycle is:

`approved -> active -> retired`

or

`approved -> active -> rolled_back`

Only an approved release inside its activation window can become active. One active release per rule is enforced by a partial unique index. Activating a replacement retires the previous active release for that rule.

Rollback requires an active release, a non-expired approved or retired replacement for the same rule, and a reason. The current release becomes `rolled_back`; the selected prior release becomes active.

The production engine receives `RuleMetadata` only from an active release whose digest still matches the candidate. Approved metadata requires:

- two distinct sign-off IDs
- governance release ID
- candidate digest
- approval time
- future review/expiry time

Production startup remains blocked when no current approved rule metadata is available.

## Audit history

Governance events record reviews, release approval, activation, retirement, and rollback. Event history and release-approval links are append-only. End-user roles cannot read or write governance tables or execute governance RPCs.

The mobile application must never receive a service-role key. A future controlled backend administration service may call governance RPCs after authenticating and authorising real reviewers.

## Local verification

The free CI path starts an ephemeral local Supabase stack, rebuilds all migrations, provisions synthetic users, and runs:

- existing user RLS and private-storage tests
- end-user denial tests for governance tables and RPCs
- synthetic reviewer provisioning
- exact-digest review recording
- role-separated dual approval
- release activation
- approval-link verification
- candidate-content immutability
- append-only review and event verification

The local stack is destroyed at the end of the job. The hosted Janani Supabase project is not changed.

## Remaining gates

Before any real rule can be activated:

- appoint and verify authorised clinical reviewers
- define the reviewer conflict-of-interest policy
- replace every placeholder source with reviewed current material
- write documented clinical rationale and applicability limits
- review English and Telugu wording
- add true-positive, false-positive, boundary, interaction, and regression cases
- run the workflow in an isolated hosted staging environment
- complete legal, privacy, incident-response, and clinical-validation review
- explicitly approve a production ruleset release

Until those gates pass, Janani AI remains synthetic-data-only and not clinically deployable.
