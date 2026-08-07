# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 29%

Updated: 2026-08-08
Branch: `phase-10/reminder-delivery-events`
Latest verified engineering implementation commit: `65f7e7c`
Draft PR: `#10`
Percentage gate: remains at 29% until the real 29–30% clinical-authorisation and hosted-staging requirements pass.

Engineering is allowed to continue building isolated synthetic-only components ahead of this gate. Those components do not advance the official verified percentage beyond 29%.

## Foundation completed and verified

- [x] Repository initialised and mission/safety boundaries documented.
- [x] Free-first Python/FastAPI foundation created.
- [x] Typed health, readiness, safety, and provider-neutral AI contracts created.
- [x] Deterministic safety-engine core created.
- [x] Draft rules remain development-only and excluded from production activation.
- [x] Mock LLM provider created; no hosted model is required for current engineering.
- [x] Privacy-minimised safety auditing created.
- [x] Pytest, Ruff, Docker, and GitHub Actions foundations created.
- [x] Architecture decisions, threat model, and permanent progress tracker established.

## Phase 2 — data, consent, attachments, and context foundation

- [x] Added privacy-minimised user-health, pregnancy, medication, and appointment models.
- [x] Added append-only consent events with separate care, AI, attachment, model-improvement, and research purposes.
- [x] Added attachment extraction/confirmation state contracts.
- [x] Blocked attachment text from AI context until extraction is completed and user-confirmed.
- [x] Added task-specific context inclusion/exclusion rules and context budgets.
- [x] Added the deterministic Context Assembly Engine and provider-neutral `JananiLLMRequest`.
- [x] Added synthetic-only context assembly API and privacy-minimised context auditing.
- [x] Added initial Supabase schema, private Storage, owner RLS, and cross-owner link triggers.
- [x] GitHub Actions passed on implementation commit `8686255`: 12 safety tests, 92.50% safety coverage, 40 full-suite tests, and Docker build.

## Phase 3 — authenticated persistence and local RLS validation

- [x] Added Supabase bearer-token verification and verified request identity.
- [x] Added RLS-scoped PostgREST persistence using the caller token and publishable key.
- [x] Added authenticated stored-context assembly.
- [x] Added minimal safety/context audit RPCs without raw questions, symptom notes, reports, prompts, or model outputs.
- [x] Added attachment extraction state transitions and service-role-only extraction persistence.
- [x] Added account-deletion request foundation.
- [x] Added explicit table grants/revokes and owner-read audit policies.
- [x] Added isolated local Supabase CI with ephemeral synthetic users.
- [x] Verified RLS isolation, append-only consent, private Storage, RPC ownership, extraction separation, and deletion-request privacy.
- [x] GitHub Actions passed on `5b4210a`: quality pipeline green and 9/9 local RLS/RPC/Storage integration tests passed.

## Phase 4 — clinical safety governance foundation

- [x] Added distinct obstetrician and clinical-safety sign-off requirements.
- [x] Added reviewer identity, jurisdiction, license reference, verification and expiry metadata.
- [x] Added clinical-source provenance, exact sections, applicability, and review expiry.
- [x] Added English/Telugu escalation wording contracts.
- [x] Added immutable review candidates and candidate digests.
- [x] Added release approval, activation, retirement, replacement, rollback, and append-only governance events.
- [x] Marked all current warning-rule candidates with development-placeholder provenance so clinical activation remains impossible.
- [x] Denied end-user access to governance tables/RPCs.
- [x] Added adversarial governance and local-Supabase validation.
- [x] GitHub Actions passed on `148565f`: 27 safety tests, 96.87% safety coverage, 80 full-suite tests, 10 expected staging skips, Docker build, and 10/10 local integration tests.

## Phase 5 — atomic deterministic safety rulesets

- [x] Made a complete safety ruleset the deployable unit.
- [x] Added exact required-rule manifests and immutable member digests.
- [x] Rejected incomplete, duplicate, altered, expired, extra, or invalid manifests.
- [x] Added service-role-only approval, activation, replacement, and rollback RPCs.
- [x] Enforced one active ruleset and exact active-release consistency.
- [x] Added drift detection and PostgREST RPC discovery validation.
- [x] Added two-generation activation/replacement/rollback integration validation.
- [x] GitHub Actions passed on `59c7c10`: 34 safety tests, 97.44% safety coverage, 94 full-suite tests, 12 expected staging skips, Docker build, and 12/12 local integration tests.

