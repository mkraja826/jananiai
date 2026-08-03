# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 22%

Updated: 2026-08-04
Branch: `phase-4/clinical-safety-governance`
Latest verified implementation commit: `148565f`
Draft PR: `#4`

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

## Current limitations

- No licensed clinician identity or credential has been entered into Janani AI.
- No warning rule has been reviewed or approved by a licensed clinician.
- Every current safety candidate contains development-placeholder provenance and cannot be activated.
- Current English and Telugu escalation wording remains development-only and not clinically approved.
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

## Next milestone: 22–30% — clinically reviewed deterministic safety rules

- Establish the authorised reviewer onboarding and conflict-of-interest policy.
- Verify real obstetrician and clinical-safety reviewer credentials outside source control.
- Replace development placeholders with current clinician-reviewed sources and exact sections.
- Document rationale and applicability boundaries for each warning rule.
- Review English and Telugu escalation wording with clinical and language reviewers.
- Add true-positive, false-positive, boundary, interaction, and regression datasets for each candidate.
- Add ruleset-level release composition, atomic activation, and rollback tests.
- Add controlled administration APIs that never expose the service-role key to mobile clients.
- Repeat governance validation in an isolated hosted staging environment before any real-user path.
- Keep every rule inactive until all required reviews, tests, and launch gates pass.

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
