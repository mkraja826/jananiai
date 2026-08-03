# ADR 0001: Free-first, provider-independent AI foundation

Status: Accepted
Date: 2026-08-03

## Context

Janani AI needs to establish safety, privacy, auditability, and retrieval quality before spending money on hosted language models or processing real patient information.

## Decision

- Build the backend in Python 3.12 and FastAPI.
- Use deterministic code as the safety authority.
- Use a provider protocol rather than hardcoding any LLM vendor.
- Permit only the deterministic mock provider during free-first mode.
- Permit only synthetic data during free-first mode.
- Keep draft safety rules inactive in production mode until clinician sign-off exists.
- Add Supabase-compatible migrations while retaining local testability.

## Consequences

Positive:

- no model API cost during foundation work;
- safer development and simpler tests;
- no vendor lock-in;
- paid providers can be compared later using the same evaluation set.

Negative:

- generated conversational quality cannot be evaluated yet;
- real clinical workflows remain blocked;
- clinician review and content licensing remain external dependencies.