## Phase 6 — reviewer administration and validation datasets

- [x] Added trusted governance roles sourced only from Supabase `app_metadata`.
- [x] Added reviewer onboarding, credential reverification, and controlled deactivation.
- [x] Added conflict-of-interest attestation and opaque evidence references.
- [x] Added disabled-by-default backend governance administration APIs.
- [x] Kept service-role credentials outside mobile/browser clients.
- [x] Added append-only reviewer lifecycle events and active-release deactivation protection.
- [x] Added 35 synthetic validation cases across true-positive, true-negative, boundary, interaction, and regression categories.
- [x] Added fail-closed validation-dataset checks and per-rule reporting.
- [x] GitHub Actions passed on `dcda56f`: 49 safety tests, 96.33% safety coverage, 149 full-suite tests, 13 expected staging skips, Docker build, and 13/13 local integration tests.

## Phase 7 — pre-clinical review packets and rollback rehearsal

- [x] Expanded deterministic validation to 63 synthetic cases across nine categories per rule.
- [x] Added ambiguity, missing-data, adversarial, and cross-rule challenge cases.
- [x] Added immutable pre-clinical review packets bound to exact candidate and dataset digests.
- [x] Required obstetrician, clinical-safety, and language-review roles in review packets.
- [x] Kept packets non-eligible while placeholder clinical sources remain.
- [x] Added synthetic emergency rollback rehearsal with six required evidence steps.
- [x] Added private append-only review/rehearsal evidence persistence.
- [x] Found and fixed PostgreSQL `42702` ambiguous JSON-value extraction during real local validation.
- [x] Hardened rehearsal persistence to require complete passing evidence.
- [x] GitHub Actions passed on `de9b594`: 63 safety tests, 95.43% safety coverage, 168 full-suite tests, 14 expected staging skips, Docker build, and 14/14 local integration tests.

## Phase 8 — structured pregnancy engineering ahead of the unresolved 30% gate

- [x] Added structured pregnancy episode dating, provenance, status, and lifecycle contracts without clinical interpretation.
- [x] Added typed weight, blood-pressure, and lab-result observation records.
- [x] Added pregnancy encounter records.
- [x] Made observation/encounter corrections append-only through supersession.
- [x] Added a factual chronological timeline combining observations, encounters, appointments, and attachment metadata.
- [x] Kept timeline rendering neutral; it does not label recorded values normal, abnormal, reassuring, dangerous, or diagnostic.
- [x] Added attachment document date, label, capture source, size, and SHA-256 metadata.
- [x] Kept extracted text outside timeline summaries.
- [x] Added authenticated pregnancy timeline APIs and RLS-protected append-only persistence.
- [x] GitHub Actions passed on `8914d80`: 63 safety tests, 95.43% safety coverage, 183 full-suite tests, 15 expected staging skips, Docker build, and 15/15 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 9 — pregnancy lifecycle, explicit reminders, and upload integrity ahead of the unresolved 30% gate

- [x] Added append-only pregnancy completion events and superseding corrections.
- [x] Made first completion atomically close the active pregnancy episode and set `completed_at`.
- [x] Kept completion records factual and non-diagnostic.
- [x] Kept completed pregnancy history viewable while `/active` remains active-only.
- [x] Added explicit medication reminder schedules with user-selected local time, IANA timezone, date range, and weekdays.
- [x] Required medication reminder targets to be caller-owned, active, and confirmed.
- [x] Never derive medication reminder timing from dose text, prescription text, OCR, rules, or an LLM.
- [x] Added explicit appointment reminder lead times.
- [x] Kept reminder schedules owner-readable but RPC-controlled for mutation.
- [x] Added short-lived owner-scoped attachment upload intents.
- [x] Restricted uploads to PDF/JPEG/PNG/WEBP with a 20 MiB application limit.
- [x] Required expected SHA-256 before upload.
- [x] Finalization verifies the exact private Storage object, MIME type, and byte size.
- [x] Closed direct authenticated attachment-row writes.
- [x] Made finalized object paths immutable to authenticated clients.
- [x] Added service-only SHA-256 verification and blocked extraction until integrity is verified.
- [x] Required verified integrity + completed extraction + user confirmation before extracted text can be context-eligible.
- [x] GitHub Actions passed on `bf1ddeb`: 63 safety tests, 95.43% safety coverage, 194 full-suite tests, 16 expected staging skips, Docker build, and 18/18 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 10 — deterministic reminder delivery and neutral response events ahead of the unresolved 30% gate

