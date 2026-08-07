import json
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.workers import cli
from app.workers.models import ReminderWorkerRunReport, ReminderWorkerRunState

RUN_AT = datetime(2030, 1, 2, 6, 30, tzinfo=UTC)


def worker_settings(*, enabled: bool = True) -> Settings:
    return Settings(
        reminder_worker_enabled=enabled,
        supabase_url="http://127.0.0.1:54321",
        supabase_service_role_key="synthetic-service-role",
    )


def report(state: ReminderWorkerRunState) -> ReminderWorkerRunReport:
    return ReminderWorkerRunReport(
        state=state,
        run_at=RUN_AT,
        materialization_window_start=RUN_AT - timedelta(minutes=15),
        materialization_window_end=RUN_AT + timedelta(days=1),
        materialized_job_count=2,
        claimed_job_count=1,
        sent_job_count=1 if state is ReminderWorkerRunState.COMPLETED else 0,
        retryable_job_count=0,
        terminal_job_count=0,
        runtime_error_job_count=0 if state is ReminderWorkerRunState.COMPLETED else 1,
        requeue_failure_job_count=0,
    )


def test_cli_returns_configuration_exit_when_worker_is_disabled(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: worker_settings(enabled=False))

    exit_code = cli.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "failure_code": "worker_disabled",
        "state": "disabled",
    }


def test_cli_completed_run_emits_aggregate_report_and_returns_zero(monkeypatch, capsys) -> None:
    settings = worker_settings()
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    async def fake_run(configured_settings):
        assert configured_settings is settings
        return report(ReminderWorkerRunState.COMPLETED)

    monkeypatch.setattr(cli, "run_configured_reminder_worker_once", fake_run)

    exit_code = cli.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert captured.err == ""
    assert payload["state"] == "completed"
    assert payload["claimed_job_count"] == 1
    assert "synthetic-service-role" not in captured.out
    assert "push_token" not in captured.out


def test_cli_degraded_run_returns_nonzero_without_dumping_sensitive_failures(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(cli, "get_settings", worker_settings)

    async def fake_run(_settings):
        return report(ReminderWorkerRunState.DEGRADED)

    monkeypatch.setattr(cli, "run_configured_reminder_worker_once", fake_run)

    exit_code = cli.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["state"] == "degraded"
    assert payload["runtime_error_job_count"] == 1


def test_cli_unhandled_runtime_error_is_collapsed_to_machine_code(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "get_settings", worker_settings)

    async def fake_run(_settings):
        raise RuntimeError("raw provider error with synthetic secret")

    monkeypatch.setattr(cli, "run_configured_reminder_worker_once", fake_run)

    exit_code = cli.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "failure_code": "worker_runtime_failed",
        "state": "failed",
    }
    assert "raw provider error" not in captured.err
    assert "synthetic secret" not in captured.err
