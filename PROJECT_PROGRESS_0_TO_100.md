# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 17%

Updated: 2026-08-04
Branch: `phase-3/authenticated-persistence`
Latest verified implementation commit: `60c4406`
Draft PR: `#3`

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

## Phase 3 authenticated persistence foundation completed and verified

- [x] Added Supabase bearer-token verification through the Auth user endpoint.
- [x] Added verified request identity with bearer tokens excluded from serialization and logs.
- [x] Made authentication and Supabase configuration mandatory in staging and production.
- [x] Added an RLS-scoped PostgREST client using the verified caller token and publishable key.
- [x] Added server-side loading for profiles, active pregnancy, consent history, medications, appointments, attachments, and extraction versions.
- [x] Added `POST /v1/context/assemble-stored`; clients no longer need to send their complete health history for this path.
- [x] Added identity matching between the verified user and repository client.
- [x] Added authenticated database RPC foundations for minimal safety and context audit writes.
- [x] Kept questions, symptom notes, extracted report text, prompts, and model outputs out of audit RPC payloads.
- [x] Added attachment extraction state transitions: start, process, complete/fail, confirm/reject.
- [x] Added authenticated attachment-confirmation RPC foundation.
- [x] Added account-deletion request table, RPC, model, and protected endpoint.
- [x] Added explicit grants and revokes for user-owned and internal tables.
- [x] Added owner-read policy for safety audit events.
- [x] Added an opt-in two-user synthetic Supabase RLS staging test harness.
- [x] Added architecture documentation for authenticated persistence.
- [x] GitHub Actions passed on `60c4406`: Ruff lint, Ruff formatting, 12 safety tests, 92.50% safety coverage, 60 full-suite tests, one intentionally skipped staging test, and Docker build.

## Current limitations

- Draft warning rules have not been reviewed or approved by a licensed clinician.
- No real patient data may be processed.
- The new migrations have not been executed against an isolated Supabase staging environment.
- The two-user RLS test is implemented but has not run against live synthetic staging credentials.
- The existing Janani Supabase project has not been modified by this phase.
- No dedicated Supabase development branch or separate staging project has been provisioned.
- No Gemini adapter or hosted LLM is connected.
- No hosted-model response schema or output-policy validator is implemented yet.
- No OCR or extraction worker is implemented; only the state machine and confirmation controls exist.
- No approved clinical-content ingestion, embeddings, or RAG retrieval is implemented.
- The deletion-request workflow does not yet include the controlled deletion worker, storage cleanup, session revocation, or retention-policy execution.
- No caregiver sharing or permissions model is implemented.
- The service is not deployable for clinical use.

## Final gate to 18% — isolated Supabase staging validation

- Provision or approve an isolated synthetic Supabase staging project or development branch.
- Apply all Janani AI migrations in order to that isolated environment.
- Create two synthetic authenticated users only.
- Run the two-user RLS test across every user-owned table and private storage path.
- Verify append-only consent and consent revocation behavior.
- Verify that direct writes to extraction and audit tables are denied.
- Verify authenticated audit, attachment-confirmation, and deletion-request RPCs.
- Run Supabase database security and performance advisors and resolve relevant findings.
- Keep the existing Janani project and all real data untouched until this gate passes.

## Following milestone: 18–30% — clinician-approved deterministic safety engine

- Establish the clinician review and dual-approval workflow.
- Convert draft warning rules into versioned review candidates.
- Add rule provenance, applicability boundaries, expiry, and rollback.
- Expand true-positive, false-positive, boundary, and interaction tests.
- Keep all rules inactive for real users until clinician sign-off and staging validation are complete.

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

### 2026-08-04 — 17%

Built and verified the authenticated persistence foundation on `phase-3/authenticated-persistence`. Added Supabase token verification, RLS-scoped record loading, authenticated stored-context assembly, privacy-minimised audit RPCs, attachment state transitions, deletion-request foundations, migration hardening, and an opt-in two-user staging harness. GitHub Actions passed on implementation commit `60c4406`: Ruff lint, Ruff formatting, 12 safety tests with 92.50% safety coverage, 60 full-suite tests, one intentionally skipped staging integration test, and the Docker build. The remaining gate to 18% is execution against an isolated synthetic Supabase environment.

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
