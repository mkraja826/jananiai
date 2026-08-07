# Janani AI Progress — 0% to 100%

This file is the permanent source of truth for Janani AI engineering progress. Update it after every meaningful architecture, code, database, safety, testing, deployment, failure/fix, or milestone change. Never store secrets or patient data here.

## Current verified progress: 29%

Updated: 2026-08-08
Branch: `phase-12/reminder-worker-runtime`
Latest verified engineering implementation commit: `2b310c9`
Draft PR: `#12`
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
- [x] Added attachment extraction/confirmation states.
- [x] Blocked extracted text from AI context until extraction is complete and user-confirmed.
- [x] Added task-specific context inclusion/exclusion and budgets.
- [x] Added deterministic Context Assembly Engine and provider-neutral `JananiLLMRequest`.
- [x] Added synthetic-only context assembly API and minimal context auditing.
- [x] Added initial Supabase schema, private Storage, owner RLS, and cross-owner relationship guards.
- [x] GitHub Actions passed on `8686255`: 12 safety tests, 92.50% safety coverage, 40 full-suite tests, Docker build.

## Phase 3 — authenticated persistence and free local RLS validation

- [x] Added Supabase bearer-token verification and authenticated request identity.
- [x] Added RLS-scoped PostgREST persistence using publishable key + caller bearer token.
- [x] Added authenticated stored-context assembly.
- [x] Added minimal safety/context audit RPCs.
- [x] Added attachment extraction transitions and service-role-only extraction persistence.
- [x] Added account-deletion request foundation.
- [x] Added explicit table grants/revokes and owner-readable audit policies.
- [x] Added isolated local-Supabase CI using two ephemeral synthetic users.
- [x] Verified owner isolation, append-only consent, private Storage, RPC ownership, extraction separation, and deletion-request privacy.
- [x] GitHub Actions passed on `5b4210a`: quality green and 9/9 local integration tests.

## Phase 4 — clinical safety governance foundation

- [x] Added distinct obstetrician and clinical-safety approval requirements.
- [x] Added reviewer identity, jurisdiction, license reference, verification, expiry, source provenance, exact-section, applicability, and review-expiry contracts.
- [x] Added English/Telugu escalation wording contracts.
- [x] Added immutable review candidates and candidate digests.
- [x] Added release approval, activation, retirement, replacement, rollback, and append-only governance events.
- [x] Marked all current safety candidates as development-placeholder provenance so real activation remains impossible.
- [x] Denied ordinary end-user access to governance tables/RPCs.
- [x] GitHub Actions passed on `148565f`: 27 safety tests, 96.87% coverage, 80 full-suite tests, 10 expected staging skips, Docker build, 10/10 local integration tests.

## Phase 5 — atomic deterministic safety rulesets

- [x] Made the complete safety ruleset the deployable unit.
- [x] Added exact required-rule manifests and immutable member digests.
- [x] Rejected incomplete, duplicate, altered, expired, extra, or invalid manifests.
- [x] Added service-role-only approval/activation/replacement/rollback RPCs.
- [x] Enforced one active ruleset and exact active-release consistency.
- [x] Added drift detection and PostgREST RPC discovery checks.
- [x] Added two-generation activation/replacement/rollback validation.
- [x] GitHub Actions passed on `59c7c10`: 34 safety tests, 97.44% coverage, 94 full-suite tests, 12 expected staging skips, Docker build, 12/12 local integration tests.

## Phase 6 — reviewer administration and validation datasets

- [x] Added trusted governance roles sourced only from Supabase `app_metadata`.
- [x] Added reviewer onboarding, credential reverification, controlled deactivation, conflict-of-interest attestation, and opaque evidence references.
- [x] Added disabled-by-default backend governance administration APIs.
- [x] Added append-only reviewer lifecycle events and active-release deactivation protection.
- [x] Added 35 synthetic validation cases across true-positive, true-negative, boundary, interaction, and regression categories.
- [x] Added fail-closed validation-dataset checks and per-rule reporting.
- [x] GitHub Actions passed on `dcda56f`: 49 safety tests, 96.33% coverage, 149 full-suite tests, 13 expected staging skips, Docker build, 13/13 local integration tests.

## Phase 7 — pre-clinical review packets and rollback rehearsal

