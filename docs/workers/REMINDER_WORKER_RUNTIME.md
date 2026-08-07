# Phase 12 reminder worker runtime

This phase adds a backend-only, run-once execution boundary for Janani reminder delivery. It is synthetic-only engineering ahead of the unresolved real clinical-authorisation gate and does not make Janani clinically deployable.

## Execution model

A scheduler may invoke:

```text
janani-reminder-worker
```

Each invocation performs one bounded cycle and exits. The worker does not create an internal infinite loop, daemon thread, public HTTP worker route, or background task inside the API process.

The cycle is:

1. capture one timezone-aware worker clock and normalize it to UTC;
2. materialize reminder occurrences in a configured bounded lookback/horizon window;
3. claim at most the configured batch size through the existing service-role queue RPC;
4. resolve active notification destinations only through the exact `delivery_id + claim_token` service-role RPC;
5. dispatch generic notification envelopes through the configured transport;
6. complete each queue claim using the existing deterministic retry/terminal rules;
7. emit an aggregate run report and exit.

Phase 12 supports `mock` transport only. It performs no provider network request.

## Default gates

The worker is disabled by default:

```text
JANANI_REMINDER_WORKER_ENABLED=false
JANANI_REMINDER_WORKER_TRANSPORT=mock
JANANI_REMINDER_WORKER_BATCH_SIZE=50
JANANI_REMINDER_WORKER_MATERIALIZATION_LOOKBACK_MINUTES=15
JANANI_REMINDER_WORKER_MATERIALIZATION_HORIZON_MINUTES=1440
```

When enabled, a Supabase URL and backend-only service-role key are required. The service-role key must never be bundled into the mobile app or browser, committed to source control, or emitted to logs/analytics.

This phase explicitly rejects worker enablement in `production`. Removing that block requires the later production launch gate, not merely a configuration change.

## Failure isolation

Transport/destination infrastructure failure for one claimed job does not abort the remaining batch. The worker attempts to complete that claim as retryable using the opaque machine code `worker_runtime_error`. If even that completion fails, the job remains protected by the existing stale-claim recovery path and the aggregate report records a requeue failure count.

Raw exception messages are not included in worker reports or CLI error output.

## Output contract

Successful/degraded runs contain aggregate operational metadata only:

- run timestamp and materialization window;
- number of jobs materialized and claimed;
- sent/retryable/terminal job counts;
- runtime-error and requeue-failure counts.

The report intentionally excludes:

- patient/user identifiers;
- delivery identifiers;
- medication names or dose text;
- symptoms or clinical observations;
- appointment details;
- report/extraction content;
- notification push tokens/fingerprints;
- provider responses;
- prompts/model output;
- raw exceptions.

Exit codes are scheduler-friendly:

- `0`: completed without worker-runtime errors;
- `1`: degraded or runtime failure;
- `2`: worker disabled or invalid configuration.

A retryable notification outcome is a valid queue outcome and does not by itself make the worker process degraded.

## Still excluded

- Expo Push, FCM, APNs, email, SMS, WhatsApp, or another hosted provider;
- provider credentials;
- a deployed scheduler or always-on worker service;
- clinical interpretation or adherence inference;
- real patient data;
- hosted Janani Supabase changes;
- clinician approval or production launch readiness.
