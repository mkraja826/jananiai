from dataclasses import dataclass

from app.attachments import AttachmentKind
from app.context.models import TaskType


@dataclass(frozen=True, slots=True)
class ContextPolicy:
    include_profile: bool
    include_pregnancy: bool
    include_medications: bool
    include_appointments: bool
    include_attachments: bool
    include_knowledge: bool
    allowed_attachment_kinds: frozenset[AttachmentKind] = frozenset()
    max_medications: int = 10
    max_appointments: int = 5
    max_attachments: int = 3
    max_knowledge_chunks: int = 8


_POLICIES: dict[TaskType, ContextPolicy] = {
    TaskType.WEEKLY_GUIDANCE: ContextPolicy(
        include_profile=True,
        include_pregnancy=True,
        include_medications=False,
        include_appointments=False,
        include_attachments=False,
        include_knowledge=True,
    ),
    TaskType.NUTRITION: ContextPolicy(
        include_profile=True,
        include_pregnancy=True,
        include_medications=False,
        include_appointments=False,
        include_attachments=False,
        include_knowledge=True,
    ),
    TaskType.APPOINTMENT_PREPARATION: ContextPolicy(
        include_profile=True,
        include_pregnancy=True,
        include_medications=True,
        include_appointments=True,
        include_attachments=True,
        include_knowledge=True,
        allowed_attachment_kinds=frozenset(
            {
                AttachmentKind.LAB_REPORT,
                AttachmentKind.ULTRASOUND_REPORT,
                AttachmentKind.PRESCRIPTION,
                AttachmentKind.DISCHARGE_SUMMARY,
            }
        ),
    ),
    TaskType.REPORT_EXPLANATION: ContextPolicy(
        include_profile=False,
        include_pregnancy=True,
        include_medications=False,
        include_appointments=False,
        include_attachments=True,
        include_knowledge=True,
        allowed_attachment_kinds=frozenset(
            {
                AttachmentKind.LAB_REPORT,
                AttachmentKind.ULTRASOUND_REPORT,
                AttachmentKind.DISCHARGE_SUMMARY,
                AttachmentKind.OTHER_DOCUMENT,
            }
        ),
        max_attachments=2,
    ),
    TaskType.MEDICATION_REMINDER: ContextPolicy(
        include_profile=False,
        include_pregnancy=True,
        include_medications=True,
        include_appointments=False,
        include_attachments=False,
        include_knowledge=False,
        max_medications=5,
    ),
    TaskType.GENERAL_QUESTION: ContextPolicy(
        include_profile=True,
        include_pregnancy=True,
        include_medications=False,
        include_appointments=False,
        include_attachments=False,
        include_knowledge=True,
    ),
}


def policy_for(task: TaskType) -> ContextPolicy:
    return _POLICIES[task]
