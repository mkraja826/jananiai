import asyncio
import json
import sys

from pydantic import ValidationError

from app.config import get_settings
from app.workers.models import ReminderWorkerRunState
from app.workers.runtime import (
    ReminderWorkerConfigurationError,
    run_configured_reminder_worker_once,
)


def _write_status(payload: dict[str, object], *, stream) -> None:
    stream.write(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    stream.write("\n")


def main() -> int:
    """Execute one reminder-worker cycle and return a scheduler-friendly exit code."""

    try:
        settings = get_settings()
    except ValidationError:
        _write_status(
            {"state": "failed", "failure_code": "invalid_worker_configuration"},
            stream=sys.stderr,
        )
        return 2

    if not settings.reminder_worker_enabled:
        _write_status(
            {"state": "disabled", "failure_code": "worker_disabled"},
            stream=sys.stderr,
        )
        return 2

    try:
        report = asyncio.run(run_configured_reminder_worker_once(settings))
    except ReminderWorkerConfigurationError:
        _write_status(
            {"state": "failed", "failure_code": "invalid_worker_configuration"},
            stream=sys.stderr,
        )
        return 2
    except Exception:
        _write_status(
            {"state": "failed", "failure_code": "worker_runtime_failed"},
            stream=sys.stderr,
        )
        return 1

    sys.stdout.write(report.model_dump_json())
    sys.stdout.write("\n")
    return 1 if report.state is ReminderWorkerRunState.DEGRADED else 0


if __name__ == "__main__":
    raise SystemExit(main())
