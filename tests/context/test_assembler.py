from app.attachments import (
    AttachmentKind,
    AttachmentRecord,
    ConfirmationStatus,
    ExtractionStatus,
)
from app.context import ContextAssembler, ContextAssemblyInput, ContextAssemblyStatus, TaskType
from app.context.models import ApprovedKnowledgeChunk
from app.domain import (
    ConsentEvent,
    ConsentPurpose,
    ConsentSnapshot,
    ConsentStatus,
    DietaryPreference,
    MedicationRecord,
    MedicationSource,
    PregnancyRecord,
    UserHealthProfile,
)
from app.safety.engine import SafetyEngine
from app.safety.models import SymptomAssessmentRequest
from app.safety.rules import build_development_rules


def consent_snapshot(*purposes: ConsentPurpose) -> ConsentSnapshot:
    return ConsentSnapshot(
        events=[
            ConsentEvent(
                purpose=purpose,
                status=ConsentStatus.GRANTED,
                policy_version="synthetic-test-v1",
            )
            for purpose in purposes
        ]
    )


def routine_safety_decision():
    engine = SafetyEngine(build_development_rules(), "synthetic-test", allow_unapproved=True)
    return engine.evaluate(SymptomAssessmentRequest())


def warning_safety_decision():
    engine = SafetyEngine(build_development_rules(), "synthetic-test", allow_unapproved=True)
    return engine.evaluate(SymptomAssessmentRequest(heavy_bleeding=True))


def pregnancy() -> PregnancyRecord:
    return PregnancyRecord(
        gestational_week=22,
        known_conditions=["synthetic anaemia"],
        weight_kg=62,
    )


def confirmed_attachment(text: str = "Synthetic confirmed report text") -> AttachmentRecord:
    return AttachmentRecord(
        kind=AttachmentKind.LAB_REPORT,
        mime_type="application/pdf",
        storage_object_path="synthetic-user/report.pdf",
        extraction_status=ExtractionStatus.COMPLETED,
        confirmation_status=ConfirmationStatus.CONFIRMED,
        extracted_text=text,
        extraction_confidence=0.98,
    )


def approved_chunk(
    content: str = "Synthetic approved pregnancy guidance",
) -> ApprovedKnowledgeChunk:
    return ApprovedKnowledgeChunk(
        chunk_id="SYNTHETIC-KNOWLEDGE-1",
        source_title="Synthetic clinician-reviewed source",
        content=content,
        citation_label="Synthetic source section 1",
        approved=True,
        review_valid=True,
    )


def test_nutrition_selects_relevant_context_and_excludes_unrelated_records() -> None:
    medication = MedicationRecord(
        name="Synthetic tablet",
        source=MedicationSource.USER_ENTERED,
        confirmed=True,
    )
    attachment = confirmed_attachment()
    payload = ContextAssemblyInput(
        task=TaskType.NUTRITION,
        user_question="What synthetic food guidance applies this week?",
        consents=consent_snapshot(
            ConsentPurpose.CARE_SUPPORT,
            ConsentPurpose.AI_PROCESSING,
        ),
        profile=UserHealthProfile(dietary_preference=DietaryPreference.VEGETARIAN),
        pregnancy=pregnancy(),
        medications=[medication],
        attachments=[attachment],
        approved_knowledge=[approved_chunk()],
    )

    response = ContextAssembler().assemble(payload, routine_safety_decision())

    assert response.status is ContextAssemblyStatus.READY
    assert response.llm_request is not None
    selected = response.llm_request.selected_context
    assert selected.profile is not None
    assert selected.pregnancy is not None
    assert selected.medications == []
    assert selected.attachments == []
    assert len(selected.approved_knowledge) == 1
    assert {item.category for item in response.exclusions} >= {"medication", "attachment"}


def test_missing_ai_consent_stops_context_assembly() -> None:
    payload = ContextAssemblyInput(
        task=TaskType.NUTRITION,
        user_question="Synthetic nutrition question",
        consents=consent_snapshot(ConsentPurpose.CARE_SUPPORT),
        pregnancy=pregnancy(),
    )

    response = ContextAssembler().assemble(payload, routine_safety_decision())

    assert response.status is ContextAssemblyStatus.CONSENT_REQUIRED
    assert response.llm_request is None
    assert response.missing_consents == [ConsentPurpose.AI_PROCESSING]


def test_safety_block_prevents_any_llm_request() -> None:
    payload = ContextAssemblyInput(
        task=TaskType.GENERAL_QUESTION,
        user_question="Synthetic warning-sign question",
        consents=consent_snapshot(
            ConsentPurpose.CARE_SUPPORT,
            ConsentPurpose.AI_PROCESSING,
        ),
        pregnancy=pregnancy(),
    )

    response = ContextAssembler().assemble(payload, warning_safety_decision())

    assert response.status is ContextAssemblyStatus.BLOCKED_BY_SAFETY
    assert response.llm_request is None
    assert response.safety_decision.blocks_llm is True