- [x] Expanded deterministic validation to 63 synthetic cases across nine categories per rule.
- [x] Added ambiguity, missing-data, adversarial, and cross-rule challenge cases.
- [x] Added immutable pre-clinical review packets bound to exact candidate/dataset digests.
- [x] Required obstetrician, clinical-safety, and language-review roles in review packets.
- [x] Kept packets non-eligible while placeholder sources remain.
- [x] Added synthetic emergency rollback rehearsal with six required evidence steps.
- [x] Added private append-only review/rehearsal evidence persistence.
- [x] Found and fixed PostgreSQL `42702` ambiguous JSON-value extraction during real local validation.
- [x] GitHub Actions passed on `de9b594`: 63 safety tests, 95.43% coverage, 168 full-suite tests, 14 expected staging skips, Docker build, 14/14 local integration tests.
- [x] Official progress reached 29% and is intentionally gated there pending real-world authorization.

## Phase 8 — structured pregnancy engineering ahead of the unresolved 30% gate

- [x] Added structured pregnancy episode dating, provenance, status, and lifecycle contracts without clinical interpretation.
- [x] Added typed weight, blood-pressure, lab-result, and encounter records.
- [x] Made observation/encounter corrections append-only through supersession.
- [x] Added a factual chronological timeline combining observations, encounters, appointments, and attachment metadata.
- [x] Timeline remains neutral and does not label values normal, abnormal, reassuring, dangerous, or diagnostic.
- [x] Added attachment document date, label, capture source, size, and SHA-256 metadata without extracted text in timeline summaries.
- [x] Added authenticated pregnancy timeline APIs and owner-scoped persistence.
- [x] GitHub Actions passed on `8914d80`: 63 safety tests, 95.43% coverage, 183 full-suite tests, 15 expected staging skips, Docker build, 15/15 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 9 — lifecycle, explicit reminders, and upload integrity ahead of the unresolved 30% gate

- [x] Added append-only pregnancy completion events and superseding corrections.
- [x] First completion atomically closes the active pregnancy episode while preserving factual history.
- [x] Added medication reminder schedules using explicit user-selected local time, IANA timezone, date range, and weekdays.
- [x] Medication reminder timing is never inferred from dose text, prescription text, OCR, rules, or an LLM.
- [x] Added explicit appointment reminder lead times.
- [x] Added short-lived owner-scoped attachment upload intents.
- [x] Restricted uploads to PDF/JPEG/PNG/WEBP with a 20 MiB application limit and required expected SHA-256.
- [x] Finalization verifies exact private Storage object, MIME type, and byte size.
- [x] Closed direct authenticated attachment-row writes and made finalized object paths immutable.
- [x] Added service-only SHA-256 verification and blocked extraction until integrity is verified.
- [x] Required verified integrity + completed extraction + user confirmation before extracted text becomes context-eligible.
- [x] GitHub Actions passed on `bf1ddeb`: 63 safety tests, 95.43% coverage, 194 full-suite tests, 16 expected staging skips, Docker build, 18/18 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 10 — deterministic reminder delivery and neutral response events ahead of the unresolved 30% gate

- [x] Added privacy-minimised `reminder_delivery_jobs` containing opaque identifiers, timing, status, attempts, claim metadata, and short machine failure codes only.
- [x] Excluded medication names, doses, symptoms, report content, prompts, model output, and notification message bodies from delivery jobs.
- [x] Added deterministic medication occurrence materialization from explicit schedules and appointment occurrences from explicit appointment time minus explicit lead minutes.
- [x] Used PostgreSQL IANA timezone data for local-time conversion.
- [x] Capped materialization windows and added idempotent unique occurrence indexes.
- [x] Added service-only materialize/claim/complete RPCs with `FOR UPDATE SKIP LOCKED`, opaque claim tokens, stale-claim recovery, explicit worker clock, and five-attempt retry cap.
- [x] Added cancellation of future jobs when reminder/source records become invalid.
- [x] Added neutral append-only response events: `opened`, `acknowledged`, `dismissed`, and explicit `remind_later`.
- [x] Deliberately excluded `taken`, `dose_completed`, `adherent`, and similar medication-taking claims.
- [x] Added idempotent client-event IDs and one-off exact-time `remind_later` occurrences.
- [x] Added owner APIs for deliveries/responses without exposing claim tokens or worker failure metadata.
- [x] GitHub Actions passed on `65f7e7c`: 63 safety tests, 95.43% coverage, 212 full-suite tests, 19 expected staging skips, Docker build, all migrations rebuilt, 19/19 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 11 — private notification devices and provider-neutral transport ahead of the unresolved 30% gate

