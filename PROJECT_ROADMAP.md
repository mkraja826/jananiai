# Janani AI Roadmap

## Updated product architecture

Janani AI will not initially train or host a complete language model. Janani's own intelligence will be the controlled orchestration layer that collects, validates, selects, and assembles relevant user information before calling a hosted language model.

The first hosted provider planned for synthetic development is Google Gemini through a provider-independent adapter, using the stable model identifier `gemini-3.5-flash`.

```text
Janani mobile application
        |
        | structured data, confirmed records, user request, attachments
        v
FastAPI backend
        |
        +-- authentication, consent, and access checks
        +-- deterministic safety engine (always first)
        +-- intent/task router
        +-- attachment extraction and user confirmation
        +-- Janani Context Assembly Engine
        |      +-- select only relevant confirmed data
        |      +-- remove unnecessary identity fields
        |      +-- retrieve approved clinical knowledge
        |      +-- preserve attachment/source references
        |      +-- enforce task-specific token budget
        |
        +-- one typed Janani LLM request
        v
Provider-independent LLM adapter
        |
        +-- development target: Gemini 3.5 Flash
        +-- future alternatives: Claude, OpenAI, Grok, or another approved provider
        v
Structured LLM response
        |
        +-- Pydantic schema validation
        +-- diagnosis/medication/policy checks
        +-- citation and support verification
        +-- audit event
        v
Safe UI response returned to the Janani application
```

## Core design decision

Janani must never send the user's complete history automatically. The Context Assembly Engine selects the minimum relevant information required for the current task.

Examples:

- Nutrition request: pregnancy stage, confirmed height/weight context, dietary preference, allergies, relevant conditions, clinician restrictions, and approved nutrition sources.
- Appointment preparation: current pregnancy summary, recent confirmed symptoms, active entered prescriptions, recent reports, and previous appointment actions.
- Report explanation: report date/type, user-confirmed extracted text, relevant previous values, pregnancy stage, and approved explanation content.
- Medication reminder: only the prescription and schedule entered or confirmed by the user/clinician; the LLM cannot originate or alter medication instructions.

## Attachment policy

Attachments are not blindly forwarded.

```text
Upload
  -> malware/type/size checks
  -> private storage
  -> text/OCR extraction
  -> confidence and field validation
  -> user confirmation where needed
  -> relevant section selection
  -> identity minimisation
  -> attachment reference or selected text included in the LLM request
```

Initial scope:

- text-based PDF reports;
- prescription images with mandatory user confirmation;
- laboratory-report images/PDFs;
- written ultrasound-report text.

Autonomous ultrasound-image diagnosis is excluded.

## Hosted model plan

### Free development phase

- Keep the current deterministic mock provider for automated tests and local development.
- Add a Gemini adapter only after the context-request schema and policy tests exist.
- Use Gemini's unpaid quota only with synthetic profiles, synthetic reports, and fake attachments.
- Never send real names, phone numbers, prescriptions, reports, scans, or health histories through unpaid services.
- Store the API key only in backend environment/secrets; never in the mobile application or repository.

### Paid/private-data phase

Before processing real user health data:

- activate an approved paid service and complete vendor/privacy review;
- verify contractual and regional availability;
- document retention and logging controls;
- establish consent, RLS, deletion, audit, incident-response, and key-rotation controls;
- run Janani's clinical, privacy, red-team, and retrieval evaluation gates.

### Model routing later

- `gemini-3.5-flash`: primary complex context summarisation and explanations.
- lower-cost model: classification, extraction, translation, and simple high-volume tasks after evaluation.
- secondary verifier/fallback provider: added only after the primary path is stable and measurable.

Model identifiers remain configuration values rather than hardcoded business logic.

## Revised critical build order

1. Governance, intended use, and safety boundaries.
2. Engineering foundation and permanent progress tracking.
3. Database, authentication, consent, privacy, and RLS.
4. Clinician-approved deterministic safety engine.
5. Structured pregnancy, medication, appointment, symptom, and report services.
6. Attachment ingestion, extraction, confirmation, and private-storage pipeline.
7. Intent/task router and relevance rules.
8. Janani Context Assembly Engine with privacy minimisation and token budgeting.
9. Clinically reviewed content management and RAG retrieval.
10. Typed `JananiLLMRequest` and `JananiLLMResponse` contracts.
11. Gemini 3.5 Flash adapter for synthetic development.
12. Output policy validation, citation checks, and audit trail.
13. English and Telugu localisation and clinical-language review.
14. Complete Janani product capabilities and partner mode.
15. Specialised ML pipelines only where they improve context selection, extraction, or ranking.
16. Security, observability, load tests, red-team tests, controlled pilot, and production gate.

## Free-first gate

Until the foundation and context assembly path are validated:

- use only synthetic data and fake attachments;
- keep the mock LLM as the default provider;
- do not ingest unlicensed textbooks;
- do not deploy draft safety rules to real users;
- do not send data directly from the mobile app to Gemini;
- do not include all user history by default;
- do not allow uncertain OCR text to become a confirmed health record;
- do not claim diagnosis, medical-device functionality, or clinical readiness.

## Milestone 1 — Deterministic safety path

A synthetic structured symptom request enters FastAPI, is validated, passes through the deterministic rules engine, returns a draft escalation or non-escalation result, and creates a privacy-minimised audit event without an LLM call.

## Milestone 2 — Context assembly without hosted AI

Given a synthetic task, the Context Assembly Engine selects only relevant confirmed records, excludes unrelated/private fields, links relevant fake attachments, retrieves approved test content, and produces a typed `JananiLLMRequest` within a token budget.

## Milestone 3 — Gemini synthetic integration

The Gemini adapter sends the typed synthetic request to `gemini-3.5-flash`, requests structured output, validates the result with Pydantic and policy checks, and returns a safe response. No real user data is permitted.

## Milestone 4 — End-to-end user workflow

The Janani app submits a user task, the backend performs safety and relevance selection, attachments are confirmed, the approved context is assembled, the hosted model generates a structured response, Janani validates it, and the final answer is delivered with sources and limitations.

## Definition of Janani's own AI

Janani's defensible intelligence is:

```text
structured pregnancy data
+ deterministic clinical safety
+ attachment processing and confirmation
+ task classification
+ relevance and context selection
+ approved clinical knowledge retrieval
+ privacy minimisation
+ provider-independent request construction
+ structured response validation
+ longitudinal feedback and evaluation
```

The hosted LLM supplies language understanding, summarisation, explanation, and generation. It does not own Janani's clinical rules, data permissions, medication policy, or final response approval.
