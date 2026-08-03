# Janani AI

Janani AI is the clinical-support intelligence layer for the Janani pregnancy application. It is designed to support women from preconception through delivery with personalised education, reminders, record summaries, report explanations, and clinician-approved warning-sign escalation.

## Safety position

Janani AI is not a doctor and must not diagnose conditions, prescribe treatment, change medication doses, declare symptoms normal without assessment, replace antenatal care, or override an escalation produced by the deterministic safety engine.

The system will be built around four foundations:

1. Deterministic, clinician-approved safety rules.
2. Structured pregnancy and consent data.
3. Retrieval from approved, versioned clinical content.
4. Provider-independent language generation with validated outputs.

## Planned stack

- Python 3.12
- FastAPI
- Pydantic v2
- Pytest
- Ruff
- Supabase Postgres, pgvector, Auth, RLS, and private Storage
- Docker and GitHub Actions
- Hosted LLM through a provider-independent adapter
- scikit-learn for early specialised models
- PyTorch and Hugging Face for later model work

## Current status

Repository initialised. The first engineering milestone is the production foundation and deterministic safety-engine scaffold.