- [x] Added private `notification_devices` lifecycle registry with backend-only push-token storage.
- [x] Raw notification-device table remains inaccessible to `anon` and `authenticated`; only `service_role` has direct table access.
- [x] Added identity-derived register/list/revoke RPCs without caller-supplied user IDs.
- [x] Kept raw push tokens and token fingerprints out of authenticated API/RPC responses.
- [x] Wrapped push tokens in `SecretStr` at Python boundaries.
- [x] Added atomic same-installation token rotation and SHA-256 fingerprint/advisory locking to prevent cross-user active-token races.
- [x] Added service-only destination lookup bound to exact active `delivery_id + claim_token` and matching synthetic/real provenance.
- [x] Added provider-neutral `NotificationTransport` and deterministic network-free `MockNotificationTransport`.
- [x] Added generic lock-screen envelope: `Janani reminder` / `You have a reminder in Janani.` with only opaque `delivery_id` routing data.
- [x] Excluded medication/dose/symptom/appointment/report/diagnosis/treatment/prompt/model content from notification bodies.
- [x] Added deterministic dispatch semantics for sent, retryable, and terminal outcomes.
- [x] Added authenticated device APIs and kept worker dispatch off public routes.
- [x] GitHub Actions passed on `027b60b`: 63 safety tests, 95.43% coverage, 231 full-suite tests, 21 expected staging skips, Docker build, all migrations rebuilt, 21/21 local integration tests.
- [x] Official progress intentionally remained 29%.

## Phase 12 — bounded run-once reminder worker runtime ahead of the unresolved 30% gate

- [x] Added backend-only `janani-reminder-worker` run-once CLI command.
- [x] Each invocation performs one bounded materialization, claim, dispatch, completion cycle and exits.
- [x] Added no internal infinite loop, daemon thread, API background task, or public worker route.
- [x] Captures one timezone-aware execution clock and normalizes it to UTC.
- [x] Worker is disabled by default.
- [x] Enabled worker requires Supabase URL + backend-only service-role key.
- [x] Worker batch size is capped at 100.
- [x] Materialization lookback is capped at 24 hours and horizon at 7 days.
- [x] Production worker enablement is explicitly blocked at this phase.
- [x] Transport remains `mock` only and performs no hosted-provider network request.
- [x] Added per-claim failure isolation so one destination/infrastructure failure does not abort the remaining batch.
- [x] Failed claims are requeued through the existing deterministic retry path using opaque `worker_runtime_error` when possible.
- [x] If requeue persistence itself fails, the existing stale-claim recovery remains the fallback.
- [x] Added privacy-minimised run reports containing only timestamps/windows and aggregate materialized/claimed/sent/retryable/terminal/runtime-error/requeue-failure counts.
- [x] Reports and CLI failures exclude user IDs, delivery IDs, medication/dose/symptom/appointment/report content, push tokens, provider payloads, prompts/model outputs, and raw exceptions.
- [x] Added scheduler-friendly exit codes: `0` completed, `1` degraded/runtime failure, `2` disabled/invalid configuration.
- [x] Added adversarial runtime, configuration, timezone, failure-isolation, batch-bound, and CLI privacy tests.
- [x] GitHub Actions passed on `2b310c9`: Ruff lint/format, 63 safety tests with 95.43% safety-module coverage, 257 full-suite tests with 21 expected staging skips, Docker build, every migration rebuilt from zero, PostgREST schema refresh, two ephemeral synthetic users, and 21/21 local integration tests.
- [x] Official progress intentionally remains 29%; this engineering-ahead work does not satisfy the real clinical-authorisation or hosted-staging gate.

## Current limitations

