# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 8%

Updated: 2026-08-04
Branch: `phase-0-1/foundation`
Latest fully verified commit: `8c78ccc`
Draft PR: `#1`

## Completed and verified through `8c78ccc`

- [x] Repository initialised.
- [x] Mission and safety boundaries documented.
- [x] Free-first development policy established.
- [x] Python/FastAPI project foundation created.
- [x] Typed health, readiness, and safety-evaluation API contracts created.
- [x] Deterministic safety-engine core created.
- [x] Draft synthetic-test warning rules created.
- [x] Production mode blocks unapproved rules.
- [x] Provider-independent LLM interface created.
- [x] Mock LLM provider created; no paid API required.
- [x] Pytest, Ruff, Docker, and GitHub Actions foundations created.
- [x] Initial Supabase migration for rule versions and audit events created.
- [x] CI lint failures identified and corrected.
- [x] Ruff lint and formatting checks passed.
- [x] Safety-module coverage gate of at least 90% passed.
- [x] Full automated test suite passed.
- [x] Production-style Docker image build passed.

## Architecture direction accepted on 2026-08-04

- [x] Janani's core intelligence redefined as a Context Assembly Engine rather than a newly trained general-purpose LLM.
- [x] User data will be selected by task; the full history will not be sent by default.
- [x] Attachments will be privately stored, extracted, confidence-checked, and confirmed before relevant content is included.
- [x] One typed request will combine the current task, relevant confirmed records, selected attachment text/references, approved RAG knowledge, response policy, and token budget.
- [x] The first planned hosted provider is Gemini through the provider-independent adapter.
- [x] Synthetic integration target recorded as stable model configuration `gemini-3.5-flash`.
- [x] Mock provider remains the default for automated and local tests.
- [x] Unpaid hosted-model use remains synthetic-data-only.
- [x] Provider outputs must pass Pydantic, policy, citation, and audit validation before reaching users.
- [x] Updated roadmap, ADR, architecture flow, and README committed.

## Changes added after the latest fully verified commit

The branch also contains foundation-hardening work that requires a fresh complete CI pass before progress is advanced:

- privacy-minimised in-memory safety audit recorder and API wiring;
- stricter clinician approval metadata and review deadlines;
- production startup blocking without a current approved ruleset;
- configuration, mock-provider, audit, and startup tests;
- foundation threat model;
- Context Assembly Engine and Gemini-first architecture documentation.

Do not describe these post-`8c78ccc` changes as verified until CI completes successfully on the latest branch head.

## Current limitations

- Draft warning rules have not been reviewed or approved by a licensed clinician.
- No real patient data may be processed.
- No Gemini adapter or hosted LLM is connected yet.
- No Context Assembly Engine is implemented yet.
- No attachment extraction/confirmation pipeline is implemented.
- No RAG or clinical knowledge ingestion is implemented.
- No authentication, consent workflow, or complete user/caregiver RLS model is implemented.
- The service is not deployable for clinical use.

## Next milestone: verified 10%

- Run full CI on the latest branch head and fix failures.
- Complete request-level audit persistence interfaces.
- Finalise production startup and expired-rule tests.
- Define versioned `JananiLLMRequest` and `JananiLLMResponse` Pydantic schemas.
- Define task-specific context policies and relevance tests.
- Define attachment metadata, extraction-confidence, and confirmation-state schemas.
- Add a deterministic Context Assembly Engine skeleton using synthetic records.
- Keep Gemini integration behind a later explicit synthetic-data gate.

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

### 2026-08-04 — Architecture path revised

Changed the planned AI path. Janani will assemble a minimal, relevant, verified context package from structured records and attachments, add approved clinical knowledge, and send one typed request through a provider-independent adapter. Gemini 3.5 Flash is the first planned hosted model for synthetic development; the free/unpaid path cannot process real health data. Added ADR 0002 and a detailed Context Assembly and Hosted LLM Flow document. Verified progress remains 8% until the latest branch head passes complete CI.

### 2026-08-03 — 8%

Corrected FastAPI dependency-injection linting and test formatting. GitHub Actions completed successfully: Ruff lint, Ruff format, the safety coverage gate, the full test suite, and the Docker build all passed.

### 2026-08-03 — 7%

Created the free-first production foundation. Added a FastAPI service, deterministic safety-engine scaffold, draft development rules, mock LLM provider, tests, CI, Docker, Supabase migration, and documentation. Real patient use remains explicitly blocked.
