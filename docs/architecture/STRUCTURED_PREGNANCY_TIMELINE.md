# Structured Pregnancy Timeline and Attachment Records

Status: engineering foundation built ahead of the unresolved clinical-authorisation gate. Synthetic data only.

## Purpose

This layer gives Janani a structured longitudinal pregnancy record without turning storage or timeline code into a clinical decision system.

The service stores and returns recorded facts, provenance, confirmation state, and chronology. It does not decide whether a value is normal or abnormal, diagnose a condition, prescribe treatment, change medication, or interpret ultrasound images.

## Pregnancy episode

An active pregnancy episode can record:

- gestational week;
- estimated due date;
- last menstrual period when supplied;
- dating source;
- whether dating was confirmed;
- known-condition labels already recorded by the user/application;
- weight already present on the episode;
- clinician-restriction text already present on the episode;
- active/completed/archived lifecycle state;
- synthetic-development state.

Dating provenance is explicit. A user-reported LMP source requires an LMP date. EDD-based sources require an EDD. Confirmed dating cannot use an unknown source.

## Structured observations

`pregnancy_observations` is an append-only user-owned record for:

- weight;
- blood pressure;
- lab-result facts.

The data model validates shape only. For example, a blood-pressure record requires both systolic and diastolic values, but Janani does not classify that pair as safe, unsafe, normal, or abnormal in this layer.

A document-confirmed observation requires both user confirmation and a source attachment belonging to the same user and pregnancy.

Corrections are represented with `supersedes_observation_id`. Authenticated users receive no direct UPDATE or DELETE privilege on this table.

## Pregnancy encounters

`pregnancy_encounters` stores chronological encounters such as routine visits, scans, lab reviews, procedures, and other visits.

It records occurrence time, an optional summary, an optional next follow-up time, provenance, confirmation, an optional source attachment, and an optional superseded encounter.

Document-confirmed encounters require confirmation plus a same-owner, same-pregnancy source attachment. Corrections use `supersedes_encounter_id` rather than rewriting prior history.

## Attachment metadata boundary

Attachment registration records metadata needed for chronology and integrity:

- pregnancy link;
- document kind;
- MIME type;
- private Storage object path;
- document date;
- display label;
- capture source;
- file size;
- optional SHA-256 content digest.

`AttachmentSummary` is the timeline-safe representation. It deliberately does not contain extracted report text.

`AttachmentRecord` remains the private representation used by controlled extraction/context flows and may contain extracted text only under the existing extraction and user-confirmation rules.

The API additionally requires registered object paths to start inside the authenticated user's private Storage folder.

## Timeline assembly

`GET /v1/pregnancy/timeline` loads the user's active episode and concurrently retrieves records for that exact `user_id` and `pregnancy_id`:

- observations;
- encounters;
- appointments;
- attachment metadata.

The service converts them to neutral timeline items and sorts them newest first.

The merger may render a recorded value literally, for example `120/80 mmHg`, but must not add an interpretation such as normal, abnormal, high, low, reassuring, dangerous, or diagnostic.

## API surface

- `GET /v1/pregnancy/active`
- `GET /v1/pregnancy/timeline`
- `POST /v1/pregnancy/observations`
- `POST /v1/pregnancy/encounters`
- `POST /v1/pregnancy/attachments/register`

Real-health write payloads remain blocked when `allow_real_patient_data` is disabled. This phase does not enable that flag.

## Database security

Both timeline tables have RLS enabled.

Authenticated callers receive only SELECT and INSERT privileges. Owner policies require `auth.uid() = user_id` and pregnancy ownership. Database triggers independently reject references to another user's pregnancy, source attachment, or superseded record.

Repository queries also include explicit `user_id` and `pregnancy_id` filters in addition to RLS.

The service-role boundary remains backend-only.

## Testing

The engineering gate covers:

- model-shape and provenance validation;
- no-interpretation timeline behavior;
- explicit repository ownership filters;
- API synthetic/real-data gates;
- static migration contracts;
- local Supabase owner isolation;
- cross-user link rejection;
- direct UPDATE/DELETE denial;
- append-only superseding corrections;
- complete migration rebuild from an empty local database.

## What this does not unlock

This engineering layer does not clear Janani's 29→30% clinical-authorisation gate. It does not make current deterministic warning rules clinically approved, enable real patient use, connect Gemini, add OCR interpretation, or create a production deployment.

The unresolved external gate still requires real qualified reviewers, approved operating procedures, reviewed sources and wording, independent expected-outcome review, hosted staging rehearsal, and launch sign-off.

## Next engineering work after this layer

Likely follow-on work within the structured pregnancy-services area includes:

1. controlled pregnancy lifecycle transitions, including completion/delivery records;
2. structured medication-reminder schedule links rather than medication interpretation;
3. appointment/reminder scheduling state;
4. safer condition/history vocabularies with provenance;
5. attachment upload-registration handshake and integrity verification;
6. timeline pagination and supersession-aware presentation;
7. later integration into Context Assembly only after task relevance, consent, confirmation, and clinical-content gates remain satisfied.
