# Lifecycle, reminders, and attachment integrity

Phase 9 adds structured lifecycle and reminder engineering ahead of Janani's unresolved real-clinician authorisation gate. The implementation is synthetic-only and does not make the service clinically deployable.

## Pregnancy completion facts

Pregnancy completion is recorded as an append-only event rather than by silently editing history. The first completion event closes an active pregnancy episode and records `completed_at` atomically. A later correction creates a new event that explicitly supersedes the previous completion event.

The completion record is factual metadata only. Janani does not infer delivery outcome, neonatal condition, diagnosis, prognosis, or treatment from the completion event. Document-derived completion is intentionally not accepted in this phase; that requires a future attachment-linked confirmation workflow.

The pregnancy timeline loads the latest episode so a completed episode remains viewable after delivery or another recorded completion. `GET /v1/pregnancy/active` retains the narrower meaning of an active pregnancy only.

## Reminder boundary

Medication and appointment reminders are scheduling tools, not prescribing tools.

Medication reminder times must be supplied explicitly by the user or another future authorised workflow. Janani does not convert `dose_text`, prescription text, extracted OCR text, or an LLM response into reminder times. Medication reminders can only be created for an owned medication already marked active and confirmed.

Medication schedules store a local clock time, IANA timezone, start/end date, and explicit ISO weekdays. Appointment reminders store an explicit lead time for an owned scheduled appointment. Direct client mutation of schedule rows is denied; controlled RPCs create and disable reminders.

A future notification-delivery worker can consume these schedules, but this phase does not send push notifications or claim medication-adherence functionality.

## Attachment upload handshake

Direct authenticated inserts into `attachment_records` are closed. The intended flow is:

1. The authenticated user requests a short-lived upload intent with attachment kind, MIME type, byte size, expected SHA-256 digest, and optional pregnancy/document metadata.
2. Janani returns a generated path beneath that user's private Storage folder.
3. The client uploads the file to the private bucket.
4. Finalization verifies that a Storage object exists at the exact intent path and that Storage-reported size and MIME type match the intent.
5. Janani creates the attachment metadata row with integrity state `pending_worker_hash` and marks the intent completed.
6. Once finalized, authenticated clients may read the object but cannot overwrite or delete that exact object path.
7. A backend-only worker reads the immutable object, calculates its SHA-256 digest, and calls the service-role-only verification RPC.
8. Extraction is allowed only when integrity state is `verified`.

A size/MIME match is not treated as cryptographic verification. Only the backend worker hash step can set `verified`. A mismatch keeps the file out of extraction and therefore out of AI context.

## Storage restrictions

The Janani private bucket is constrained by this migration to the app-level maximum of 20 MiB and the document/image MIME types currently supported by the attachment contract:

- `application/pdf`
- `image/jpeg`
- `image/png`
- `image/webp`

A stricter project-level Storage limit may still apply. The bucket remains private and owner folder access remains enforced with Storage RLS.

## AI/context boundary

Attachment text can become context-eligible only when all of these are true:

- the finalized file passed backend SHA-256 verification;
- extraction completed;
- the user confirmed the extraction;
- extracted text exists;
- all existing task, consent, selection, safety, and context-budget rules also pass.

The timeline exposes attachment metadata only and never extracted report text.

## Security model

- User identity comes from the authenticated Supabase bearer token.
- RLS restricts reads to the owner.
- Completion, reminder, upload-intent, and upload-finalization writes use owner-scoped security-definer RPCs that derive `auth.uid()` rather than trusting a client-supplied owner ID.
- Hash verification and extraction persistence remain service-role-only backend operations.
- Finalized Storage objects are immutable to authenticated clients.
- The hosted Janani Supabase project is not modified by Phase 9 validation; GitHub Actions rebuilds migrations in an isolated local Supabase stack with ephemeral synthetic users.

## Explicit non-goals

Phase 9 does not add or enable:

- real patient data processing;
- clinician-approved warning rules;
- medication prescribing or dose interpretation;
- reminder-time inference from prescriptions or OCR;
- push-notification delivery;
- OCR/extraction workers themselves;
- ultrasound-image interpretation;
- Gemini or another hosted LLM;
- clinical RAG;
- clinical or production readiness.

Official Janani progress therefore remains at the 29% gate until the real clinical-authorisation and hosted-staging requirements are satisfied.
