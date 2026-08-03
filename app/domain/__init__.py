"""Typed domain records used by Janani AI orchestration."""

from app.domain.consent import ConsentEvent, ConsentPurpose, ConsentSnapshot, ConsentStatus
from app.domain.records import (
    AppointmentRecord,
    DietaryPreference,
    MedicationRecord,
    MedicationSource,
    PregnancyRecord,
    UserHealthProfile,
)

__all__ = [
    "AppointmentRecord",
    "ConsentEvent",
    "ConsentPurpose",
    "ConsentSnapshot",
    "ConsentStatus",
    "DietaryPreference",
    "MedicationRecord",
    "MedicationSource",
    "PregnancyRecord",
    "UserHealthProfile",
]
