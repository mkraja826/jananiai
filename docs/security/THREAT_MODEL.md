# Janani AI Foundation Threat Model

Status: Development baseline
Date: 2026-08-03

## Protected assets

- pregnancy and health records;
- medication and appointment information;
- uploaded reports and future extracted text;
- consent records;
- deterministic safety-rule definitions and approvals;
- safety audit events;
- future model credentials, prompts, retrieved context, and outputs.

## Trust boundaries

1. Janani mobile application to FastAPI over HTTPS.
2. FastAPI authentication layer to structured application services.
3. Structured inputs to the deterministic safety engine.
4. Safety engine to future RAG and LLM layers.
5. FastAPI to Supabase Postgres and private Storage.
6. Janani backend to any future hosted model provider.
7. Clinician administration tools to rule and content approval workflows.

## Foundation threats and controls

### Real patient data entering development

Risk: accidental processing of identifiable health data before privacy controls are complete.

Controls:

- free-first mode rejects requests marked as real data;
- only the deterministic mock provider is allowed;
- documentation prohibits real patient use;
- audit models intentionally exclude raw notes and symptom fields.

### Unapproved rule activation

Risk: draft clinical logic could be treated as approved guidance.

Controls:

- every rule has an explicit lifecycle status;
- production mode ignores draft, under-review, and retired rules;
- approved metadata requires clinician sign-off, approval time, and future review time;
- production startup fails when no current approved ruleset is active.

### LLM overriding safety

Risk: a language model weakens, contradicts, or bypasses an escalation.

Controls:

- safety evaluation is deterministic and runs before future LLM use;
- triggered decisions set `blocks_llm=true`;
- the current mock provider is not connected to the safety endpoint;
- future output validation and red-team suites are required before hosted-model use.

### Sensitive information in logs

Risk: raw health information is copied into application or analytics logs.

Controls:

- safety audit events contain rule IDs, severity, ruleset version, and path outcome only;
- raw notes, symptom values, prompts, names, and contact details are excluded;
- durable audit persistence must preserve the same minimum-data contract.

### Expired clinical approval

Risk: an old rule continues operating after its review deadline.

Controls:

- approval metadata includes `next_review_at`;
- expired rules fail the `is_clinically_approved` check;
- production readiness fails when no current approved rule remains.

### Direct database access

Risk: a mobile client reads or modifies clinical rule and audit tables.

Controls:

- RLS is enabled from the first migration;
- no direct authenticated-client policies are created for these internal tables;
- future backend service access must use narrowly scoped server-side credentials.

## Not yet mitigated

The following remain blocking risks for real-user deployment:

- complete authentication and consent design;
- user and caregiver RLS policies;
- durable encrypted audit persistence;
- clinical rule administration and dual-review workflow;
- licensed clinical content ingestion;
- prompt-injection protection for uploaded documents;
- vendor privacy and data-processing agreements;
- key rotation and secret management;
- rate limiting, abuse controls, incident response, and backup restoration testing.

## Review rule

Update this threat model whenever a new data source, external provider, user role, storage path, clinical workflow, or deployment environment is introduced.
