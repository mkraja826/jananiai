# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 29%

Updated: 2026-08-07
Branch: `phase-7/clinical-review-rehearsal`
Latest verified implementation commit: `de9b594`
Draft PR: `#7`

## Foundation completed and verified

- [x] Repository initialised.
- [x] Mission, intended role, and safety boundaries documented.
- [x] Free-first development policy established.
- [x] Python/FastAPI project foundation created.
- [x] Typed health, readiness, and safety-evaluation API contracts created.
- [x] Deterministic safety-engine core created.
- [x] Draft synthetic-test warning rules created.
- [x] Production mode excludes unapproved rules.
- [x] Provider-independent LLM protocol created.
- [x] Mock LLM provider created; no paid API required.
- [x] Privacy-minimised safety audit model and development recorder created.
- [x] Safety API records minimal audit events without raw notes or symptom fields.
- [x] Clinician approval metadata requires sign-off, approval time, and review deadline.
- [x] Production startup blocks when no current approved ruleset is active.
- [x] Pytest, Ruff, Docker, and GitHub Actions foundations created.
- [x] Foundation architecture, ADRs, threat model, and permanent progress tracker created.

## Phase 2 data and context foundation completed and verified

- [x] Added privacy-minimised user health, pregnancy, medication, and appointment models.
- [x] Excluded direct identifiers from AI context-domain models.
- [x] Added append-only consent events with grant and revocation resolution by purpose.
- [x] Separated care support, AI processing, attachment processing, model improvement, and research consent.
- [x] Added attachment type, extraction state, confidence, and user-confirmation contracts.
- [x] Blocked attachment text from AI context until extraction is complete and user-confirmed.
- [x] Added task-specific context inclusion and exclusion policies.
- [x] Implemented the deterministic Context Assembly Engine using synthetic records.
- [x] Added safety-first blocking before any LLM request can be assembled.
- [x] Added explicit attachment selection for report explanations.
- [x] Added active and confirmed medication filtering.
- [x] Added approved and review-valid knowledge filtering.
- [x] Added context-size budgeting and optional-context trimming.
- [x] Added versioned, provider-neutral `JananiLLMRequest` schema.
- [x] Added `POST /v1/context/assemble` synthetic-only API endpoint.
- [x] Added privacy-minimised context audit events containing IDs and decisions only.
- [x] Added Supabase schema for profiles, pregnancies, consent, medication, appointments, attachments, extraction versions, and context audits.
- [x] Added owner-scoped RLS policies and private storage policies.
- [x] Added database triggers preventing records from being linked to another user's pregnancy.
- [x] Added tests for consent revocation, data confirmation, task relevance, safety blocking, budgets, API behavior, and audit minimisation.

## Phase 3 authenticated persistence and local RLS validation completed

- [x] Added Supabase bearer-token verification through the Auth user endpoint.
- [x] Added verified request identity with bearer tokens excluded from serialization and logs.
- [x] Made authentication and Supabase configuration mandatory in staging and production.
- [x] Added an RLS-scoped PostgREST client using the verified caller token and publishable key.
- [x] Added server-side loading for profiles, active pregnancy, consent history, medications, appointments, attachments, and extraction versions.
- [x] Added `POST /v1/context/assemble-stored`; clients no longer need to send their complete health history for this path.
- [x] Added identity matching between the verified user and repository client.
- [x] Added authenticated database RPCs for minimal safety and context audit writes.
- [x] Kept questions, symptom notes, extracted report text, prompts, and model outputs out of audit RPC payloads.
- [x] Added attachment extraction state transitions: start, process, complete/fail, confirm/reject.
- [x] Added owner-scoped attachment-confirmation RPC.
- [x] Added a service-role-only extraction writer RPC while keeping direct extraction-table writes closed.
- [x] Added account-deletion request table, RPC, model, and protected endpoint.
- [x] Added explicit grants and revokes for user-owned and internal tables.
- [x] Added owner-read policy for safety audit events.
- [x] Added free local Supabase configuration and synthetic-user provisioning.
- [x] Added a separate GitHub Actions local-Supabase job requiring no paid branch or hosted credentials.
- [x] Rebuilt all six migrations from an empty local Postgres database.
- [x] Created and authenticated two ephemeral synthetic users.
- [x] Verified profile and pregnancy owner isolation.
- [x] Verified append-only consent history.
- [x] Verified medication, appointment, and attachment ownership links.
- [x] Verified direct writes to audit and extraction tables are denied.
- [x] Verified owner-scoped audit and attachment-confirmation RPCs.
- [x] Verified service-role-only extraction writes.
- [x] Verified private Storage object paths are owner-scoped.
- [x] Verified deletion requests are private and idempotent.
- [x] Added Windows PowerShell instructions for the same local validation flow.
- [x] GitHub Actions passed on `5b4210a`: quality pipeline and free local-Supabase pipeline both green; 9/9 local RLS/RPC/Storage tests passed.

