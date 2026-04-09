from __future__ import annotations

from types import SimpleNamespace

from polio_api.api.routes import diagnosis as diagnosis_route


def test_maybe_process_diagnosis_job_inline_processes_queued_job(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        diagnosis_route,
        "get_settings",
        lambda: SimpleNamespace(allow_inline_job_processing=True),
    )
    monkeypatch.setattr(
        diagnosis_route,
        "get_latest_job_for_resource",
        lambda db, resource_type, resource_id: SimpleNamespace(id="job-1", status="queued"),
    )
    monkeypatch.setattr(
        diagnosis_route,
        "process_async_job",
        lambda db, job_id: called.append(job_id),
    )

    run = SimpleNamespace(id="run-1", status="PENDING")
    diagnosis_route._maybe_process_diagnosis_job_inline(SimpleNamespace(), run)

    assert called == ["job-1"]


def test_maybe_process_diagnosis_job_inline_skips_terminal_runs(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        diagnosis_route,
        "get_settings",
        lambda: SimpleNamespace(allow_inline_job_processing=True),
    )
    monkeypatch.setattr(
        diagnosis_route,
        "get_latest_job_for_resource",
        lambda db, resource_type, resource_id: SimpleNamespace(id="job-2", status="queued"),
    )
    monkeypatch.setattr(
        diagnosis_route,
        "process_async_job",
        lambda db, job_id: called.append(job_id),
    )

    diagnosis_route._maybe_process_diagnosis_job_inline(SimpleNamespace(), SimpleNamespace(id="run-2", status="COMPLETED"))
    diagnosis_route._maybe_process_diagnosis_job_inline(SimpleNamespace(), SimpleNamespace(id="run-3", status="FAILED"))

    assert called == []


def test_maybe_process_report_job_inline_processes_queued_job(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        diagnosis_route,
        "get_settings",
        lambda: SimpleNamespace(allow_inline_job_processing=True),
    )
    monkeypatch.setattr(
        diagnosis_route,
        "get_latest_job_for_resource",
        lambda db, resource_type, resource_id: SimpleNamespace(id="report-job-1", status="queued"),
    )
    monkeypatch.setattr(
        diagnosis_route,
        "process_async_job",
        lambda db, job_id: called.append(job_id),
    )

    diagnosis_route._maybe_process_report_job_inline(SimpleNamespace(), SimpleNamespace(id="run-11", status="COMPLETED"))

    assert called == ["report-job-1"]


def test_maybe_process_report_job_inline_skips_non_completed_runs(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        diagnosis_route,
        "get_settings",
        lambda: SimpleNamespace(allow_inline_job_processing=True),
    )
    monkeypatch.setattr(
        diagnosis_route,
        "get_latest_job_for_resource",
        lambda db, resource_type, resource_id: SimpleNamespace(id="report-job-2", status="queued"),
    )
    monkeypatch.setattr(
        diagnosis_route,
        "process_async_job",
        lambda db, job_id: called.append(job_id),
    )

    diagnosis_route._maybe_process_report_job_inline(SimpleNamespace(), SimpleNamespace(id="run-12", status="RUNNING"))

    assert called == []


def _minimal_run(*, status: str, result_payload: str | None = None):
    return SimpleNamespace(
        id="run-x",
        project_id="project-x",
        status=status,
        result_payload=result_payload,
        error_message=None,
        review_tasks=[],
        policy_flags=[],
        response_traces=[],
    )


def test_build_run_response_uses_auto_starting_when_report_not_materialized(monkeypatch) -> None:
    run = _minimal_run(
        status="COMPLETED",
        result_payload='{"headline":"h","strengths":["s"],"gaps":["g"],"recommended_focus":"f","risk_level":"warning"}',
    )

    def fake_latest_job(db, *, resource_type, resource_id):  # noqa: ANN001, ANN003
        if resource_type == "diagnosis_run":
            return SimpleNamespace(id="diag-job", status="succeeded")
        return None

    monkeypatch.setattr(diagnosis_route, "latest_response_trace", lambda run: None)
    monkeypatch.setattr(diagnosis_route, "get_latest_job_for_resource", fake_latest_job)
    monkeypatch.setattr(diagnosis_route, "get_latest_report_artifact_for_run", lambda db, diagnosis_run_id, report_mode: None)

    response = diagnosis_route._build_run_response(SimpleNamespace(), run)

    assert response.report_status == "AUTO_STARTING"
    assert response.report_async_job_id is None
    assert response.report_artifact_id is None


def test_build_run_response_prefers_failed_report_artifact_error(monkeypatch) -> None:
    run = _minimal_run(
        status="COMPLETED",
        result_payload='{"headline":"h","strengths":["s"],"gaps":["g"],"recommended_focus":"f","risk_level":"warning"}',
    )
    failed_artifact = SimpleNamespace(
        id="artifact-1",
        status="FAILED",
        error_message="report render failed",
    )

    def fake_latest_job(db, *, resource_type, resource_id):  # noqa: ANN001, ANN003
        if resource_type == "diagnosis_run":
            return SimpleNamespace(id="diag-job", status="succeeded")
        if resource_type == "diagnosis_report":
            return SimpleNamespace(id="report-job", status="failed", failure_reason="job failed")
        return None

    monkeypatch.setattr(diagnosis_route, "latest_response_trace", lambda run: None)
    monkeypatch.setattr(diagnosis_route, "get_latest_job_for_resource", fake_latest_job)
    monkeypatch.setattr(
        diagnosis_route,
        "get_latest_report_artifact_for_run",
        lambda db, diagnosis_run_id, report_mode: failed_artifact,
    )

    response = diagnosis_route._build_run_response(SimpleNamespace(), run)

    assert response.report_status == "FAILED"
    assert response.report_artifact_id == "artifact-1"
    assert response.report_error_message == "report render failed"


def test_ensure_default_report_bootstrap_runs_only_for_completed(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        diagnosis_route,
        "ensure_default_diagnosis_report_job",
        lambda db, **kwargs: calls.append(kwargs["run"].id) or "queued",
    )

    diagnosis_route._ensure_default_report_bootstrap(SimpleNamespace(), _minimal_run(status="RUNNING", result_payload=None))
    diagnosis_route._ensure_default_report_bootstrap(
        SimpleNamespace(),
        _minimal_run(
            status="COMPLETED",
            result_payload='{"headline":"h","strengths":["s"],"gaps":["g"],"recommended_focus":"f","risk_level":"warning"}',
        ),
    )

    assert calls == ["run-x"]
