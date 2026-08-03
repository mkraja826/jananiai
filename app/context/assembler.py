from collections.abc import Iterable

from app.context.models import (
    ApprovedKnowledgeChunk,
    ContextAssemblyInput,
    ContextAssemblyResponse,
    ContextAssemblyStatus,
    ExcludedContextItem,
    JananiLLMRequest,
    SafetyContextSummary,
    SelectedAttachment,
    SelectedContext,
    TaskType,
)
from app.context.policies import ContextPolicy, policy_for
from app.domain import AppointmentRecord, MedicationRecord
from app.safety.models import SafetyDecision

_HARD_CONSTRAINTS = [
    "Use only the selected context and approved knowledge supplied in this request.",
    "Do not diagnose a condition or declare a symptom safe or normal.",
    "Do not prescribe, start, stop, or change the dose, frequency, or duration of medication.",
    "Do not override or weaken a deterministic safety decision.",
    "Do not claim to interpret ultrasound images; explain confirmed report text only.",
    "Clearly state when information is insufficient and direct the user to a qualified clinician.",
    "Return only the response schema requested by Janani AI.",
]

_TASK_INSTRUCTIONS: dict[TaskType, str] = {
    TaskType.WEEKLY_GUIDANCE: (
        "Provide stage-appropriate educational guidance grounded only in approved knowledge."
    ),
    TaskType.NUTRITION: (
        "Provide educational nutrition guidance based on the selected pregnancy and dietary "
        "context; do not create a medical diet or treatment plan."
    ),
    TaskType.APPOINTMENT_PREPARATION: (
        "Summarise the selected confirmed records and generate concise questions for the next "
        "clinician appointment."
    ),
    TaskType.REPORT_EXPLANATION: (
        "Explain the confirmed report text in plain language without diagnosing or interpreting "
        "medical images."
    ),
    TaskType.MEDICATION_REMINDER: (
        "Restate only the selected confirmed medication schedule; do not infer or modify it."
    ),
    TaskType.GENERAL_QUESTION: (
        "Answer the question using only approved knowledge and selected pregnancy context."
    ),
}