## Phase 4 clinical safety governance foundation completed and verified

- [x] Replaced single-signoff approval metadata with two distinct clinician sign-offs.
- [x] Bound approved engine rules to a governance release ID and SHA-256 candidate digest.
- [x] Added reviewer roles for obstetrician, clinical safety, and language review.
- [x] Added reviewer identity, jurisdiction, license reference, verification time, expiry, and active status.
- [x] Added clinical-source provenance, section, review time, expiry, and development-placeholder controls.
- [x] Added gestational applicability boundaries and required structured-input fields.
- [x] Added versioned English and Telugu escalation-wording contracts.
- [x] Added immutable candidate content digests and exact-content clinical reviews.
- [x] Required two distinct reviewers with obstetrician and clinical-safety roles for release approval.
- [x] Prevented releases from outliving their sources or reviewer credentials.
- [x] Added approved, active, retired, expired, and rolled-back release states.
- [x] Added activation, retirement, replacement, and rollback controls.
- [x] Added immutable governance-event models and append-only database history.
- [x] Converted all seven development warning rules into versioned review candidates.
- [x] Marked every current candidate with development-placeholder provenance so approval remains impossible.
- [x] Added service-role-only Supabase reviewer, candidate, review, release, approval, and event tables.
- [x] Denied end-user access to all clinical-governance tables and RPCs.
- [x] Added per-approval validation of reviewer identity, role, candidate digest, and credential validity.
- [x] Added static migration-contract tests and adversarial governance tests.
- [x] Added local-Supabase integration tests for end-user denial, dual approval, activation, immutability, and append-only history.
- [x] Documented the clinical safety governance lifecycle and remaining launch gates.
- [x] GitHub Actions passed on `148565f`: Ruff lint and formatting, 27 safety tests, 96.87% safety-module coverage, 80 full-suite tests, 10 expected staging skips, Docker build, eight migrations rebuilt from zero, and 10/10 local RLS/RPC/Storage/governance tests.

## Phase 5 atomic safety ruleset activation completed and verified

