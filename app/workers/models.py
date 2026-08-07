from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ReminderWorkerRunState(StrEnum):
    COMPLETED = "completed"
    DEGRADED = "degraded"


class ReminderWorkerRunReport(BaseModel):
    """Privacy-minimised worker report containing aggregate operational counts only."""

    state: ReminderWorkerRunState
    run_at: datetime
    materialization_window_start: datetime
    materialization_window_end: datetime
    materialized_job_count: int = Field(ge=0)
    claimed_job_count: int = Field(ge=0)
    sent_job_count: int = Field(ge=0)
    retryable_job_count: int = Field(ge=0)
    terminal_job_count: int = Field(ge=0)
    runtime_error_job_count: int = Field(ge=0)
    requeue_failure_job_count: int = Field(ge=0)
