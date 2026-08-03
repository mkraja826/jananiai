# Data, Consent, Attachment, and Context Foundation

Status: Synthetic development only
Branch: `phase-2/data-context-foundation`

## Purpose

This phase turns Janani's updated AI plan into deterministic backend contracts. Janani does not send the user's complete history to a hosted model. It selects only confirmed, task-relevant records and produces one provider-neutral `JananiLLMRequest`.

No hosted model is called in this phase.

## Request path

```text
Synthetic ContextAssemblyInput
        |
        v
Structured Pydantic validation
        |
        v
Deterministic safety engine
        |-- escalation/block --> no LLM request
        |
        v
Consent snapshot evaluation
        |-- missing/revoked --> no LLM request
        |
        v
Task-specific context policy
        |
        +-- exclude unrelated records
        +-- exclude inactive/unconfirmed medication
        +-- exclude unconfirmed attachment extraction
        +-- require explicit report attachment selection
        +-- include only approved and review-valid knowledge
        |
        v
Context budget enforcement
        |
        v
Typed JananiLLMRequest
        |
        v
Privacy-minimised audit event
```

## Domain boundaries

### Direct identity

Names, phone numbers, email addresses, home addresses, and authentication tokens do not belong in the AI context models. The application and database may need identity records for account operations, but the Context Assembly Engine consumes privacy-minimised health records.

### Consent

Consent is represented as append-only events. A later revocation supersedes an earlier grant for the same purpose. Initial context assembly requires:

- `care_support`;
- `ai_processing`;
- `attachment_processing` when the selected task processes attachments.

`model_improvement` and `research` are separate purposes and are never implied by care or AI-processing consent.

### Attachments

Binary files remain in the private `janani-private` storage bucket. Context contains neither a signed URL nor the storage path. Only extracted text may be selected, and only after:

1. extraction completed;
2. required text exists;
3. the user confirmed the extraction;
4. the attachment kind is allowed for the current task;
5. report-explanation requests explicitly selected the attachment.

### Medication

Medication context records preserve their source. Only active, confirmed records can enter a medication-reminder or appointment-preparation request. The context builder never creates a medicine, dose, frequency, or duration.

## Task policies

| Task | Profile | Pregnancy | Medication | Appointments | Attachments | Approved knowledge |
|---|---:|---:|---:|---:|---:|---:|
| Weekly guidance | Yes | Yes | No | No | No | Yes |
| Nutrition | Yes | Yes | No | No | No | Yes |
| Appointment preparation | Yes | Yes | Confirmed | Yes | Confirmed | Yes |
| Report explanation | No | Yes | No | No | Explicitly selected and confirmed | Yes |
| Medication reminder | No | Yes | Active and confirmed | No | No | No |
| General question | Yes | Yes | No | No | No | Yes |

## Database controls

The Supabase migrations add:

- user-owned health profiles;
- pregnancy records;
- append-only consent events;
- medication and appointment records;
- private attachment metadata and extraction versions;
- context assembly audit events;
- owner-scoped RLS policies;
- private storage policies using a user-ID folder prefix;
- database triggers preventing records from being linked to another user's pregnancy.

Backend-only tables have no authenticated write policies. Service credentials must remain server-side and narrowly scoped.

## Audit minimisation

Context audit events may contain:

- task and status;
- safety event ID;
- selected medication, appointment, attachment, and knowledge IDs;
- number of exclusions;
- request schema version;
- synthetic flag and timestamp.

They deliberately exclude:

- the user's question;
- raw symptoms or notes;
- report text;
- prompts;
- model responses;
- names and contact information.

## Current limitations

- The models operate on synthetic data only.
- No Supabase project has been connected or migrated by this repository change.
- Authentication tokens are not yet verified by FastAPI.
- RLS policies have not yet been executed against a staging Supabase instance.
- No durable audit recorder is implemented.
- No extraction/OCR service is implemented.
- No clinician-approved production safety rules exist.
- No clinical knowledge ingestion or RAG exists.
- No Gemini adapter or hosted-model call exists.
- The API is not clinically ready and must not process real pregnancy records.

## Next engineering gate

Before connecting Gemini with synthetic data:

1. validate migrations and RLS against staging Supabase;
2. add backend authentication and user identity propagation;
3. implement durable consent and audit repositories;
4. implement attachment extraction state transitions;
5. add approved knowledge schemas and retrieval tests;
6. freeze and test `JananiLLMRequest` and response schemas;
7. add a Gemini adapter behind the existing synthetic-data configuration guard.
