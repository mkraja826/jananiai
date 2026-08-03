# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current progress: 7%

Updated: 2026-08-03
Branch: `phase-0-1/foundation`

## Completed

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

## Current limitations

- Draft warning rules have not been reviewed or approved by a licensed clinician.
- No real patient data may be processed.
- No hosted LLM is connected.
- No RAG or clinical knowledge ingestion is implemented.
- No authentication, consent workflow, or complete RLS model is implemented.
- The service is not deployable for clinical use.

## Next milestone: 10%

- Run CI and fix all lint/test failures.
- Add request-level audit event persistence interface.
- Add clinical rule sign-off workflow models.
- Add explicit production startup guard when no approved ruleset exists.
- Add architecture and threat-model documentation.

## Roadmap allocation

- 0–4%: governance and source of truth
- 4–10%: engineering foundation
- 10–19%: database, privacy, consent, and RLS
- 19–32%: clinician-approved deterministic safety engine
- 32–40%: structured pregnancy services
- 40–48%: clinical content management
- 48–57%: RAG ingestion and retrieval
- 57–66%: LLM orchestration
- 66–71%: English and Telugu localisation
- 71–84%: twelve core capabilities
- 84–90%: specialised ML pipelines
- 90–94%: shadow-mode evaluation
- 94–97%: observability, security, and reliability
- 97–99%: controlled clinical pilot
- 99–100%: production-readiness gate

## Change log

### 2026-08-03 — 7%

Created the free-first production foundation. Added a FastAPI service, deterministic safety-engine scaffold, draft development rules, mock LLM provider, tests, CI, Docker, Supabase migration, and documentation. Real patient use remains explicitly blocked.
