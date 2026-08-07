# Phase 13 — Expo Push adapter boundary

## Status

Synthetic-only engineering ahead of the unresolved 29→30% clinical-authorisation gate.
Official verified progress remains 29%.

This phase adds the first real push-provider adapter boundary. It does not deploy a scheduler, enable production delivery, introduce real patient data, or change the hosted Janani Supabase project.

## Provider boundary

The backend can select `expo` as a reminder worker transport only when all existing worker requirements are satisfied and a backend-only Expo push access token is configured.

The adapter uses the Expo Push Service send endpoint and sends one message at a time. The outbound message is deliberately restricted to:

- recipient Expo push token,
- title `Janani reminder`,
- body `You have a reminder in Janani.`,
- opaque `delivery_id` routing data.

Medication names, dose text, symptoms, appointment details, report content, diagnoses, treatment, prompts, model output, user IDs, and other clinical content are not added to provider payloads.

## Token registration

`notification_devices.transport` now permits `mock` and `expo` only.

Expo registration rules:

- Android and iOS only,
- web is rejected,
- token must have an Expo/Exponent push-token shape,
- raw token remains backend-only,
- authenticated callers receive safe device metadata only,
- active cross-user token conflicts remain serialized by fingerprint advisory locking.

## Provider response classification

The adapter intentionally exposes only short machine failure codes.
Raw provider response messages and exception strings are discarded.

Retryable outcomes include:

- HTTP 429,
- HTTP 5xx,
- network/timeouts,
- `MessageRateExceeded`,
- `TOO_MANY_REQUESTS`,
- malformed/unknown provider responses.

Terminal outcomes include known non-transient ticket errors such as:

- `DeviceNotRegistered`,
- `MessageTooBig`,
- `MismatchSenderId`,
- `InvalidCredentials`,
- project/batch mismatch errors,
- provider authorization rejection.

The existing reminder queue still owns the bounded retry/backoff policy and five-attempt cap.

## Security

- Expo access token is represented as `SecretStr`.
- The access token is never part of API responses, worker reports, or progress logs.
- The provider URL is fixed in code; it is not a user-configurable arbitrary endpoint.
- Production reminder worker enablement remains blocked by application configuration.
- `mock` remains the default transport and performs no network request.
- Expo provider tests use `httpx.MockTransport`; CI never sends a real push notification.

## Known limitation and next boundary

An Expo send ticket confirms that Expo accepted the notification for processing; it is not a final device-delivery receipt. Expo recommends checking push receipts after sending. This phase deliberately does not persist provider ticket IDs or run receipt polling yet.

Before any real push rollout, the next provider milestone must add:

- backend-only ticket/receipt persistence,
- bounded receipt polling,
- `DeviceNotRegistered` device revocation handling,
- receipt retention/cleanup,
- provider observability using opaque counts/codes only,
- synthetic hosted-staging validation.

No production push delivery is approved by this phase.
