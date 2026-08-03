# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 14%

Updated: 2026-08-04
Branch: `phase-2/data-context-foundation`
Latest verified implementation commit: `8686255`
Draft PR: `#2`

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
- [x] GitHub Actions passed on `8686255`: Ruff lint, Ruff formatting, 92.50% safety coverage, 40 tests, and Docker build.

## Current limitations

- Draft warning rules have not been reviewed or approved by a licensed clinician.
- No real patient data may be processed.
- No Gemini adapter or hosted LLM is connected.
- No hosted-model response schema or output-policy validator is implemented yet.
- Supabase migrations have not been executed against a staging project.
- RLS policies have not been integration-tested against authenticated staging users.
- FastAPI does not yet verify Supabase access tokens or propagate authenticated user identity.
- Consent, record, attachment, safety-audit, and context-audit repositories are not durably connected to Supabase.
- No OCR or attachment extraction service is implemented.
- No approved clinical-content ingestion, embeddings, or RAG retrieval is implemented.
- No caregiver sharing or permissions model is implemented.
- The service is not deployable for clinical use.

## Next milestone: 18% — authenticated persistence and staging RLS validation

- Add Supabase access-token verification to FastAPI.
- Propagate authenticated user identity through protected service calls.
- Implement durable repositories for consent, pregnancy, medication, appointments, attachments, and audits.
- Execute migrations against a separate staging Supabase project.
- Add automated two-user isolation tests for every user-owned table and private storage path.
- Validate append-only consent behavior and consent revocation in staging.
- Validate that backend-only extraction and context-audit tables reject direct client writes.
- Add attachment extraction state-transition services without adding OCR yet.
- Add data-retention and account-deletion workflow foundations.
- Keep all fixtures and hosted-service tests synthetic.

## Following milestones

After authenticated persistence and staging isolation are verified:

- complete clinician-reviewed safety-rule workflow;
- build approved clinical content management and RAG retrieval;
- define and validate the structured hosted-model response schema;
- implement the Gemini adapter behind the synthetic-data-only gate;
- add post-generation policy, citation, and safety validation before any response reaches the app.

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

### 2026-08-04 — 14%

Built the first working data, consent, attachment, and Context Assembly Engine layer on `phase-2/data-context-foundation`. The system can now transform synthetic structured records into one minimal provider-neutral LLM request while enforcing deterministic safety blocking, consent, task relevance, confirmation status, approved-content status, context budgets, and privacy-minimised auditing. GitHub Actions passed on implementation commit `8686255`: Ruff lint, Ruff formatting, 12 safety tests with 92.50% safety coverage, 40 full-suite tests, and the Docker build.

### 2026-08-04 — 10%

Completed the free-first engineering foundation and revised Janani's architecture around controlled context assembly. GitHub Actions passed on commit `5c283d5`: Ruff lint, Ruff formatting, the safety coverage gate, the full test suite, and the Docker build.

### 2026-08-04 — Architecture path revised

Changed the planned AI path. Janani will assemble a minimal, relevant, verified context package from structured records and attachments, add approved clinical knowledge, and send one typed request through a provider-independent adapter. Gemini 3.5 Flash is the first planned hosted model for synthetic development; the unpaid path cannot process real health data. Added ADR 0002 and a detailed Context Assembly and Hosted LLM Flow document.

### 2026-08-03 — 8%

Corrected FastAPI dependency-injection linting and test formatting. GitHub Actions completed successfully: Ruff lint, Ruff format, the safety coverage gate, the full test suite, and the Docker build all passed.

### 2026-08-03 — 7%

Created the free-first production foundation. Added a FastAPI service, deterministic safety-engine scaffold, draft development rules, mock LLM provider, tests, CI, Docker, Supabase migration, and documentation. Real patient use remains explicitly blocked.
