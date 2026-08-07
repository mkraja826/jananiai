# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 29%

Updated: 2026-08-08
Branch: `phase-13/expo-push-adapter`
Latest verified engineering implementation commit: `63f5953`
Draft PR: `#13`
Percentage gate: remains at 29% until the real 29–30% clinical-authorisation and hosted-staging requirements pass.

Engineering is allowed to continue building isolated synthetic-only components ahead of this gate. Those components do not advance the official verified percentage beyond 29%.

## Permanent safety boundaries

- [x] No diagnosis.
- [x] No prescribing or medication dose changes.
- [x] No independent ultrasound-image interpretation.
- [x] Real patient data remains prohibited during current development.
- [x] Free-first mode permits the mock LLM only.
- [x] Supabase service-role credentials are backend-only and must never be exposed to mobile/browser clients.
- [x] Safety/context/worker auditing avoids raw symptoms, reports, questions, prompts, model outputs, notification tokens, and other unnecessary sensitive content.
- [x] Current warning rules and bilingual escalation wording remain development-only until qualified clinical review and approval.
- [x] Hosted Janani Supabase remains untouched by the synthetic/local engineering phases recorded below.

## Foundation — 0–10%

- [x] Repository mission, safety boundaries, architecture decisions, threat model, and this permanent tracker established.
- [x] Free-first Python/FastAPI service foundation created.
- [x] Typed health/readiness/safety/provider-neutral AI contracts created.
- [x] Deterministic safety-engine core created.
- [x] Mock LLM provider created.
- [x] Privacy-minimised safety auditing created.
- [x] Pytest, Ruff, Docker, and GitHub Actions foundations created.
- [x] Foundation CI verified on `5c283d5`.

## Phase 2 — data, consent, attachments, and context foundation

- [x] Added privacy-minimised profile, pregnancy, medication, and appointment models.
- [x] Added append-only consent events for care support, AI processing, attachment processing, model improvement, and research.
- [x] Added attachment extraction/confirmation states and blocked extracted text from AI context until complete and user-confirmed.
- [x] Added task-specific context inclusion/exclusion, budgets, deterministic Context Assembly Engine, and provider-neutral `JananiLLMRequest`.
- [x] Added synthetic-only context assembly API, minimal context auditing, initial Supabase schema, private Storage, owner RLS, and cross-owner guards.
- [x] GitHub Actions passed on `8686255`: 12 safety tests, 92.50% safety coverage, 40 full-suite tests, Docker build.

## Phase 3 — authenticated persistence and free local RLS validation

- [x] Added Supabase bearer-token verification and authenticated request identity.
- [x] Added RLS-scoped PostgREST persistence using publishable key + caller bearer token and authenticated stored-context assembly.
- [x] Added minimal safety/context audit RPCs, attachment extraction transitions, service-role-only extraction persistence, and account-deletion request foundation.
- [x] Added explicit grants/revokes, owner-readable audit policies, and isolated local-Supabase CI using two ephemeral synthetic users.
- [x] Verified owner isolation, append-only consent, private Storage, RPC ownership, extraction separation, and deletion-request privacy.
- [x] GitHub Actions passed on `5b4210a`: quality green and 9/9 local integration tests.

## Phase 4 — clinical safety governance foundation

- [x] Added distinct obstetrician and clinical-safety approval requirements plus reviewer identity, jurisdiction, license reference, verification, expiry, source provenance, exact-section, applicability, and review-expiry contracts.
- [x] Added English/Telugu escalation wording contracts, immutable review candidates/digests, release approval/activation/retirement/replacement/rollback, and append-only governance events.
- [x] Marked all current safety candidates as development-placeholder provenance so real activation remains impossible.
- [x] Denied ordinary end-user access to governance tables/RPCs.
- [x] GitHub Actions passed on `148565f`: 27 safety tests, 96.87% coverage, 80 full-suite tests, 10 expected staging skips, Docker build, 10/10 local integration tests.

## Phase 5 — atomic deterministic safety rulesets

