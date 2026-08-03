from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.attachments import AttachmentKind, AttachmentRecord
from app.domain import (
    AppointmentRecord,
    ConsentPurpose,
    ConsentSnapshot,
    MedicationRecord,
    PregnancyRecord,
    UserHealthProfile,
)
from app.safety.models import SafetyDecision, SymptomAssessmentRequest


class TaskType(StrEnum):
    WEEKLY_GUIDANCE = "weekly_guidance"
    NUTRITION = "nutrition"
    APPOINTMENT_PREPARATION = "appointment_preparation"
    REPORT_EXPLANATION = "report_explanation"
    MEDICATION_REMINDER = "medication_reminder"
    GENERAL_QUESTION = "general_question"


class ContextAssemblyStatus(StrEnum):
    READY = "ready"
    BLOCKED_BY_SAFETY = "blocked_by_safety"
    CONSENT_REQUIRED = "consent_required"
    INSUFFICIENT_CONTEXT = "insufficient_context"


class ApprovedKnowledgeChunk(BaseModel):
    chunk_id: str = Field(min_length=1, max_length=200)
    source_title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=8_000)
    citation_label: str = Field(min_length=1, max_length=500)
    approved: bool = False
    review_valid: bool = False
    applicable_tasks: list[TaskType] = Field(default_factory=list, max_length=20)

    def eligible_for(self, task: TaskType) -> bool:
        return (
            self.approved
            and self.review_valid
            and (not self.applicable_tasks or task in self.applicable_tasks)
        )


class SelectedAttachment(BaseModel):
    attachment_id: UUID
    kind: AttachmentKind
    extracted_text: str
    extraction_confidence: float | None = None


class SafetyContextSummary(BaseModel):
    severity: str
    triggered: bool
    triggered_rule_ids: list[str]
    ruleset_version: str


class SelectedContext(BaseModel):
    profile: UserHealthProfile | None = None
    pregnancy: PregnancyRecord | None = None
    medications: list[MedicationRecord] = Field(default_factory=list)
    appointments: list[AppointmentRecord] = Field(default_factory=list)
    attachments: list[SelectedAttachment] = Field(default_factory=list)
    approved_knowledge: list[ApprovedKnowledgeChunk] = Field(default_factory=list)


class ExcludedContextItem(BaseModel):
    category: str
    item_id: str
    reason: str


class JananiLLMRequest(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    task: TaskType
    language: Literal["en", "te"]
    user_question: str = Field(min_length=1, max_length=2_000)
    request_instruction: str
    selected_context: SelectedContext
    safety_summary: SafetyContextSummary
    hard_constraints: list[str]
    max_output_tokens: int = Field(default=800, ge=100, le=4_000)
    synthetic_data_only: bool = True


class ContextAssemblyInput(BaseModel):
    is_synthetic: bool = True
    task: TaskType
    language: Literal["en", "te"] = "en"
    user_question: str = Field(min_length=1, max_length=2_000)
    consents: ConsentSnapshot
    profile: UserHealthProfile | None = None
    pregnancy: PregnancyRecord | None = None
    medications: list[MedicationRecord] = Field(default_factory=list, max_length=100)
    appointments: list[AppointmentRecord] = Field(default_factory=list, max_length=100)
    attachments: list[AttachmentRecord] = Field(default_factory=list, max_length=30)
    approved_knowledge: list[ApprovedKnowledgeChunk] = Field(default_factory=list, max_length=50)
    requested_attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)
    requested_medication_ids: list[UUID] = Field(default_factory=list, max_length=20)
    safety_input: SymptomAssessmentRequest = Field(default_factory=SymptomAssessmentRequest)
    max_context_chars: int = Field(default=16_000, ge=2_000, le=80_000)

    @model_validator(mode="after")
    def enforce_synthetic_consistency(self) -> "ContextAssemblyInput":
        synthetic_flags = [self.safety_input.is_synthetic]
        if self.profile is not None:
            synthetic_flags.append(self.profile.synthetic)
        if self.pregnancy is not None:
            synthetic_flags.append(self.pregnancy.synthetic)
        synthetic_flags.extend(item.synthetic for item in self.medications)
        synthetic_flags.extend(item.synthetic for item in self.appointments)
        synthetic_flags.extend(item.synthetic for item in self.attachments)
        synthetic_flags.extend(event.synthetic for event in self.consents.events)
        if self.is_synthetic and not all(synthetic_flags):
            raise ValueError("Synthetic context cannot contain records marked as real data")
        return self

    def required_consents(self, attachment_processing_needed: bool) -> list[ConsentPurpose]:
        required = [ConsentPurpose.CARE_SUPPORT, ConsentPurpose.AI_PROCESSING]
        if attachment_processing_needed:
            required.append(ConsentPurpose.ATTACHMENT_PROCESSING)
        return required


class ContextAssemblyResponse(BaseModel):
    status: ContextAssemblyStatus
    safety_decision: SafetyDecision
    llm_request: JananiLLMRequest | None = None
    missing_consents: list[ConsentPurpose] = Field(default_factory=list)
    exclusions: list[ExcludedContextItem] = Field(default_factory=list)
    message: str

    @model_validator(mode="after")
    def validate_status_payload(self) -> "ContextAssemblyResponse":
        if self.status is ContextAssemblyStatus.READY and self.llm_request is None:
            raise ValueError("Ready context response requires an LLM request")
        if self.status is not ContextAssemblyStatus.READY and self.llm_request is not None:
            raise ValueError("Blocked context response cannot include an LLM request")
        return self
