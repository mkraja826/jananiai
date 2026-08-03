from datetime import UTC, datetime, timedelta

from app.safety import governance
from app.safety.rules import build_development_rules


_REQUIRED_FIELDS = {
    "DEV-SEIZURE-001": ("seizure",),
    "DEV-LOSS-CONSCIOUSNESS-001": ("loss_of_consciousness",),
    "DEV-BREATHING-001": ("severe_breathing_difficulty",),
    "DEV-HEAVY-BLEEDING-001": ("heavy_bleeding",),
    "DEV-SEVERE-PAIN-001": ("severe_abdominal_pain",),
    "DEV-REDUCED-MOVEMENT-001": ("reduced_fetal_movement",),
    "DEV-HEADACHE-VISION-001": ("severe_headache", "vision_changes"),
}

_TELUGU_DEVELOPMENT_ONLY = (
    "ఇది వైద్యపరంగా ఆమోదించని అభివృద్ధి నమూనా మాత్రమే; నిజమైన వినియోగానికి అనుమతి లేదు."
)


def build_development_candidates(
    *,
    created_at: datetime | None = None,
) -> tuple[governance.SafetyRuleCandidate, ...]:
    """Create review candidates that remain unapprovable until real sources replace placeholders."""

    now = created_at or datetime.now(UTC)
    placeholder_source = governance.ClinicalSource(
        source_id="DEVELOPMENT-SOURCE-REQUIRED",
        title="Clinician-reviewed source required before approval",
        publisher="Janani AI development placeholder",
        reference="development-only://replace-with-reviewed-source",
        section="No clinical source has been approved",
        reviewed_at=now,
        expires_at=now + timedelta(days=30),
        development_placeholder=True,
    )

    candidates: list[governance.SafetyRuleCandidate] = []
    for rule in build_development_rules():
        candidates.append(
            governance.SafetyRuleCandidate(
                rule_id=rule.metadata.rule_id,
                version=rule.metadata.version,
                severity=rule.metadata.severity,
                predicate_key=f"structured.{rule.metadata.rule_id.lower()}",
                clinical_rationale=(
                    "Development-only engineering candidate. A licensed clinical reviewer must "
                    "replace this placeholder with documented rationale and current sources."
                ),
                applicability=governance.RuleApplicability(
                    required_structured_fields=_REQUIRED_FIELDS[rule.metadata.rule_id],
                ),
                escalation_text=governance.LocalizedEscalationText(
                    wording_version="development-only-1",
                    english=rule.metadata.response_template,
                    telugu=_TELUGU_DEVELOPMENT_ONLY,
                ),
                sources=(placeholder_source,),
                created_at=now,
            )
        )
    return tuple(candidates)