- [x] Made a complete deterministic safety ruleset the deployable unit instead of an individual rule release.
- [x] Added immutable ruleset and member domain models.
- [x] Added a complete required-rule manifest with exactly one release per required rule ID.
- [x] Bound every ruleset member to its release ID, rule ID, and reviewed candidate digest.
- [x] Added deterministic SHA-256 ruleset manifest digests.
- [x] Rejected partial, extra, duplicate, altered, expired, or invalid-state member collections.
- [x] Added pure-domain atomic approval, first activation, replacement, and rollback transitions.
- [x] Added private Supabase ruleset and ruleset-member tables.
- [x] Enforced at most one active clinical safety ruleset.
- [x] Made ruleset manifests and membership immutable.
- [x] Added service-role-only ruleset approval, activation, and rollback RPCs.
- [x] Denied `anon` and `authenticated` access to ruleset tables and management RPCs.
- [x] Added active-release drift detection before activation and rollback.
- [x] Added final exact-active-release-set consistency checks inside each transaction.
- [x] Added ruleset approval, activation, retirement, and rollback governance events.
- [x] Added PostgREST OpenAPI discovery validation for all three ruleset RPCs.
- [x] Added explicit local PostgREST schema refresh after migration reset.
- [x] Resolved pgcrypto hashing under a locked `public, extensions` security-definer search path.
- [x] Added adversarial unit tests for incomplete manifests, altered digests, duplicate identities, invalid states, and expired members.
- [x] Added a two-generation local-Supabase test proving complete activation, replacement, exact active membership, and rollback restoration.
- [x] Documented the atomic ruleset architecture, failure modes, API boundary, and launch gates.
- [x] GitHub Actions passed on `59c7c10`: Ruff lint and formatting, 34 safety tests with 97.44% safety-module coverage, 94 full-suite tests with 12 expected staging skips, Docker build, all migrations rebuilt from zero, and 12/12 local RLS/RPC/Storage/governance/atomic-ruleset integration tests.

## Phase 6 reviewer administration and safety validation datasets completed and verified

- [x] Added trusted governance-role claims sourced only from Supabase `app_metadata`.
- [x] Explicitly ignored user-editable metadata for governance authorization.
- [x] Added `reviewer_admin`, `safety_release_manager`, and `auditor` role contracts.
- [x] Made malformed, unknown, non-string, and missing governance roles fail closed.
- [x] Kept bearer tokens, trusted app metadata, and service-role secrets out of serialization and repr output.
- [x] Added reviewer onboarding, credential reverification, deactivation, and result models.
- [x] Required timezone-aware credential windows, conflict-of-interest attestation, attestation version, opaque evidence reference, and substantive reason.
- [x] Added a governance administration API that is disabled by default.
- [x] Required authentication, Supabase configuration, and a backend-only service-role key before the administration API can be enabled.
- [x] Added protected reviewer onboarding, reverification, and deactivation routes.
- [x] Added a service-role-backed repository so mobile and browser clients never receive the service-role key.
- [x] Made reviewer identity, role, jurisdiction, and license reference immutable after onboarding.
- [x] Allowed credential and lifecycle updates only through controlled database RPCs.
- [x] Added append-only reviewer-onboarded, reviewer-reverified, and reviewer-deactivated governance events with administrator user IDs.
- [x] Blocked reviewer deactivation while the reviewer has an approval on an active release.
- [x] Kept end-user access to reviewer tables and lifecycle RPCs denied.
- [x] Added executable true-positive, true-negative, boundary, interaction, and regression categories.
- [x] Added 35 synthetic validation cases: five categories for each of seven development warning rules.
- [x] Added exact expected triggered-rule sets, highest severity, and LLM-blocking assertions.
- [x] Added free-text regression cases proving notes cannot trigger deterministic rules without structured fields.
- [x] Added fail-closed checks for duplicate cases, incomplete rule coverage, missing categories, real-data payloads, and invalid expectations.
- [x] Added per-case mismatch reports and per-rule case counts.
- [x] Added HTTP, repository, authorization, model, configuration, migration, and local-Supabase lifecycle tests.
- [x] Documented reviewer authority, evidence handling, validation categories, API boundaries, and remaining clinical gates.
- [x] GitHub Actions passed on `dcda56f`: Ruff lint and formatting, 49 safety tests with 96.33% safety-module coverage, 149 full-suite tests with 13 expected staging skips, Docker build, all migrations rebuilt from zero, and 13/13 local RLS/RPC/Storage/governance/reviewer-lifecycle integration tests.

## Phase 7 pre-clinical review packets and rollback rehearsal completed and verified

