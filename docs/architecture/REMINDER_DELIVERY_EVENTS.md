# Reminder Delivery Queue and Response Events

Status: synthetic-only engineering foundation. This does not enable clinical use or real patient data.

## Purpose

Phase 10 turns the explicit medication and appointment reminder schedules from Phase 9 into a deterministic, privacy-minimised delivery queue. It intentionally stops before any external push-notification provider is connected.

Janani does not infer medication reminder times from medication names, dose text, prescription text, OCR, an LLM, or clinical rules. Medication occurrences come only from the user's already stored explicit local time, IANA timezone, date range, and weekdays. Appointment occurrences come only from the stored appointment time and the user's explicit reminder lead time.

## Data boundary

`reminder_delivery_jobs` stores only:

- opaque user and schedule identifiers;
- reminder kind (`medication` or `appointment`);
- scheduled time and next transport-attempt time;
- origin (`schedule` or explicit `remind_later`);
- queue status;
- bounded attempt count;
- backend claim metadata;
- a short machine failure code;
- synthetic flag and timestamps.

It does **not** store medication names, dosage, report text, symptoms, clinical notes, prompts, model output, or notification message bodies.

A future push transport should therefore send a generic notification and require the authenticated application to fetch protected details after open. Sensitive health text should not be copied into push-provider payloads by this queue.

## Occurrence materialization

`materialize_janani_reminder_deliveries(window_start, window_end)` is service-role only.

Medication materialization uses PostgreSQL timezone data to convert the explicit local schedule into an absolute delivery time. The materialization window is capped at eight days and inserts are idempotent through unique schedule-occurrence indexes.

Appointment materialization subtracts the explicit lead minutes from the owned scheduled appointment. Cancelled/completed appointments are not materialized.

Disabled medication/appointment schedules are not materialized. Inactive or unconfirmed medication records are also excluded.

## Claim and retry semantics

`claim_janani_reminder_deliveries(now, limit)` is service-role only.

- Claims use `FOR UPDATE SKIP LOCKED` so parallel workers cannot claim the same job concurrently.
- A claim has a unique token.
- Attempt count increments on claim.
- Claims older than 15 minutes are considered stale.
- Stale claims below the attempt cap return to pending with bounded backoff.
- At five attempts, a stale claim becomes failed.
- Claim batches are capped at 100.

`complete_janani_reminder_delivery(...)` requires the exact delivery ID and claim token. Completion uses an explicit worker clock so replay tests, backoff, and completion timestamps use one deterministic time source.

Outcomes are:

- `sent` — terminal success;
- `retryable_failure` — returns to pending with bounded backoff until the five-attempt cap;
- `terminal_failure` — terminal failure.

Failure metadata is limited to a short machine code. Raw provider responses must not be persisted in this table.

## Cancellation races

Queue cancellation is enforced in the database, not left to individual clients.

Future pending or claimed jobs are cancelled when:

- a medication reminder schedule is disabled;
- an appointment reminder schedule is disabled;
- the linked medication becomes inactive or unconfirmed;
- the linked appointment leaves `scheduled` status.

If a worker attempts to complete a job after cancellation, its old claim is rejected because the job is no longer in `claimed` state.

## User response events

`reminder_response_events` is append-only and owner-readable. Direct authenticated inserts are denied; responses are created through `record_janani_reminder_response(...)`, which derives the owner from `auth.uid()`.

Supported neutral events are:

- `opened`;
- `acknowledged`;
- `dismissed`;
- `remind_later` with an explicit future timestamp selected by the user.

There is intentionally no `taken`, `dose_completed`, `adherent`, or equivalent clinical claim. An acknowledgement is only an application interaction and must not be interpreted as proof that medication was taken.

A `client_event_id` makes retries idempotent. Reusing the same client event ID with different content is rejected.

`remind_later` creates a one-off queue occurrence at exactly the user-selected absolute time. It does not change the underlying medication schedule and does not infer a replacement dose time.

## API boundary

Authenticated user API:

- `GET /v1/reminders/deliveries`
- `POST /v1/reminders/deliveries/{delivery_id}/responses`

The user API does not expose claim tokens or transport failure codes.

There are no public materialize/claim/complete routes. The backend worker repository calls service-role-only RPCs, and the service-role key must never be shipped to the mobile application.

## Not implemented in Phase 10

- Expo, FCM, APNs, email, SMS, WhatsApp, or another delivery provider;
- device-token registration for this backend;
- notification message rendering;
- medication adherence scoring;
- dose-taking confirmation;
- clinical escalation from reminder interactions;
- real patient data;
- hosted Supabase changes;
- OCR or LLM behavior.

The next transport phase must preserve the generic-payload privacy boundary and prove provider idempotency before any real notification channel is enabled.
