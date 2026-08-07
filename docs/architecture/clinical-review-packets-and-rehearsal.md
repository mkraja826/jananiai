# Clinical Review Packets and Emergency Rollback Rehearsal

Status: pre-clinical engineering controls implemented with synthetic data only.

This phase prepares Janani AI for qualified human review without pretending that clinical authorisation has occurred. It adds stronger challenge datasets, immutable review packets, and synthetic emergency rollback rehearsal evidence.

## Expanded validation evidence

Every current development warning rule now has nine executable synthetic categories:

1. true positive;
2. true negative;
3. gestational boundary;
4. two-rule interaction;
5. regression/free-text isolation;
6. ambiguity;
7. missing gestational data;
8. adversarial free text;
9. three-rule cross-interaction.

Seven development rules therefore produce 63 cases. These cases verify deterministic software behavior only. They do not estimate sensitivity, specificity, clinical benefit, or safety in real patients.

Free text remains non-authoritative for deterministic warning decisions. Ambiguous or prompt-like notes cannot manufacture structured safety fields. Missing gestational week does not erase a directly confirmed structured warning in the current development rules. These expectations themselves require clinician review before any real-user deployment.

## Review packet

A pre-clinical review packet binds one rule candidate to:

- candidate ID, version, and canonical SHA-256 content digest;
- severity and predicate identifier;
- documented rationale;
- source references and placeholder-source status;
- English and Telugu escalation wording versions;
- exact validation dataset version and SHA-256 digest;
- all nine required validation categories;
- exact case IDs for the target rule;
- fully passing engineering results;
- required obstetrician, clinical-safety, and language-review roles.

A packet cannot be generated from a failing or mismatched validation report. The packet content itself has a deterministic digest so a reviewer attestation can be tied to the exact evidence they inspected.

The current development candidates contain placeholder sources, so generated packets explicitly remain in `clinical_input_required` state and are not clinically approval-eligible.

## Reviewer attestations

The code defines an attestation contract that binds a reviewer identity and role to the exact packet digest. An approval attestation must explicitly confirm:

- expected validation results;
- sources and exact sections;
- escalation wording.

The contract does not fabricate attestations. No real reviewer attestation is created by tests, CI, or repository code.

## Emergency rollback rehearsal

The synthetic rehearsal runner uses the same atomic ruleset rollback domain service that protects deployment. A successful rehearsal must demonstrate:

1. incident detection was recorded;
2. the active manifest was verified;
3. atomic rollback executed;
4. the complete prior manifest was restored;
5. the incident ruleset entered `rolled_back` state;
6. audit evidence was recorded.

The report is synthetic-only and requires a distinct prior ruleset. The restored release IDs must exactly match the prior ruleset release set.

## Immutable Supabase evidence

The migration adds private append-only tables for:

- pre-clinical review packets;
- safety incident rehearsals.

Normal `anon` and `authenticated` roles cannot read or mutate these tables or invoke their recording RPCs. The trusted backend service role can record evidence through validated RPCs and can read it for governance review, but update and delete operations are blocked after insertion.

Review packet persistence validates the stored candidate ID and digest, fully passing case counts, all nine categories, and synthetic-only status.

Rehearsal persistence validates synthetic-only status, the complete required step set, distinct ruleset identities, an active restored ruleset, and a rolled-back incident ruleset.

Both actions emit append-only governance events with the administrator user ID.

## What remains blocked

This work does not complete the 30% clinical-safety milestone. The following remain mandatory before clinical authorisation:

- approved reviewer-onboarding, conflict-of-interest, evidence-retention, and operating procedures;
- verified real obstetrician, clinical-safety, and Telugu-language reviewer credentials;
- replacement of development placeholders with current exact-section sources;
- independent clinical review of every predicate, severity, rationale, and applicability boundary;
- independent approval of English and Telugu escalation wording;
- independently authored and reviewed expected outcomes beyond the implementation team;
- hosted-staging rehearsal with synthetic data;
- documented incident-response ownership and production access controls;
- privacy, legal, security, and clinical launch sign-off.

Until those gates are complete, every current rule remains inactive and development-only, and real patient data is prohibited.