- [x] Expanded deterministic validation from 35 to 63 synthetic cases.
- [x] Required nine categories for every one of the seven development rules: true positive, true negative, boundary, interaction, regression, ambiguity, missing data, adversarial, and cross-rule.
- [x] Added challenge cases proving ambiguous and prompt-like free text cannot manufacture structured deterministic warning signals.
- [x] Added missing-data cases documenting current behavior when gestational week is unavailable.
- [x] Added three-rule cross-interaction cases with exact rule-set and highest-severity expectations.
- [x] Added immutable pre-clinical review-packet models.
- [x] Bound each packet to candidate ID, version, canonical candidate SHA-256 digest, validation dataset version, dataset SHA-256 digest, and exact target-rule case IDs.
- [x] Required fully passing engineering validation and all nine categories before a packet can be built or persisted.
- [x] Required obstetrician, clinical-safety, and language-review roles in every packet.
- [x] Added future reviewer-attestation contracts tied to the exact packet digest.
- [x] Required approval attestations to confirm expected results, sources and sections, and escalation wording.
- [x] Kept packets non-eligible for clinical approval while development-placeholder sources remain.
- [x] Added a synthetic emergency rollback rehearsal runner using the existing atomic ruleset rollback service.
- [x] Required six rehearsal evidence steps: incident detection, active-manifest verification, atomic rollback, restored-manifest verification, rolled-back-state verification, and audit evidence.
- [x] Verified exact prior ruleset restoration and incident ruleset rollback state.
- [x] Added private append-only review-packet and safety-rehearsal Supabase tables.
- [x] Added service-role-only RPCs for recording review packets and rehearsal evidence.
- [x] Denied normal users read access and RPC execution for the evidence tables.
- [x] Blocked update and delete after evidence insertion, including for the service role.
- [x] Added review-packet-recorded and rehearsal-recorded immutable governance events with administrator user IDs.
- [x] Found PostgreSQL error `42702` (`column reference "value" is ambiguous`) in rehearsal step extraction during real local-Supabase validation.
- [x] Fixed the SQL with explicit JSON-element and `unnest` aliases instead of weakening the test.
- [x] Hardened rehearsal persistence to require top-level `passed=true`, exactly six unique required steps, every step `passed=true`, and a nonempty evidence reference for every step.
- [x] Documented the pre-clinical review dossier, attestation boundary, immutable evidence store, and remaining launch gates.
- [x] GitHub Actions passed on `de9b594`: Ruff lint and formatting, 63 safety tests with 95.43% safety-module coverage, 168 full-suite tests with 14 expected staging skips, Docker build, every migration rebuilt from zero, two synthetic users provisioned, and 14/14 local RLS/RPC/Storage/governance/reviewer/evidence/rehearsal integration tests.

## Current limitations

- No real licensed clinician has been onboarded through the reviewer administration flow.
- No real reviewer credential, attestation, or identity-evidence document has been stored or verified.
- The governance administration API remains disabled by default and has only synthetic validation.
- No warning rule has been reviewed or approved by a licensed clinician.
- Every current safety candidate contains development-placeholder provenance and cannot be activated.
- Current English and Telugu escalation wording remains development-only and not clinically approved.
- The 63 validation cases and review packets are synthetic engineering evidence, not clinical validation, diagnostic performance evidence, or real-world safety evidence.
- Rollback rehearsal evidence is synthetic and local only.
- Atomic ruleset, reviewer-lifecycle, review-packet, and rehearsal controls are validated only in isolated local infrastructure.
- No real patient data may be processed.
- The existing hosted Janani Supabase project has not been modified.
- No dedicated hosted staging project or paid Supabase branch exists; validation currently uses isolated local Docker infrastructure.
- No Gemini adapter or hosted LLM is connected.
- No hosted-model response schema or output-policy validator is implemented yet.
- No OCR engine or extraction worker process is implemented; only the worker-only persistence RPC and confirmation controls exist.
- No approved clinical-content ingestion, embeddings, or RAG retrieval is implemented.
- The deletion-request workflow does not yet include the controlled deletion worker, storage cleanup, session revocation, or retention-policy execution.
- No caregiver sharing or permissions model is implemented.
- The service is not deployable for clinical use.

