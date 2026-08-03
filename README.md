# Janani AI

Janani AI is the clinical-support intelligence layer for the Janani pregnancy application. It supports women from preconception through delivery with personalised education, reminders, record summaries, report explanations, and clinician-approved warning-sign escalation.

## Safety position

Janani AI is not a doctor. It must not diagnose, prescribe, change medication doses, declare symptoms safe without assessment, replace antenatal care, or override an escalation produced by the deterministic safety engine.

## Free-first development policy

The current phase uses only free/local components:

- Python and FastAPI
- deterministic safety rules
- a mock LLM provider for synthetic tests
- local Docker and GitHub Actions
- Supabase-compatible migrations without requiring a paid plan

Real patient data is prohibited during this phase. Paid hosted models will only be evaluated after the safety, retrieval, privacy, and audit foundations are working.

## Current milestone

`phase-0-1/foundation` establishes:

1. a typed FastAPI service and health endpoints;
2. deterministic safety-engine interfaces;
3. draft development rules that production mode cannot activate;
4. provider-independent LLM interfaces with a mock implementation;
5. automated tests, linting, Docker, CI, and progress tracking.

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