- No real licensed clinician has been onboarded through the reviewer administration flow.
- No real reviewer credential, attestation, or identity-evidence document has been stored or verified.
- Governance administration remains disabled by default and has only synthetic validation.
- No warning rule has been reviewed or approved by a licensed clinician.
- Every current safety candidate contains development-placeholder provenance and cannot be activated.
- Current English/Telugu escalation wording remains development-only and not clinically approved.
- The 63 safety validation cases and review packets are synthetic engineering evidence, not clinical validation or real-world safety evidence.
- Rollback rehearsal evidence is synthetic/local only.
- Structured pregnancy, lifecycle, attachment, reminder, notification, and worker services are validated only with synthetic/local data and do not interpret clinical meaning.
- No real patient data may be processed.
- Existing hosted Janani Supabase has not been modified.
- No dedicated hosted staging project or paid Supabase branch exists; validation uses isolated local Docker infrastructure.
- A private notification-device registry and provider-neutral transport foundation exist, but only the deterministic local `mock` transport is implemented.
- No Expo Push, FCM, APNs, email, SMS, WhatsApp, or other hosted notification transport is connected.
- Notification rendering is intentionally generic and forbids clinical lock-screen details.
- A run-once worker runtime now exists, but no scheduler, cron service, container job, or always-on worker is deployed.
- Production worker enablement remains explicitly blocked.
- No medication-adherence scoring or dose-taking confirmation exists; `sent` means only destination acceptance and `acknowledged` means only application interaction.
- No Gemini adapter or hosted LLM is connected.
- No hosted-model response schema/output-policy validator is implemented.
- No OCR/extraction worker process is implemented; only persistence/integrity/extraction contracts exist.
- No approved clinical-content ingestion, embeddings, or RAG retrieval is implemented.
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

Engineering may continue building isolated synthetic-only components ahead of this gate, but official verified progress must not advance past 29% until these external requirements are satisfied.

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

### 2026-08-08 — 29% + Phase 12 engineering ahead

Built and verified the bounded backend-only run-once reminder worker on `phase-12/reminder-worker-runtime` while intentionally leaving official progress at 29%. Each invocation captures one UTC-normalized clock, materializes a bounded window, claims a capped batch, dispatches through the existing generic mock notification transport, completes queue outcomes, emits aggregate-only operational metrics, and exits. The worker is disabled by default, requires a backend-only service-role key when enabled, and is explicitly blocked in production. Per-claim infrastructure failures are isolated and requeued with opaque machine codes without leaking raw exceptions or clinical/token data. GitHub Actions passed on `2b310c9`: 63 safety tests with 95.43% coverage, 257 full-suite tests, 21 expected staging skips, Docker build, every migration rebuilt from zero, and 21/21 local integration tests. No real patient data, hosted Supabase change, hosted notification provider, deployed scheduler, clinician approval, OCR worker, or hosted LLM was introduced.

### 2026-08-08 — 29% + Phase 11 engineering ahead

Built and verified the private notification-device and provider-neutral transport foundation on `phase-11/notification-transport-devices`. Raw tokens are service-only; authenticated callers manage safe device metadata through identity-derived RPCs. Claim-bound lookup, token rotation/revocation, cross-user token protection, generic notification content, and mock dispatch were verified. GitHub Actions passed on `027b60b`: 63 safety tests with 95.43% coverage, 231 full-suite tests, 21 expected staging skips, Docker build, and 21/21 local integration tests.

### 2026-08-08 — 29% + Phase 10 engineering ahead

Built and verified deterministic reminder delivery, service-only queue claiming/retry mechanics, and neutral response events on `phase-10/reminder-delivery-events`. GitHub Actions passed on `65f7e7c`: 63 safety tests with 95.43% coverage, 212 full-suite tests, 19 expected staging skips, Docker build, and 19/19 local integration tests.

### 2026-08-07 — 29% + Phase 9 engineering ahead

Built and verified pregnancy completion lifecycle, explicit reminder schedules, and secure attachment upload-integrity workflow on `phase-9/lifecycle-reminders-upload-integrity`. GitHub Actions passed on `bf1ddeb`: 194 full-suite tests and 18/18 local integration tests.

### 2026-08-07 — 29% + Phase 8 engineering ahead

Built and verified structured pregnancy timeline/observation/encounter/attachment metadata services without clinical interpretation on `phase-8/pregnancy-services-attachments`. GitHub Actions passed on `8914d80`: 183 full-suite tests and 15/15 local integration tests.

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
