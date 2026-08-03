# Janani AI

Janani AI is the clinical-support intelligence layer for the Janani pregnancy application. It supports women from preconception through delivery with personalised education, reminders, record summaries, report explanations, and clinician-approved warning-sign escalation.

## Safety position

Janani AI is not a doctor. It must not diagnose, prescribe, change medication doses, declare symptoms safe without assessment, replace antenatal care, or override an escalation produced by the deterministic safety engine.

## Updated operating model

Janani will not initially train a complete language model. Janani's own intelligence is the controlled orchestration layer that:

1. receives structured user records, a user task, and attachment references;
2. validates authentication, consent, and data provenance;
3. runs the deterministic safety engine first;
4. selects only the relevant confirmed information for the task;
5. processes and confirms attachment text where required;
6. retrieves approved clinical knowledge;
7. removes unnecessary identity information and unrelated history;
8. assembles one typed request for a hosted language model;
9. validates the hosted model's structured response before delivery.

```text
Janani app
   -> FastAPI
   -> safety engine
   -> attachment processing
   -> Context Assembly Engine
   -> approved RAG knowledge
   -> provider adapter
   -> structured response validation
   -> Janani app
```

The mobile application never calls a hosted model directly and never contains the provider API key.

## Hosted model path

The first planned external provider is Google Gemini through the provider-independent adapter.

- Primary synthetic-development target: `gemini-3.5-flash`
- Automated/local tests: deterministic mock provider
- Future alternatives: Claude, OpenAI, Grok, or another approved provider

Gemini is the first adapter, not a permanent vendor lock-in.

## Free-first development policy

The current phase uses only free/local components by default:

- Python and FastAPI
- deterministic safety rules
- a mock LLM provider for synthetic tests
- local Docker and GitHub Actions
- Supabase-compatible migrations without requiring a paid plan

Gemini's unpaid quota may be added for opt-in integration testing only with synthetic profiles, synthetic reports, and fake attachments. Real names, phone numbers, reports, scans, prescriptions, and health histories must not be sent through unpaid hosted-model services.

Before Janani processes real user health data, the project must move through the paid/private-data gate with vendor review, consent, RLS, deletion, audit, incident-response, clinical evaluation, and security controls.

## Current milestone

`phase-0-1/foundation` establishes:

1. a typed FastAPI service and health endpoints;
2. deterministic safety-engine interfaces;
3. draft development rules that production mode cannot activate;
4. provider-independent LLM interfaces with a mock implementation;
5. privacy-minimised safety audit primitives;
6. production startup guards for clinician-approved rules;
7. automated tests, linting, Docker, CI, and progress tracking;
8. the revised Context Assembly Engine and Gemini-first architecture plan.

## Next implementation path

1. Complete database, authentication, consent, and RLS foundations.
2. Implement structured pregnancy and report/attachment records.
3. Implement attachment extraction and confirmation states.
4. Build the task router and Context Assembly Engine.
5. Add versioned `JananiLLMRequest` and `JananiLLMResponse` schemas.
6. Add approved clinical RAG retrieval.
7. Implement the Gemini adapter for synthetic development.
8. Add output policy, citation, red-team, and audit validation.

See:

- `PROJECT_ROADMAP.md`
- `docs/adr/0002-context-assembly-gemini-first.md`
- `docs/architecture/CONTEXT_ASSEMBLY_AND_LLM_FLOW.md`

## Local setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the generated OpenAPI interface.

## Clinical readiness

The service is **not clinically ready**. Draft rules and placeholder escalation wording require licensed-clinician review and sign-off before any real-user deployment.