- [x] Made the complete safety ruleset the deployable unit with exact required-rule manifests and immutable member digests.
- [x] Rejected incomplete, duplicate, altered, expired, extra, or invalid manifests.
- [x] Added service-role-only approval/activation/replacement/rollback RPCs, one-active-ruleset enforcement, drift detection, PostgREST discovery checks, and two-generation rollback validation.
- [x] GitHub Actions passed on `59c7c10`: 34 safety tests, 97.44% coverage, 94 full-suite tests, 12 expected staging skips, Docker build, 12/12 local integration tests.

## Phase 6 — reviewer administration and validation datasets

- [x] Added trusted governance roles sourced only from Supabase `app_metadata`.
- [x] Added reviewer onboarding, credential reverification, controlled deactivation, conflict-of-interest attestation, opaque evidence references, disabled-by-default backend governance APIs, append-only reviewer lifecycle events, and active-release deactivation protection.
- [x] Added 35 synthetic validation cases across true-positive, true-negative, boundary, interaction, and regression categories plus fail-closed validation reporting.
- [x] GitHub Actions passed on `dcda56f`: 49 safety tests, 96.33% coverage, 149 full-suite tests, 13 expected staging skips, Docker build, 13/13 local integration tests.

## Phase 7 — pre-clinical review packets and rollback rehearsal

- [x] Expanded deterministic validation to 63 synthetic cases across nine categories per rule, including ambiguity, missing-data, adversarial, and cross-rule challenges.
- [x] Added immutable pre-clinical review packets bound to candidate/dataset digests and requiring obstetrician, clinical-safety, and language-review roles.
- [x] Kept packets non-eligible while placeholder sources remain.
- [x] Added synthetic emergency rollback rehearsal, private append-only evidence persistence, and fixed PostgreSQL `42702` ambiguous JSON extraction found during local validation.
- [x] GitHub Actions passed on `de9b594`: 63 safety tests, 95.43% coverage, 168 full-suite tests, 14 expected staging skips, Docker build, 14/14 local integration tests.
- [x] Official progress reached 29% and is intentionally gated there pending real-world authorization.

## Phase 8 — structured pregnancy engineering ahead of the unresolved 30% gate

- [x] Added structured pregnancy episode dating/provenance/status/lifecycle contracts, typed weight/BP/lab/encounter records, and append-only superseding corrections.
- [x] Added factual chronological timeline combining observations, encounters, appointments, and attachment metadata without clinical interpretation.
- [x] Added attachment document date, label, capture source, size, SHA-256 metadata, authenticated timeline APIs, and owner-scoped persistence.
- [x] GitHub Actions passed on `8914d80`: 63 safety tests, 95.43% coverage, 183 full-suite tests, 15 expected staging skips, Docker build, 15/15 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 9 — lifecycle, explicit reminders, and upload integrity ahead of the unresolved 30% gate

- [x] Added append-only pregnancy completion events/corrections and factual pregnancy history.
- [x] Added medication reminder schedules using explicit user-selected local time, IANA timezone, date range, and weekdays; timing is never inferred from dose/prescription/OCR/rules/LLM.
- [x] Added explicit appointment reminder lead times.
- [x] Added short-lived owner-scoped attachment upload intents, PDF/JPEG/PNG/WEBP and 20 MiB limits, expected SHA-256, exact Storage/MIME/size finalization, immutable finalized paths, and service-only SHA verification.
- [x] Required verified integrity + completed extraction + user confirmation before extracted text becomes context-eligible.
- [x] GitHub Actions passed on `bf1ddeb`: 63 safety tests, 95.43% coverage, 194 full-suite tests, 16 expected staging skips, Docker build, 18/18 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 10 — deterministic reminder delivery and neutral response events ahead of the unresolved 30% gate

