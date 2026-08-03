# Authenticated Persistence Architecture

Status: Synthetic development foundation
Date: 2026-08-04
Branch: `phase-3/authenticated-persistence`

## Request flow

```text
Janani mobile app
  -> Supabase Auth access token
  -> FastAPI bearer-token dependency
  -> Supabase Auth /auth/v1/user validation
  -> verified user ID + original access token
  -> RLS-scoped PostgREST client
  -> user-owned records only
  -> deterministic safety engine
  -> Context Assembly Engine
  -> privacy-minimised audit RPCs using auth.uid()
```

## Why FastAPI validates the token remotely first

The initial implementation calls Supabase Auth's user endpoint with the publishable key and bearer token. This fails closed and works regardless of whether the project currently uses legacy symmetric signing or asymmetric signing keys. A later optimisation may verify asymmetric tokens locally against the project JWKS while retaining remote validation compatibility.

## Identity propagation

The verified identity contains:

- Supabase user UUID;
- role;
- optional email for request identity only;
- bearer token stored as a secret field and excluded from serialization;
- a synthetic flag for local development.

The mobile client cannot choose a database `user_id`. PostgREST receives the verified bearer token, and database policies derive identity from `auth.uid()`.

## Stored-context endpoint

`POST /v1/context/assemble-stored` accepts only:

- task;
- user question;
- language;
- selected attachment and medication IDs;
- structured safety inputs;
- context budget;
- synthetic-data declaration.

The backend loads profile, active pregnancy, consent history, medications, appointments, attachment metadata, and latest extraction versions through RLS. It does not accept the complete health history in the request body.

## Internal writes

Authenticated security-definer RPCs write:

- safety audit events;
- context-selection audit events;
- attachment confirmation decisions;
- account deletion requests.

Each function derives the caller from `auth.uid()`. Raw questions, symptom notes, extracted report text, prompts, and model responses are excluded from audit payloads.

## Account deletion foundation

The current endpoint creates a deletion request. It does not immediately destroy health records. A later controlled worker must:

1. lock the request;
2. revoke active sessions where appropriate;
3. delete private storage objects;
4. delete or anonymise records according to the approved retention policy;
5. preserve only legally required minimal audit evidence;
6. mark the request complete.

## Staging validation

The repository includes an opt-in two-user RLS test. It runs only when dedicated synthetic staging variables are present. No migration in this branch has been executed against the existing Janani Supabase project, and no real data is permitted.

## Remaining blockers

- dedicated staging project or paid Supabase branch;
- migration execution and advisor review;
- complete two-user tests across every table and storage operation;
- durable extraction-worker authentication;
- session revocation and deletion worker;
- caregiver access model;
- clinician-approved safety rules and clinical RAG;
- hosted-model output validation.
