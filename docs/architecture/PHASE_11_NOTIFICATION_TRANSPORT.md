# Phase 11 — Notification transport and device lifecycle

This phase connects the deterministic reminder-delivery queue to a provider-neutral notification transport without adding clinical content to push payloads or enabling real-patient use.

## Boundaries

- Device registrations are private backend data. Authenticated clients manage them only through RPCs and never read raw push tokens back.
- Push tokens are treated as secrets and are excluded from model repr/serialization where possible.
- Delivery notification content is generic: a Janani reminder is available in the app. Medication names, dose text, symptoms, appointments, reports, prompts, model output, and other clinical details are never placed in transport payloads.
- A delivery UUID may be carried as an opaque application routing identifier.
- The provider adapter is neutral. The default development provider is mock-only.
- No Expo Push, FCM, APNs, email, SMS, WhatsApp, or other hosted notification provider is connected in this phase.
- No real patient data is enabled.
- Hosted Janani Supabase remains unchanged.

## Device lifecycle

Each installation registers a client-generated installation UUID, platform, transport kind, and push token through an authenticated RPC. The database derives `auth.uid()` and stores the raw token only in a private service-readable table. The RPC returns only safe metadata.

Re-registering the same installation rotates the token atomically. Revocation disables the installation without deleting history. A service-only delivery destination RPC returns active destinations for a claimed user.

## Dispatch flow

1. Materialize reminder occurrences using the Phase 10 deterministic scheduler.
2. Claim due queue rows using the existing service-only queue claim RPC.
3. Load active notification destinations for the claimed user.
4. Render a generic content envelope with no clinical details.
5. Send through the configured provider-neutral transport.
6. If at least one destination succeeds, complete the reminder delivery as `sent`.
7. If all attempts are retryable, complete as `retryable_failure`.
8. If there are no active destinations, complete as a retryable `no_active_destination` outcome so device registration can recover before the queue reaches its bounded five-attempt cap.
9. If all failures are terminal, complete as `terminal_failure`.

The worker never marks medication as taken and does not interpret clinical meaning.

## Security properties

- `anon` and `authenticated` receive no table grants on the raw-token table.
- Device registration and revocation RPCs derive the user identity from `auth.uid()`.
- Service-only destination lookup is not executable by end users.
- Cross-user installation mutation is impossible because the caller never supplies `user_id`.
- Raw token values do not appear in user-facing API responses, reminder jobs, response events, audit rows, or transport-result records.
- Dispatch attempts are not persisted with raw notification body or token content.

## Testing

Phase 11 must prove with synthetic data that:

- two users cannot manage each other's device registrations;
- authenticated direct table reads/writes are denied;
- re-registration rotates a token for the same installation;
- revocation removes the destination from worker lookup;
- the mock transport receives only generic content and opaque IDs;
- one successful destination marks a job sent;
- no destination creates a bounded retryable outcome;
- terminal-only failures mark the job failed;
- raw tokens never enter public API responses or delivery-job rows.