- [x] Added privacy-minimised `reminder_delivery_jobs` containing opaque identifiers/timing/status/attempts/claim metadata/short failure codes only.
- [x] Excluded medication names, doses, symptoms, report content, prompts, model output, and notification message bodies from delivery jobs.
- [x] Added deterministic medication/appointment occurrence materialization from explicit schedules, PostgreSQL IANA timezone conversion, capped/idempotent windows, service-only materialize/claim/complete RPCs, `FOR UPDATE SKIP LOCKED`, opaque claim tokens, stale recovery, explicit worker clock, and five-attempt retry cap.
- [x] Added future-job cancellation when reminder/source records become invalid.
- [x] Added neutral append-only `opened`, `acknowledged`, `dismissed`, and explicit `remind_later` events; deliberately excluded `taken`, `dose_completed`, `adherent`, and similar claims.
- [x] Added idempotent client-event IDs, one-off exact-time remind-later occurrences, and owner APIs without worker secrets.
- [x] GitHub Actions passed on `65f7e7c`: 63 safety tests, 95.43% coverage, 212 full-suite tests, 19 expected staging skips, Docker build, all migrations rebuilt, 19/19 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 11 — private notification devices and provider-neutral transport ahead of the unresolved 30% gate

- [x] Added private `notification_devices` lifecycle registry with backend-only push-token storage; raw table remains unavailable to `anon`/`authenticated`.
- [x] Added identity-derived register/list/revoke RPCs, `SecretStr` token boundaries, atomic installation rotation, SHA-256 fingerprint/advisory locking, and cross-user active-token protection.
- [x] Added service-only destination lookup bound to exact active `delivery_id + claim_token` with matching synthetic/real provenance.
- [x] Added provider-neutral `NotificationTransport`, network-free `MockNotificationTransport`, generic `Janani reminder` / `You have a reminder in Janani.` envelope, and deterministic dispatch semantics.
- [x] Kept medication/dose/symptom/appointment/report/diagnosis/treatment/prompt/model content out of notification bodies and worker dispatch off public routes.
- [x] GitHub Actions passed on `027b60b`: 63 safety tests, 95.43% coverage, 231 full-suite tests, 21 expected staging skips, Docker build, all migrations rebuilt, 21/21 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 12 — bounded run-once reminder worker runtime ahead of the unresolved 30% gate

- [x] Added backend-only `janani-reminder-worker` run-once CLI; each invocation performs one bounded materialization/claim/dispatch/completion cycle and exits.
- [x] Added no infinite loop, daemon thread, API background task, or public worker route.
- [x] Captures one timezone-aware UTC-normalized clock; worker disabled by default; enabled worker requires Supabase URL + backend-only service-role key.
- [x] Batch capped at 100, lookback at 24 hours, horizon at 7 days; production worker explicitly blocked.
- [x] Added per-claim failure isolation, retry requeue with opaque `worker_runtime_error`, stale-claim fallback, aggregate-only reports, and scheduler-friendly exit codes.
- [x] Reports/CLI exclude IDs, clinical content, push tokens, provider payloads, prompts/model output, and raw exceptions.
- [x] GitHub Actions passed on `2b310c9`: Ruff lint/format, 63 safety tests with 95.43% coverage, 257 full-suite tests with 21 expected staging skips, Docker build, every migration rebuilt from zero, PostgREST refresh, two ephemeral synthetic users, 21/21 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 13 — guarded Expo Push adapter ahead of the unresolved 30% gate

- [x] Added `expo` beside the existing network-free `mock` notification transport while keeping `mock` as the default.
- [x] Added backend-only `ExpoPushTransport` using the fixed Expo Push Service send endpoint; arbitrary provider URLs are not accepted.
- [x] Added backend-only Expo access-token configuration as `SecretStr`; selecting Expo requires the access token and production reminder-worker enablement remains blocked.
- [x] Restricted Expo registrations to Android/iOS and validated current `ExpoPushToken[...]` plus legacy `ExponentPushToken[...]` token shapes at both API-model and database boundaries.
- [x] Kept raw Expo tokens service-only and preserved SHA-256 fingerprint/advisory locking and cross-user active-token conflict protection.
- [x] Restricted provider payloads to recipient token, generic title `Janani reminder`, generic body `You have a reminder in Janani.`, and opaque `delivery_id` routing data only.
- [x] Added retryable handling for network/timeouts, HTTP 429/5xx, `MessageRateExceeded`, and `TOO_MANY_REQUESTS`.
- [x] Added terminal opaque handling for known non-transient provider errors including unregistered devices, message size, sender/project mismatch, invalid credentials, and authorization rejection.
- [x] Unknown/malformed provider responses fail retryably under the existing bounded queue policy; raw Expo messages and exception strings are never propagated into worker results.
- [x] Added migration `20260808020000_expo_push_transport.sql` without opening the raw notification-device table to authenticated clients.
- [x] Added provider tests using `httpx.MockTransport`; CI performs no real Expo network request or notification delivery.
- [x] Added clean local-Supabase validation for safe Expo registration metadata, raw-table denial, service-only token visibility, cross-user token conflict, web/malformed-token rejection, and revocation.
- [x] GitHub Actions passed on `63f5953`: Ruff lint/format, 63 safety tests with 95.43% safety-module coverage, 279 full-suite tests with 22 expected staging skips, Docker build, every migration including the Expo migration rebuilt from zero, PostgREST schema refresh, two ephemeral synthetic users, and 22/22 local integration tests.
- [x] Expo send tickets are intentionally not treated as final device-delivery receipts; ticket persistence/receipt polling is deferred to the next provider phase.
- [x] Official progress intentionally remains 29%; this engineering-ahead work does not satisfy clinical authorisation, hosted staging, or production launch gates.

