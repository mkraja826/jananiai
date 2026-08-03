# Clinical Safety Policy

## Intended role

Janani AI is a supportive education and organisation system. It is not a doctor and is not currently a medical device or clinical decision system.

## Prohibited behaviour

The system must not:

- diagnose pregnancy complications;
- prescribe treatment;
- recommend starting or stopping medication;
- change medication dose, frequency, or duration;
- declare a symptom safe or harmless without assessment;
- autonomously diagnose ultrasound or scan images;
- predict miscarriage or fetal abnormality outside a separately validated system;
- weaken or override a deterministic escalation;
- replace antenatal consultations or emergency care.

## Safety authority order

1. Authenticated access and consent controls.
2. Structured input validation.
3. Deterministic clinician-approved safety rules.
4. Approved clinical knowledge retrieval.
5. Language generation.
6. Code-based output validation.

A language model never outranks a safety rule.

## Current development restriction

All rules in the initial repository are development drafts for synthetic testing. Production mode ignores rules without an approved status and clinician sign-off. No real patient data is permitted in free-first mode.

## Clinical approval requirement

Every active rule must include a stable rule ID, semantic version, clinical severity, response template, reviewer identity, approval timestamp, next-review date, true-positive tests, false-positive tests, boundary tests, and audit logging.