- [x] Added a privacy-minimised `reminder_delivery_jobs` queue containing opaque identifiers, timing, status, attempts, claim metadata, and short machine failure codes only.
- [x] Excluded medication names, dose text, schedule text, symptoms, report content, prompts, model output, and notification message bodies from delivery jobs.
- [x] Added deterministic medication occurrence materialization from the user's explicit schedule only.
- [x] Used PostgreSQL IANA timezone data for local-time-to-absolute-time conversion.
- [x] Added deterministic appointment occurrence materialization from explicit appointment time minus the user's explicit lead minutes.
- [x] Capped materialization windows and added unique occurrence indexes so repeated materialization is idempotent.
- [x] Kept delivery-job writes service-role only while authenticated owners may read only their own jobs through RLS.
- [x] Added backend-only materialize, claim, and completion RPCs; no public worker routes exist.
- [x] Added `FOR UPDATE SKIP LOCKED` claiming so parallel workers cannot claim the same pending job concurrently.
- [x] Added opaque claim tokens and exact claim-token validation on completion.
- [x] Added 15-minute stale-claim recovery.
- [x] Added bounded retry/backoff with a maximum of five attempts.
- [x] Added an explicit worker clock so claim, retry, and completion timestamps are deterministic and replayable.
- [x] Added database cancellation of pending/claimed jobs when a reminder is disabled.
- [x] Added database cancellation when a linked medication becomes inactive/unconfirmed or an appointment leaves `scheduled` status.
- [x] Added append-only neutral response events: `opened`, `acknowledged`, `dismissed`, and explicit `remind_later`.
- [x] Deliberately excluded `taken`, `dose_completed`, `adherent`, or similar medication-taking claims.
- [x] Added client-event IDs for idempotent response retries; reusing an ID with different content is rejected.
- [x] Added one-off `remind_later` delivery occurrences at the exact timestamp selected by the user without changing the underlying medication schedule.
- [x] Bound response synthetic/real data mode to the original delivery so direct RPC callers cannot relabel event provenance.
- [x] Added `GET /v1/reminders/deliveries` and `POST /v1/reminders/deliveries/{delivery_id}/responses`.
- [x] Kept worker claim tokens and transport failure metadata out of authenticated user API responses.
- [x] Added a service-role-only worker repository without connecting any push provider.
- [x] Added model, API, worker, migration-contract, and clean local-Supabase integration tests.
- [x] Corrected the integration fixture after it incorrectly supplied a nonexistent `synthetic` field to `medication_records`; no schema weakening was used.
- [x] Verified Asia/Kolkata schedule materialization, owner isolation, direct job-forging denial, service-only claiming, explicit completion clock, cross-user response denial, response idempotency, remind-later creation, retry backoff, terminal failure, and future-job cancellation.
- [x] GitHub Actions passed on `65f7e7c`: Ruff lint and formatting, 63 safety tests with 95.43% safety-module coverage, 212 full-suite tests with 19 expected staging skips, Docker build, every migration rebuilt from zero, PostgREST schema refresh, two ephemeral synthetic users, and 19/19 local integration tests.
- [x] Official progress intentionally remains 29%; this engineering-ahead work does not satisfy the real clinical-authorisation gate.

## Current limitations

