# Foundation Architecture

```text
Janani mobile application (not connected yet)
              |
              | HTTPS in later phases
              v
        FastAPI service
        |     |      |
        |     |      +-- provider-independent LLM interface
        |     |          +-- mock provider only in free-first mode
        |     |
        |     +-- deterministic safety engine
        |          +-- draft rules for synthetic tests
        |          +-- approved rules only in production
        |
        +-- future structured services and RAG
              |
              v
       Supabase Postgres / pgvector
       (schema integration begins in later phases)
```

## Invariants

- Safety evaluation occurs before any future LLM request.
- Triggered escalation blocks the LLM path.
- No unvalidated model JSON reaches a client.
- No rule becomes clinically active without approval metadata.
- Free-first mode rejects real-patient payloads and non-mock providers.
- The readiness endpoint distinguishes service readiness from clinical readiness.