## Current limitations

- No real licensed clinician has been onboarded; no real reviewer credential/attestation/identity evidence has been stored or verified.
- Governance administration remains disabled by default and only synthetically validated.
- No warning rule or English/Telugu escalation wording has real licensed-clinician approval; all current candidates still contain development-placeholder provenance.
- The 63 safety cases/review packets and rollback rehearsal are synthetic engineering evidence, not clinical validation or real-world evidence.
- Structured pregnancy, lifecycle, attachment, reminder, notification, worker, and Expo adapter services are synthetic/local only and do not interpret clinical meaning.
- No real patient data may be processed.
- Existing hosted Janani Supabase has not been modified; no dedicated hosted staging project or paid branch exists.
- Expo adapter code exists, but production push delivery remains disabled and no real provider request is made in CI.
- No deployed scheduler, cron service, container job, or always-on reminder worker exists.
- Expo push tickets/receipt IDs are not persisted and no receipt-polling worker exists.
- `DeviceNotRegistered` is classified terminal, but automatic backend device revocation from receipts is not implemented yet.
- No provider receipt retention/cleanup or production provider observability exists.
- Notification rendering remains generic and forbids clinical lock-screen details.
- No medication-adherence scoring or dose-taking confirmation exists; `sent` means transport acceptance, not medication use.
- No Gemini adapter or hosted LLM is connected; no hosted-model response schema/output-policy validator exists.
- No OCR/extraction worker process exists; only persistence/integrity/extraction contracts exist.
- No approved clinical-content ingestion, embeddings, or RAG retrieval exists.
- Account deletion still lacks controlled deletion execution, Storage cleanup, session revocation, and retention-policy execution.
- No caregiver/partner permissions model is implemented.
- The service is not deployable for clinical use.

## Next milestone: 29–30% — real clinical authorisation and hosted staging gate

- Approve reviewer-onboarding, conflict-of-interest, credential-verification, evidence-retention, and governance operating procedures.
- Verify real obstetrician, clinical-safety, and Telugu-language reviewer credentials outside source control.
- Replace development placeholders with current clinician-reviewed sources and exact sections.
- Obtain actual human review/approval of every predicate, severity, rationale, applicability boundary, and bilingual escalation message.
- Obtain independently authored/reviewed expected outcomes beyond the implementation team.
- Rehearse incident ownership, reviewer deactivation, release retirement, and emergency rollback under approved procedures.
- Repeat governance/reviewer/release/ruleset/rehearsal validation in isolated hosted staging using synthetic data only.
- Document production access control, incident ownership, privacy, legal, security, and clinical launch sign-off.
- Keep every clinical rule inactive until every real-world authorization and launch gate passes.

Engineering may continue building isolated synthetic-only components ahead of this gate, but official verified progress must not advance past 29% until these external requirements are satisfied. The next notification-provider engineering phase may add Expo ticket/receipt lifecycle handling, bounded receipt polling, automatic stale-device revocation, and opaque provider observability without enabling production delivery.

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

### 2026-08-08 — 29% + Phase 13 engineering ahead