- No real licensed clinician has been onboarded through the reviewer administration flow.
- No real reviewer credential, attestation, or identity-evidence document has been stored or verified.
- The governance administration API remains disabled by default and has only synthetic validation.
- No warning rule has been reviewed or approved by a licensed clinician.
- Every current safety candidate contains development-placeholder provenance and cannot be activated.
- Current English and Telugu escalation wording remains development-only and not clinically approved.
- The 63 validation cases and review packets are synthetic engineering evidence, not clinical validation or real-world safety evidence.
- Rollback rehearsal evidence is synthetic and local only.
- Structured pregnancy, lifecycle, attachment, reminder scheduling, and reminder delivery services are validated only with synthetic/local data and do not interpret clinical meaning.
- No real patient data may be processed.
- The existing hosted Janani Supabase project has not been modified.
- No dedicated hosted staging project or paid Supabase branch exists; validation currently uses isolated local Docker infrastructure.
- No Expo Push, FCM, APNs, email, SMS, WhatsApp, or other notification transport is connected.
- No device push-token registry for the Janani AI backend is implemented.
- No notification message-rendering layer is implemented.
- No medication adherence scoring or dose-taking confirmation exists; `acknowledged` is only an application interaction.
- No production scheduler/worker process is deployed to continuously materialize and dispatch reminder jobs.
- No Gemini adapter or hosted LLM is connected.
- No hosted-model response schema or output-policy validator is implemented yet.
- No OCR/extraction worker process is implemented; only worker-side integrity/extraction persistence contracts exist.
- No approved clinical-content ingestion, embeddings, or RAG retrieval is implemented.
- The deletion-request workflow does not yet include controlled deletion execution, Storage cleanup, session revocation, or retention-policy execution.
- No caregiver sharing or partner permissions model is implemented.
- The service is not deployable for clinical use.

## Next milestone: 29–30% — real clinical authorisation and hosted staging gate

- Approve reviewer-onboarding, conflict-of-interest, credential-verification, evidence-retention, and governance operating procedures.
- Verify real obstetrician, clinical-safety, and Telugu-language reviewer credentials outside source control.
- Replace every development placeholder with current clinician-reviewed sources and exact sections.
- Obtain actual human review and approval of every predicate, severity, rationale, and applicability boundary.
- Obtain qualified clinical and language approval of English and Telugu escalation wording.
- Obtain independently authored and independently reviewed expected outcomes beyond the implementation team.
- Rehearse incident ownership, reviewer deactivation, release retirement, and emergency rollback under approved operating procedures.
- Repeat governance/reviewer/release/ruleset/rehearsal validation in isolated hosted staging using synthetic data only.
- Document production access control, incident ownership, privacy, legal, security, and clinical launch sign-off.
- Keep every rule inactive until every real-world authorization, hosted test, and launch gate passes.

Engineering may continue building isolated synthetic-only 30–39% components ahead of this gate, but the official verified percentage must not advance past 29% until these external requirements are satisfied.

## Revised roadmap allocation

- 0–4%: governance and source of truth
- 4–10%: engineering foundation
- 10–18%: database, authentication, consent, privacy, and RLS
- 18–30%: clinician-approved deterministic safety engine
- 30–39%: structured pregnancy services and attachment records
- 39–48%: attachment extraction, confirmation, task routing, and Context Assembly Engine
- 48–57%: clinical content management and RAG retrieval
- 57–65%: typed LLM contracts, Gemini adapter, and provider orchestration
- 65–71%: output validation, citations, audit, English, and Telugu
- 71–84%: twelve core capabilities and partner mode
- 84–90%: specialised extraction, ranking, and intent ML pipelines
- 90–94%: shadow-mode evaluation
- 94–97%: observability, security, reliability, and load testing
- 97–99%: controlled clinical pilot
- 99–100%: production-readiness gate

## Change log

### 2026-08-08 — 29% + Phase 10 engineering ahead

Built and verified the deterministic reminder-delivery foundation on `phase-10/reminder-delivery-events` while intentionally leaving official progress at 29%. Explicit medication schedules are materialized with PostgreSQL timezone data; appointment reminders use explicit lead minutes. Delivery jobs contain only opaque references, timing, queue state, bounded retry metadata, and short machine failure codes. Service-only workers use idempotent occurrence keys, `FOR UPDATE SKIP LOCKED`, claim tokens, stale-claim recovery, an explicit worker clock, and a five-attempt cap. Database triggers cancel future jobs when their schedule or source record becomes invalid. User interactions are neutral append-only `opened`, `acknowledged`, `dismissed`, or explicit `remind_later` events and never claim a dose was taken. Response retries are idempotent and response data mode is bound to the original delivery. GitHub Actions passed on `65f7e7c`: 63 safety tests with 95.43% coverage, 212 full-suite tests, 19 expected staging skips, Docker build, every migration rebuilt from zero, and 19/19 local integration tests. No real patient data, hosted project change, push provider, production worker deployment, clinician approval, OCR worker, or hosted LLM was introduced.

