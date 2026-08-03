# Context Assembly and Hosted LLM Flow

## Purpose

This document defines how Janani converts structured user records and attachments into one safe, relevant, typed request for a hosted language model.

## End-to-end flow

```text
1. User initiates a task
2. Authentication and consent are verified
3. Structured request is validated
4. Deterministic safety engine evaluates relevant inputs
5. Task router identifies the requested capability
6. Context policy identifies required and optional data categories
7. Confirmed records are retrieved
8. Relevant attachments are processed and selected
9. Unnecessary identifiers and unrelated history are removed
10. Approved clinical knowledge is retrieved
11. Token budget and recency rules are applied
12. JananiLLMRequest is created
13. Provider adapter calls Gemini or a mock provider
14. JananiLLMResponse is parsed and validated
15. Policy, citation, and safety checks run
16. Audit event is recorded
17. UI-facing response is delivered
```

## Context Assembly Engine responsibilities

The Context Assembly Engine must:

- accept a typed task and user identifier;
- apply task-specific inclusion policies;
- use only records the user is permitted to access;
- distinguish entered, extracted, user-confirmed, clinician-confirmed, and inferred data;
- prefer current and clinically relevant records;
- exclude unrelated data by default;
- include attachment text only when relevant;
- remove identity fields not required for the task;
- attach approved knowledge separately from user facts;
- preserve source and record identifiers for audit and citations;
- enforce maximum token and attachment budgets;
- produce deterministic assembly metadata that can be tested.

## Data-confidence levels

Every fact included in a request should carry a confidence/provenance class:

- `user_entered`
- `user_confirmed_extraction`
- `clinician_entered`
- `clinician_confirmed`
- `system_calculated`
- `unconfirmed_extraction`

`unconfirmed_extraction` must not be represented to the hosted model as established medical fact. For prescriptions and key report values, user or clinician confirmation is mandatory before persistence as a confirmed record.

## Proposed request contract

```json
{
  "request_id": "uuid",
  "task": "appointment_preparation",
  "language": "en",
  "synthetic": true,
  "user_question": "What should I ask at tomorrow's appointment?",
  "pregnancy_context": {
    "gestational_week": 24,
    "trimester": 2,
    "known_conditions": ["synthetic-condition"]
  },
  "relevant_records": [],
  "attachments": [
    {
      "attachment_id": "uuid",
      "type": "lab_report",
      "selected_text": "Synthetic confirmed report text",
      "confirmation_status": "user_confirmed_extraction"
    }
  ],
  "approved_knowledge": [
    {
      "content_id": "content-version-id",
      "source_title": "Approved test source",
      "text": "Approved synthetic context"
    }
  ],
  "response_policy": {
    "diagnosis_forbidden": true,
    "medication_changes_forbidden": true,
    "must_cite_sources": true,
    "tone": "warm_clear_respectful"
  },
  "budget": {
    "maximum_input_tokens": 12000,
    "maximum_attachments": 3
  }
}
```

The exact schemas will be implemented with Pydantic and versioned.

## Proposed response contract

```json
{
  "message": "Plain-language response",
  "response_type": "appointment_preparation",
  "language": "en",
  "summary": "Synthetic summary",
  "suggested_questions": [],
  "source_citations": [],
  "requires_clinician_contact": false,
  "contains_diagnosis": false,
  "contains_medication_change": false,
  "limitations": [],
  "provider": "gemini",
  "model": "configured-stable-model"
}
```

No provider response is returned directly to the mobile client. Janani parses it, validates it, and either approves it or returns a safe fallback.

## Task-specific context policies

### Appointment preparation

Include:

- gestational stage;
- recent confirmed symptoms and vitals;
- active entered prescriptions and adherence summaries;
- recent confirmed report extracts;
- unresolved actions from previous appointments;
- relevant approved knowledge.

Exclude:

- unrelated journal entries;
- old resolved symptoms outside the configured recency window;
- partner activity not required for the task;
- unnecessary identity and contact information.

### Report explanation

Include:

- report type and date;
- confirmed extracted text and values;
- relevant previous results;
- gestational stage and directly applicable conditions;
- approved explanation sources.

Exclude:

- unrelated records;
- interpretation of raw ultrasound images;
- uncertain OCR values represented as facts.

### Nutrition guidance

Include:

- gestational stage;
- confirmed height/weight context;
- dietary preference and regional preferences;
- allergies;
- relevant conditions;
- clinician-entered restrictions;
- approved nutrition knowledge.

Exclude:

- unrelated appointments and attachments;
- medication changes;
- unsupported calorie or therapeutic targets.

### Medication reminder explanation

Include only:

- medication name, dose text, schedule, and duration entered or confirmed from a prescription;
- reminder status;
- approved general medication-adherence information.

The hosted model cannot originate, stop, replace, or alter a medication.

## Attachment rules

- Keep originals in private storage.
- Use signed, time-limited access only where needed.
- Validate MIME type, size, and malware risk.
- Prefer native PDF text before OCR.
- Record extraction engine and confidence.
- Confirm critical values before they become health records.
- Send selected relevant text rather than the full file when practical.
- Do not send identity pages, addresses, phone numbers, barcodes, or unrelated sections.
- Do not send attachments to an unpaid hosted model when they contain real user information.

## Gemini integration boundary

The planned first external adapter targets the stable model configuration `gemini-3.5-flash`.

During free development:

- synthetic data only;
- fake attachments only;
- API key in backend secrets only;
- no mobile-to-provider direct calls;
- mock provider remains the default for tests;
- Gemini integration tests are opt-in and must not run with repository secrets on untrusted pull requests.

## Evaluation requirements

Before real-user use, test:

- whether the correct records were included;
- whether unrelated records were excluded;
- whether identity minimisation worked;
- whether attachment text was confirmed;
- whether token budgets were respected;
- whether approved sources were retrieved;
- whether output contains unsupported claims;
- whether diagnosis and medication restrictions were preserved;
- whether citations correspond to supplied knowledge;
- whether the same request behaves acceptably across provider/model versions.