## Next milestone: 29–30% — real clinical authorisation and hosted staging gate

- Approve reviewer-onboarding, conflict-of-interest, credential-verification, evidence-retention, and governance operating procedures.
- Verify real obstetrician, clinical-safety, and Telugu-language reviewer credentials outside source control.
- Replace every development placeholder with current clinician-reviewed sources and exact sections.
- Obtain actual human review and approval of every predicate, severity, rationale, and applicability boundary.
- Obtain qualified clinical and language approval of English and Telugu escalation wording.
- Obtain independently authored and independently reviewed expected outcomes beyond the implementation team.
- Rehearse incident ownership, reviewer deactivation, release retirement, and emergency rollback under approved operating procedures.
- Repeat the governance, reviewer, review-packet, release, atomic-ruleset, and rehearsal workflow in isolated hosted staging using synthetic data only.
- Document production access control, incident ownership, privacy, legal, security, and clinical launch sign-off.
- Keep every rule inactive until every real-world authorization, hosted test, and launch gate passes.

## Revised roadmap allocation

- 0–4%: governance and source of truth
- 4–10%: engineering foundation
- 10–18%: database, authentication, consent, privacy, and RLS
- 18–30%: clinician-approved deterministic safety engine
- 30–39%: structured pregnancy services and attachment records
- 39–48%: attachment extraction, confirmation, task routing, and Context Assembly Engine
- 48–57%: clinical content management and RAG retrieval
- 57–65%: typed LLM contracts, Gemini adapter, and provider orchestration
- 65–71%: output validation, citations, audit, English, and Telugu
- 71–84%: twelve core capabilities and partner mode
- 84–90%: specialised extraction, ranking, and intent ML pipelines
- 90–94%: shadow-mode evaluation
- 94–97%: observability, security, reliability, and load testing
- 97–99%: controlled clinical pilot
- 99–100%: production-readiness gate

## Change log

### 2026-08-07 — 29%

Built and verified pre-clinical review packets, expanded safety challenge datasets, immutable review/rehearsal evidence, and synthetic emergency rollback rehearsal on `phase-7/clinical-review-rehearsal`. The validation dataset now contains 63 cases across nine categories per development rule. Review packets bind exact candidate and dataset digests and remain non-eligible while placeholder sources exist. The rollback rehearsal proves exact prior ruleset restoration and persists only fully passing, evidenced synthetic rehearsals. Local validation discovered PostgreSQL `42702` from an ambiguous `value` reference; the query was fixed with explicit aliases and the persistence gate was hardened. GitHub Actions passed on `de9b594`: 63 safety tests with 95.43% coverage, 168 full-suite tests, 14 expected staging skips, Docker build, all migrations rebuilt from zero, and 14/14 local integration tests. No real clinician, patient data, clinical approval, hosted project change, or hosted LLM was introduced.

### 2026-08-05 — 27%

Built and verified controlled reviewer administration and executable safety validation datasets on `phase-6/reviewer-admin-validation-datasets`. Added trusted `app_metadata` authorization, disabled-by-default backend administration routes, service-role-only reviewer lifecycle RPCs, conflict-of-interest and evidence-reference controls, immutable reviewer identity, active-release deactivation protection, append-only lifecycle events, and 35 synthetic true-positive, true-negative, boundary, interaction, and regression cases. GitHub Actions passed on `dcda56f`: 49 safety tests with 96.33% coverage, 149 full-suite tests, 13 expected staging skips, Docker build, all migrations rebuilt from zero, and 13/13 local integration tests. No real clinician, credential, patient data, source approval, or hosted project was introduced.

### 2026-08-04 — 25%

