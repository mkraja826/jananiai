# Janani AI Roadmap

## Critical build order

1. Governance and safety boundaries.
2. Engineering foundation.
3. Database, consent, privacy, and RLS.
4. Clinician-approved deterministic safety engine.
5. Structured pregnancy services.
6. Clinically reviewed content management.
7. RAG ingestion, retrieval, and evaluation.
8. Provider-independent LLM orchestration.
9. English and Telugu validation.
10. Complete Janani product capabilities.
11. Specialised ML pipelines and model registry.
12. Shadow-mode evaluation.
13. Security, observability, and load testing.
14. Controlled clinical pilot.
15. Production-readiness review.

## Free-first gate

Until the foundation is validated:

- use only synthetic data;
- use the mock LLM adapter;
- do not ingest unlicensed textbooks;
- do not deploy draft safety rules to real users;
- do not connect the mobile application to clinical AI endpoints;
- do not claim diagnosis, medical-device functionality, or clinical readiness.

## First working milestone

A synthetic structured symptom request enters FastAPI, is validated, passes through the deterministic rules engine, returns a draft escalation or non-escalation result, and produces a typed response without an LLM call.

## Second working milestone

A routine synthetic educational question retrieves only active, approved, correctly tagged content and returns traceable citations without generating a medical conclusion.

## Third working milestone

A hosted or local language provider converts retrieved content into a validated English or Telugu response without unsupported medical claims.