### 2026-08-07 — 29% + Phase 9 engineering ahead

Built and verified pregnancy completion lifecycle, explicit medication/appointment reminder schedules, and the secure attachment upload-integrity handshake on `phase-9/lifecycle-reminders-upload-integrity`. Reminder timing remains explicit user configuration and is never inferred from dose, prescription, OCR, or AI output. Uploads use owner-scoped intents, private Storage, MIME/size checks, immutable finalized objects, and service-only SHA-256 verification before extraction. GitHub Actions passed on `bf1ddeb`: 63 safety tests with 95.43% coverage, 194 full-suite tests, 16 expected staging skips, Docker build, and 18/18 local integration tests.

### 2026-08-07 — 29% + Phase 8 engineering ahead

Built and verified the first structured-pregnancy engineering layer on `phase-8/pregnancy-services-attachments`. Added factual pregnancy timeline records, append-only observations/encounters and corrections, attachment metadata, authenticated APIs, and owner-scoped persistence without clinical interpretation. GitHub Actions passed on `8914d80`: 63 safety tests with 95.43% coverage, 183 full-suite tests, 15 expected staging skips, Docker build, and 15/15 local integration tests.

### 2026-08-07 — 29%

Built and verified pre-clinical review packets, 63-case safety challenge datasets, immutable review/rehearsal evidence, and synthetic emergency rollback rehearsal on `phase-7/clinical-review-rehearsal`. GitHub Actions passed on `de9b594`: 63 safety tests with 95.43% coverage, 168 full-suite tests, 14 expected staging skips, Docker build, and 14/14 local integration tests.

### 2026-08-05 — 27%

Built and verified reviewer administration and executable safety validation datasets on `phase-6/reviewer-admin-validation-datasets`. GitHub Actions passed on `dcda56f`: 49 safety tests with 96.33% coverage, 149 full-suite tests, 13 expected staging skips, Docker build, and 13/13 local integration tests.

### 2026-08-04 — 25%

Built and verified atomic deterministic safety rulesets on `phase-5/atomic-ruleset-activation`. GitHub Actions passed on `59c7c10`: 34 safety tests with 97.44% coverage, 94 full-suite tests, 12 expected staging skips, Docker build, and 12/12 local integration tests.

### 2026-08-04 — 22%

Built and verified the clinical safety governance foundation on `phase-4/clinical-safety-governance`. All seven warning-rule candidates remain development-only and unapprovable. GitHub Actions passed on `148565f`: 27 safety tests with 96.87% coverage, 80 full-suite tests, 10 expected staging skips, Docker build, and 10/10 local integration tests.

### 2026-08-04 — 18%

Completed the free authenticated-persistence validation gate without creating a paid Supabase branch or changing the hosted Janani project. GitHub Actions passed on `5b4210a` with all 9 local RLS/RPC/Storage tests passing.

### 2026-08-04 — 17%

Built authenticated persistence on `phase-3/authenticated-persistence`: Supabase token verification, RLS-scoped record loading, stored-context assembly, privacy-minimised audit RPCs, attachment states, and deletion-request foundations.

### 2026-08-04 — 14%

Built the initial data, consent, attachment, and Context Assembly Engine layer on `phase-2/data-context-foundation`. GitHub Actions passed on `8686255` with 40 full-suite tests.

### 2026-08-04 — 10%

Completed the free-first engineering foundation and provider-neutral architecture. GitHub Actions passed on `5c283d5`.

### 2026-08-03 — 8%

Corrected foundation linting/formatting and verified the complete foundation CI pipeline.

### 2026-08-03 — 7%

Created the initial FastAPI service, deterministic safety scaffold, mock provider, tests, CI, Docker, migration, and architecture documentation. Real patient use remained explicitly blocked.