Built and verified atomic deterministic safety rulesets on `phase-5/atomic-ruleset-activation`. Added complete required-rule manifests, immutable SHA-256 member binding, private ruleset persistence, service-role-only approval/activation/rollback, active-release drift detection, transactional exact-active-set checks, PostgREST contract validation, and two-generation activation/replacement/rollback testing. GitHub Actions passed on `59c7c10`: 34 safety tests with 97.44% coverage, 94 full-suite tests, 12 expected staging skips, Docker build, all migrations rebuilt from zero, and 12/12 local integration tests. No current warning rule became clinically approved or usable with real patient data.

### 2026-08-04 — 22%

Built and verified the clinical safety governance foundation on `phase-4/clinical-safety-governance`. Added exact-content review candidates, reviewer credentials and roles, source expiry and placeholder controls, gestational applicability, dual obstetrician and clinical-safety approval, release activation/retirement/rollback, immutable audit history, service-role-only Supabase governance, and local end-to-end governance validation. All seven existing warning rules remain development-only and unapprovable. GitHub Actions passed on `148565f`: 27 safety tests with 96.87% coverage, 80 full-suite tests, 10 expected staging skips, Docker build, all eight migrations rebuilt from zero, and 10/10 local integration tests.

### 2026-08-04 — 18%

Completed the free authenticated-persistence validation gate without creating a paid Supabase branch or changing the hosted Janani project. Added an isolated local Supabase Docker stack, full migration reset, ephemeral synthetic-user provisioning, worker-only extraction RPC, and a permanent CI isolation job. GitHub Actions passed on `5b4210a`: the normal quality pipeline was green and all 9 local RLS, RPC, extraction, deletion, and private-Storage tests passed.

### 2026-08-04 — 17%

Built and verified the authenticated persistence foundation on `phase-3/authenticated-persistence`. Added Supabase token verification, RLS-scoped record loading, authenticated stored-context assembly, privacy-minimised audit RPCs, attachment state transitions, deletion-request foundations, migration hardening, and an opt-in two-user staging harness. GitHub Actions passed on implementation commit `60c4406`: Ruff lint, Ruff formatting, 12 safety tests with 92.50% safety coverage, 60 full-suite tests, one intentionally skipped staging integration test, and the Docker build.

### 2026-08-04 — 14%

Built the first working data, consent, attachment, and Context Assembly Engine layer on `phase-2/data-context-foundation`. The system can transform synthetic structured records into one minimal provider-neutral LLM request while enforcing deterministic safety blocking, consent, task relevance, confirmation status, approved-content status, context budgets, and privacy-minimised auditing. GitHub Actions passed on implementation commit `8686255`: Ruff lint, Ruff formatting, 12 safety tests with 92.50% safety coverage, 40 full-suite tests, and the Docker build.

### 2026-08-04 — 10%

Completed the free-first engineering foundation and revised Janani's architecture around controlled context assembly. GitHub Actions passed on commit `5c283d5`: Ruff lint, Ruff formatting, the safety coverage gate, the full test suite, and the Docker build.

### 2026-08-04 — Architecture path revised

Changed the planned AI path. Janani will assemble a minimal, relevant, verified context package from structured records and attachments, add approved clinical knowledge, and send one typed request through a provider-independent adapter. Gemini 3.5 Flash is the first planned hosted model for synthetic development; the unpaid path cannot process real health data. Added ADR 0002 and a detailed Context Assembly and Hosted LLM Flow document.

### 2026-08-03 — 8%

Corrected FastAPI dependency-injection linting and test formatting. GitHub Actions completed successfully: Ruff lint, Ruff format, the safety coverage gate, the full test suite, and the Docker build all passed.

### 2026-08-03 — 7%

Created the free-first production foundation. Added a FastAPI service, deterministic safety-engine scaffold, draft development rules, mock LLM provider, tests, CI, Docker, Supabase migration, and documentation. Real patient use remains explicitly blocked.