def test_report_explanation_requires_explicit_confirmed_attachment() -> None:
    selected_report = confirmed_attachment()
    unconfirmed_report = AttachmentRecord(
        kind=AttachmentKind.LAB_REPORT,
        mime_type="application/pdf",
        storage_object_path="synthetic-user/unconfirmed.pdf",
        extraction_status=ExtractionStatus.COMPLETED,
        confirmation_status=ConfirmationStatus.UNCONFIRMED,
        extracted_text="Synthetic unconfirmed extraction",
    )
    base = dict(
        task=TaskType.REPORT_EXPLANATION,
        user_question="Explain this synthetic report",
        consents=consent_snapshot(
            ConsentPurpose.CARE_SUPPORT,
            ConsentPurpose.AI_PROCESSING,
            ConsentPurpose.ATTACHMENT_PROCESSING,
        ),
        pregnancy=pregnancy(),
        attachments=[selected_report, unconfirmed_report],
        approved_knowledge=[approved_chunk()],
    )

    without_selection = ContextAssembler().assemble(
        ContextAssemblyInput(**base),
        routine_safety_decision(),
    )
    with_selection = ContextAssembler().assemble(
        ContextAssemblyInput(
            **base,
            requested_attachment_ids=[
                selected_report.attachment_id,
                unconfirmed_report.attachment_id,
            ],
        ),
        routine_safety_decision(),
    )

    assert without_selection.status is ContextAssemblyStatus.INSUFFICIENT_CONTEXT
    assert with_selection.status is ContextAssemblyStatus.READY
    assert with_selection.llm_request is not None
    assert len(with_selection.llm_request.selected_context.attachments) == 1
    assert with_selection.llm_request.selected_context.attachments[0].attachment_id == (
        selected_report.attachment_id
    )
    assert any("unconfirmed" in item.reason for item in with_selection.exclusions)


def test_medication_reminder_uses_only_active_confirmed_medications() -> None:
    confirmed = MedicationRecord(
        name="Synthetic confirmed medication",
        dose_text="Synthetic dose",
        schedule_text="Synthetic schedule",
        source=MedicationSource.CLINICIAN_ENTERED,
        confirmed=True,
        active=True,
    )
    unconfirmed = MedicationRecord(
        name="Synthetic unconfirmed medication",
        source=MedicationSource.USER_ENTERED,
        confirmed=False,
    )
    inactive = MedicationRecord(
        name="Synthetic inactive medication",
        source=MedicationSource.USER_ENTERED,
        confirmed=True,
        active=False,
    )
    payload = ContextAssemblyInput(
        task=TaskType.MEDICATION_REMINDER,
        user_question="Prepare the synthetic medication reminder",
        consents=consent_snapshot(
            ConsentPurpose.CARE_SUPPORT,
            ConsentPurpose.AI_PROCESSING,
        ),
        pregnancy=pregnancy(),
        medications=[confirmed, unconfirmed, inactive],
    )

    response = ContextAssembler().assemble(payload, routine_safety_decision())

    assert response.status is ContextAssemblyStatus.READY
    assert response.llm_request is not None
    assert [item.medication_id for item in response.llm_request.selected_context.medications] == [
        confirmed.medication_id
    ]
    reasons = {item.reason for item in response.exclusions}
    assert "medication is not confirmed" in reasons
    assert "medication is inactive" in reasons


def test_context_budget_removes_optional_knowledge_before_failing() -> None:
    chunks = [
        ApprovedKnowledgeChunk(
            chunk_id=f"SYNTHETIC-{index}",
            source_title="Synthetic source",
            content="x" * 1_500,
            citation_label=f"Synthetic citation {index}",
            approved=True,
            review_valid=True,
        )
        for index in range(5)
    ]
    payload = ContextAssemblyInput(
        task=TaskType.NUTRITION,
        user_question="Synthetic budget question",
        consents=consent_snapshot(
            ConsentPurpose.CARE_SUPPORT,
            ConsentPurpose.AI_PROCESSING,
        ),
        pregnancy=pregnancy(),
        approved_knowledge=chunks,
        max_context_chars=2_000,
    )

    response = ContextAssembler().assemble(payload, routine_safety_decision())

    assert response.status is ContextAssemblyStatus.READY
    assert response.llm_request is not None
    assert any(item.reason == "removed to satisfy context budget" for item in response.exclusions)
