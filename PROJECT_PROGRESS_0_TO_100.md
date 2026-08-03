# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 10%

Updated: 2026-08-04
Branch: `phase-0-1/foundation`
Latest verified implementation commit: `5c283d5`
Draft PR: `#1`

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
- [x] Configuration, mock-provider, audit, startup, API, and safety tests created.
- [x] Pytest, Ruff, Docker, and GitHub Actions foundations created.
- [x] Initial Supabase migration for rule versions and audit events created with RLS enabled.
- [x] Foundation architecture, ADRs, threat model, and permanent progress tracker created.
- [x] Full CI passed on `5c283d5`: Ruff lint, Ruff format, safety coverage gate, full tests, and Docker build.

## Architecture direction accepted on 2026-08-04

- [x] Janani's core intelligence is a Context Assembly Engine rather than a newly trained general-purpose LLM.
- [x] User data will be selected according to the current task; complete history will not be sent by default.
- [x] Attachments will be privately stored, extracted, confidence-checked, and confirmed before relevant content is included.
- [x] One typed request will combine the task, relevant confirmed records, selected attachment text/references, approved RAG knowledge, response policy, language, and token budget.
- [x] The first planned hosted provider is Gemini through the provider-independent adapter.
- [x] Synthetic integration target recorded as stable model configuration `gemini-3.5-flash`.
- [x] The deterministic mock provider remains the default for automated and local tests.
- [x] Unpaid hosted-model use remains synthetic-data-only.
- [x] Provider output must pass Pydantic, policy, citation, and audit validation before reaching users.
- [x] Updated roadmap, ADR 0002, architecture flow, README, and draft PR description committed.

## Current limitations

- Draft warning rules have not been reviewed or approved by a licensed clinician.
- No real patient data may be processed.
- No Gemini adapter or hosted LLM is connected yet.
- No Context Assembly Engine is implemented yet.
- No attachment extraction/confirmation pipeline is implemented.
- No approved RAG or clinical knowledge ingestion is implemented.
- No authentication, consent workflow, or complete user/caregiver RLS model is implemented.
- The in-memory audit recorder is development-only; durable database persistence is not implemented.
- The service is not deployable for clinical use.

## Next milestone: 18% — data, consent, privacy, and RLS

- Design authenticated user, pregnancy, caregiver, consent, and deletion schemas.
- Add Supabase migrations with strict row-level security.
- Define consent versions for care, AI processing, model improvement, and research separately.
- Define structured pregnancy, medication, appointment, symptom, report, and attachment records.
- Define attachment metadata, extraction confidence, and confirmation states.
- Add durable privacy-minimised safety audit persistence.
- Add data-retention and deletion workflows.
- Add automated cross-user and caregiver-permission isolation tests.
- Keep all test fixtures synthetic.

## Following milestone: Context Assembly Engine

After the data and access-control layer is stable:

- define versioned `JananiLLMRequest` and `JananiLLMResponse` Pydantic schemas;
- build task-specific context inclusion/exclusion policies;
- implement deterministic relevance selection using synthetic records;
- enforce recency, provenance, attachment, and token budgets;
- add approved RAG content as a separate traceable context block;
- only then implement the Gemini adapter for synthetic integration testing.

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

### 2026-08-04 — 10%

Completed the free-first engineering foundation and revised Janani's architecture around controlled context assembly. GitHub Actions passed on commit `5c283d5`: Ruff lint, Ruff formatting, the safety coverage gate, the full test suite, and the Docker build. The next work begins the database, consent, privacy, and RLS milestone.

### 2026-08-04 — Architecture path revised

Changed the planned AI path. Janani will assemble a minimal, relevant, verified context package from structured records and attachments, add approved clinical knowledge, and send one typed request through a provider-independent adapter. Gemini 3.5 Flash is the first planned hosted model for synthetic development; the unpaid path cannot process real health data. Added ADR 0002 and a detailed Context Assembly and Hosted LLM Flow document.

### 2026-08-03 — 8%

Corrected FastAPI dependency-injection linting and test formatting. GitHub Actions completed successfully: Ruff lint, Ruff format, the safety coverage gate, the full test suite, and the Docker build all passed.

### 2026-08-03 — 7%

Created the free-first production foundation. Added a FastAPI service, deterministic safety-engine scaffold, draft development rules, mock LLM provider, tests, CI, Docker, Supabase migration, and documentation. Real patient use remains explicitly blocked.