Built and verified the guarded Expo Push adapter on `phase-13/expo-push-adapter` while intentionally leaving official progress at 29%. Expo registration is restricted to Android/iOS and validated token shapes; raw tokens and access credentials remain backend-only. Provider payloads retain the existing generic lock-screen copy and opaque `delivery_id` only. Network/429/5xx/rate-limit failures are retryable, known permanent ticket failures become short terminal machine codes, and raw provider messages/exceptions are discarded. CI provider tests use `httpx.MockTransport`, so no real Expo notification is sent. Migration `20260808020000_expo_push_transport.sql` rebuilt cleanly with all prior migrations, and local integration confirmed safe registration, raw-table denial, service-only token access, cross-user conflict protection, invalid/web rejection, and revocation. GitHub Actions passed on `63f5953`: 63 safety tests at 95.43% coverage, 279 full-suite tests, 22 expected staging skips, Docker build, and 22/22 local integration tests. No real patient data, hosted Supabase change, deployed scheduler, production push, receipt polling, clinician approval, OCR worker, or hosted LLM was introduced.

### 2026-08-08 — 29% + Phase 12 engineering ahead

Built and verified the bounded backend-only run-once reminder worker on `phase-12/reminder-worker-runtime`. Each invocation captures one UTC-normalized clock, materializes a bounded window, claims a capped batch, dispatches through the generic mock transport, completes queue outcomes, emits aggregate-only metrics, and exits. GitHub Actions passed on `2b310c9`: 63 safety tests at 95.43% coverage, 257 full-suite tests, 21 expected staging skips, Docker build, every migration rebuilt from zero, and 21/21 local integration tests.

### 2026-08-08 — 29% + Phase 11 engineering ahead

Built and verified private notification devices and provider-neutral transport on `phase-11/notification-transport-devices`. GitHub Actions passed on `027b60b`: 63 safety tests at 95.43% coverage, 231 full-suite tests, 21 expected staging skips, Docker build, and 21/21 local integration tests.

### 2026-08-08 — 29% + Phase 10 engineering ahead

Built and verified deterministic reminder delivery, service-only queue claiming/retry, and neutral response events on `phase-10/reminder-delivery-events`. GitHub Actions passed on `65f7e7c`: 212 full-suite tests and 19/19 local integration tests.

### 2026-08-07 — 29% + Phase 9 engineering ahead

Built and verified pregnancy completion lifecycle, explicit reminders, and secure attachment upload integrity on `phase-9/lifecycle-reminders-upload-integrity`. GitHub Actions passed on `bf1ddeb`: 194 full-suite tests and 18/18 local integration tests.

### 2026-08-07 — 29% + Phase 8 engineering ahead

Built and verified structured pregnancy timeline/observation/encounter/attachment metadata without clinical interpretation on `phase-8/pregnancy-services-attachments`. GitHub Actions passed on `8914d80`: 183 full-suite tests and 15/15 local integration tests.

### 2026-08-07 — 29%

Built and verified pre-clinical review packets, 63-case challenge datasets, immutable evidence, and synthetic rollback rehearsal on `phase-7/clinical-review-rehearsal`. GitHub Actions passed on `de9b594`.

### 2026-08-05 — 27%

Built and verified reviewer administration and executable synthetic safety validation datasets on `phase-6/reviewer-admin-validation-datasets`. GitHub Actions passed on `dcda56f`.

### 2026-08-04 — 25%

Built and verified atomic deterministic safety rulesets on `phase-5/atomic-ruleset-activation`. GitHub Actions passed on `59c7c10`.

### 2026-08-04 — 22%

Built and verified clinical safety governance foundation on `phase-4/clinical-safety-governance`. GitHub Actions passed on `148565f`.

### 2026-08-04 — 18%

Completed free authenticated-persistence validation with isolated local Supabase; hosted Janani remained untouched. GitHub Actions passed on `5b4210a`.

### 2026-08-04 — 14%

Built initial data, consent, attachment, and Context Assembly Engine foundation on `phase-2/data-context-foundation`. GitHub Actions passed on `8686255`.

### 2026-08-04 — 10%

Completed free-first engineering foundation and provider-neutral architecture. GitHub Actions passed on `5c283d5`.
