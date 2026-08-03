# ADR 0002: Context assembly with Gemini-first hosted generation

Status: Accepted
Date: 2026-08-04

## Context

Janani collects structured pregnancy information, symptoms, entered prescriptions, appointments, reports, preferences, and future caregiver data. A hosted language model can organise and explain this information, but sending an entire user history or forwarding raw attachments creates privacy, cost, relevance, and safety problems.

Janani therefore needs to own the data-selection and safety process while using a hosted model only for controlled language generation.

## Decision

1. Janani's primary intelligence layer will be a Context Assembly Engine, not a newly trained general-purpose LLM.
2. The deterministic safety engine runs before any hosted-model request.
3. The Context Assembly Engine selects the minimum relevant confirmed data for the current task.
4. Attachments are privately stored, extracted, confidence-checked, and confirmed where required before relevant sections are included.
5. Approved clinical RAG content is added separately from user records and remains traceable.
6. One typed `JananiLLMRequest` is constructed with task, relevant user context, attachment references/selected text, approved knowledge, response policy, language, and token budget.
7. The first planned hosted provider is Google Gemini through the existing provider-independent adapter, using stable model configuration `gemini-3.5-flash` for synthetic development.
8. The deterministic mock provider remains the default for local and automated tests.
9. Gemini unpaid usage is restricted to synthetic data and fake attachments.
10. Real health data requires a paid/private-data phase, privacy and legal review, consent and access controls, auditability, and clinical release gates.
11. All hosted outputs must pass structured schema validation and Janani policy checks before reaching the user.
12. The provider remains replaceable; Claude, OpenAI, Grok, or another approved provider may be evaluated later without changing Janani business logic.

## Request boundary

The mobile application never calls Gemini directly. The backend owns credentials and request construction.

```text
Mobile -> FastAPI -> safety -> context assembly -> RAG -> provider adapter -> validation -> Mobile
```

## Consequences

### Positive

- Janani controls relevance, privacy, safety, and auditability.
- Fewer unnecessary tokens and lower future model cost.
- Reduced exposure of unrelated health information.
- Provider lock-in is limited.
- The same typed request can be tested with mock, Gemini, and future providers.
- Context selection and output quality can be evaluated independently.

### Negative

- Context selection becomes a substantial product subsystem requiring rules and tests.
- Attachment extraction and confirmation add implementation effort.
- Gemini free-tier testing cannot use real user data.
- A hosted model may still produce unsupported text, requiring strict validation and fallback behaviour.

## Rejected alternatives

### Send the full profile and every attachment to the hosted model

Rejected because it increases privacy exposure, token usage, latency, and the chance that old or irrelevant information influences the response.

### Let the mobile application call the hosted model directly

Rejected because it exposes API credentials and bypasses Janani safety, consent, RAG, audit, and policy controls.

### Train a complete Janani language model first

Rejected for the initial product because it requires large licensed datasets, specialised infrastructure, extensive evaluation, and higher cost without removing the need for safety and orchestration.

### Hardcode Gemini throughout the business logic

Rejected because provider availability, pricing, terms, and model quality can change. Gemini is the first adapter, not the permanent architecture boundary.