class ContextAssembler:
    """Deterministically selects minimal, confirmed context before any hosted-model call."""

    def assemble(
        self,
        payload: ContextAssemblyInput,
        safety_decision: SafetyDecision,
    ) -> ContextAssemblyResponse:
        if safety_decision.blocks_llm:
            return ContextAssemblyResponse(
                status=ContextAssemblyStatus.BLOCKED_BY_SAFETY,
                safety_decision=safety_decision,
                message=(
                    "Context assembly stopped because the deterministic safety path blocked AI."
                ),
            )

        if not payload.is_synthetic:
            return ContextAssemblyResponse(
                status=ContextAssemblyStatus.INSUFFICIENT_CONTEXT,
                safety_decision=safety_decision,
                message="Free-first context assembly accepts synthetic data only.",
            )

        if payload.task is TaskType.REPORT_EXPLANATION and not payload.requested_attachment_ids:
            return ContextAssemblyResponse(
                status=ContextAssemblyStatus.INSUFFICIENT_CONTEXT,
                safety_decision=safety_decision,
                message="Report explanation requires an explicitly selected attachment.",
            )

        policy = policy_for(payload.task)
        attachment_processing_needed = policy.include_attachments and bool(payload.attachments)
        required_consents = payload.required_consents(attachment_processing_needed)
        missing_consents = payload.consents.require(*required_consents)
        if missing_consents:
            return ContextAssemblyResponse(
                status=ContextAssemblyStatus.CONSENT_REQUIRED,
                safety_decision=safety_decision,
                missing_consents=missing_consents,
                message="Required consent is missing or has been revoked.",
            )

        selected, exclusions = self._select_context(payload, policy)
        insufficiency = self._required_context_problem(payload.task, selected)
        if insufficiency is not None:
            return ContextAssemblyResponse(
                status=ContextAssemblyStatus.INSUFFICIENT_CONTEXT,
                safety_decision=safety_decision,
                exclusions=exclusions,
                message=insufficiency,
            )

        if not self._fit_budget(selected, payload.max_context_chars, exclusions, payload.task):
            return ContextAssemblyResponse(
                status=ContextAssemblyStatus.INSUFFICIENT_CONTEXT,
                safety_decision=safety_decision,
                exclusions=exclusions,
                message="The required confirmed context exceeds the configured context budget.",
            )

        request = JananiLLMRequest(
            task=payload.task,
            language=payload.language,
            user_question=payload.user_question,
            request_instruction=_TASK_INSTRUCTIONS[payload.task],
            selected_context=selected,
            safety_summary=SafetyContextSummary(
                severity=safety_decision.severity.value,
                triggered=safety_decision.triggered,
                triggered_rule_ids=safety_decision.triggered_rule_ids,
                ruleset_version=safety_decision.ruleset_version,
            ),
            hard_constraints=list(_HARD_CONSTRAINTS),
            synthetic_data_only=True,
        )
        return ContextAssemblyResponse(
            status=ContextAssemblyStatus.READY,
            safety_decision=safety_decision,
            llm_request=request,
            exclusions=exclusions,
            message="A minimal, confirmed, provider-neutral LLM request was assembled.",
        )

    def _select_context(
        self,
        payload: ContextAssemblyInput,
        policy: ContextPolicy,
    ) -> tuple[SelectedContext, list[ExcludedContextItem]]:
        exclusions: list[ExcludedContextItem] = []
        medications = self._select_medications(payload, policy, exclusions)
        appointments = self._select_appointments(payload, policy, exclusions)
        attachments = self._select_attachments(payload, policy, exclusions)
        knowledge = self._select_knowledge(payload, policy, exclusions)

        return (
            SelectedContext(
                profile=payload.profile if policy.include_profile else None,
                pregnancy=payload.pregnancy if policy.include_pregnancy else None,
                medications=medications,
                appointments=appointments,
                attachments=attachments,
                approved_knowledge=knowledge,
            ),
            exclusions,
        )

    def _select_knowledge(
        self,
        payload: ContextAssemblyInput,
        policy: ContextPolicy,
        exclusions: list[ExcludedContextItem],
    ) -> list[ApprovedKnowledgeChunk]:
        if not policy.include_knowledge:
            for item in payload.approved_knowledge:
                exclusions.append(
                    ExcludedContextItem(
                        category="knowledge",
                        item_id=item.chunk_id,
                        reason="task policy excludes it",
                    )
                )
            return []

        selected = [item for item in payload.approved_knowledge if item.eligible_for(payload.task)][
            : policy.max_knowledge_chunks
        ]
        selected_ids = {item.chunk_id for item in selected}
        for item in payload.approved_knowledge:
            if item.chunk_id not in selected_ids:
                exclusions.append(
                    ExcludedContextItem(
                        category="knowledge",
                        item_id=item.chunk_id,
                        reason=(
                            "not approved, review expired, task irrelevant, or over task limit"
                        ),
                    )
                )
        return selected

    def _select_medications(
        self,
        payload: ContextAssemblyInput,
        policy: ContextPolicy,
        exclusions: list[ExcludedContextItem],
    ) -> list[MedicationRecord]:
        if not policy.include_medications:
            self._exclude_all(
                exclusions,
                "medication",
                payload.medications,
                "task policy excludes it",
            )
            return []

        requested = set(payload.requested_medication_ids)
        selected: list[MedicationRecord] = []
        ordered = sorted(
            payload.medications,
            key=lambda record: record.recorded_at,
            reverse=True,
        )
        for item in ordered:
            reason: str | None = None
            if not item.confirmed:
                reason = "medication is not confirmed"
            elif not item.active:
                reason = "medication is inactive"
            elif requested and item.medication_id not in requested:
                reason = "medication was not selected for this request"
            elif len(selected) >= policy.max_medications:
                reason = "medication exceeds the task limit"

            if reason is None:
                selected.append(item)
            else:
                exclusions.append(
                    ExcludedContextItem(
                        category="medication",
                        item_id=str(item.medication_id),
                        reason=reason,
                    )
                )
        return selected

    def _select_appointments(
        self,
        payload: ContextAssemblyInput,
        policy: ContextPolicy,
        exclusions: list[ExcludedContextItem],
    ) -> list[AppointmentRecord]:
        if not policy.include_appointments:
            self._exclude_all(
                exclusions,
                "appointment",
                payload.appointments,
                "task policy excludes it",
            )
            return []

        ordered = sorted(payload.appointments, key=lambda item: item.scheduled_at, reverse=True)
        selected = ordered[: policy.max_appointments]
        self._exclude_all(
            exclusions,
            "appointment",
            ordered[policy.max_appointments :],
            "appointment exceeds the task limit",
        )
        return selected

    def _select_attachments(
        self,
        payload: ContextAssemblyInput,
        policy: ContextPolicy,
        exclusions: list[ExcludedContextItem],
    ) -> list[SelectedAttachment]:
        if not policy.include_attachments:
            self._exclude_all(
                exclusions,
                "attachment",
                payload.attachments,
                "task policy excludes it",
            )
            return []

        requested = set(payload.requested_attachment_ids)
        selected: list[SelectedAttachment] = []
        for item in payload.attachments:
            reason: str | None = None
            if requested and item.attachment_id not in requested:
                reason = "attachment was not selected for this request"
            elif item.kind not in policy.allowed_attachment_kinds:
                reason = "attachment kind is not allowed for this task"
            elif not item.eligible_for_context:
                reason = "attachment extraction is incomplete or unconfirmed"
            elif len(selected) >= policy.max_attachments:
                reason = "attachment exceeds the task limit"

            if reason is None:
                selected.append(
                    SelectedAttachment(
                        attachment_id=item.attachment_id,
                        kind=item.kind,
                        extracted_text=item.extracted_text or "",
                        extraction_confidence=item.extraction_confidence,
                    )
                )
            else:
                exclusions.append(
                    ExcludedContextItem(
                        category="attachment",
                        item_id=str(item.attachment_id),
                        reason=reason,
                    )
                )
        return selected

    def _required_context_problem(
        self,
        task: TaskType,
        selected: SelectedContext,
    ) -> str | None:
        if (
            task
            in {
                TaskType.WEEKLY_GUIDANCE,
                TaskType.NUTRITION,
                TaskType.APPOINTMENT_PREPARATION,
                TaskType.GENERAL_QUESTION,
            }
            and selected.pregnancy is None
        ):
            return "This task requires a structured pregnancy record."
        if task is TaskType.REPORT_EXPLANATION and not selected.attachments:
            return "Report explanation requires at least one confirmed selected report attachment."
        if task is TaskType.MEDICATION_REMINDER and not selected.medications:
            return "Medication reminder requires at least one active confirmed medication record."
        return None

    def _fit_budget(
        self,
        selected: SelectedContext,
        max_chars: int,
        exclusions: list[ExcludedContextItem],
        task: TaskType,
    ) -> bool:
        while len(selected.model_dump_json()) > max_chars:
            if selected.approved_knowledge:
                removed = selected.approved_knowledge.pop()
                exclusions.append(
                    ExcludedContextItem(
                        category="knowledge",
                        item_id=removed.chunk_id,
                        reason="removed to satisfy context budget",
                    )
                )
                continue
            if selected.appointments:
                removed = selected.appointments.pop()
                exclusions.append(
                    ExcludedContextItem(
                        category="appointment",
                        item_id=str(removed.appointment_id),
                        reason="removed to satisfy context budget",
                    )
                )
                continue
            if selected.attachments and task is not TaskType.REPORT_EXPLANATION:
                removed = selected.attachments.pop()
                exclusions.append(
                    ExcludedContextItem(
                        category="attachment",
                        item_id=str(removed.attachment_id),
                        reason="removed to satisfy context budget",
                    )
                )
                continue
            return False
        return True

    def _exclude_all(
        self,
        exclusions: list[ExcludedContextItem],
        category: str,
        items: Iterable[object],
        reason: str,
    ) -> None:
        for item in items:
            exclusions.append(
                ExcludedContextItem(
                    category=category,
                    item_id=self._item_id(item),
                    reason=reason,
                )
            )

    def _item_id(self, item: object) -> str:
        for field in ("medication_id", "appointment_id", "attachment_id"):
            value = getattr(item, field, None)
            if value is not None:
                return str(value)
        return "unknown"
