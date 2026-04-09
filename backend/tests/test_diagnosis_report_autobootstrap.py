from __future__ import annotations

from types import SimpleNamespace

from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.services import async_job_service
from polio_domain.enums import AsyncJobStatus


def _completed_run() -> DiagnosisRun:
    run = DiagnosisRun(project_id="project-1", status="COMPLETED")
    run.id = "run-1"
    run.result_payload = '{"headline":"h","strengths":["s"],"gaps":["g"],"recommended_focus":"f","risk_level":"warning"}'
    return run


def test_ensure_default_report_job_queues_when_missing(monkeypatch) -> None:
    created_payload: dict[str, object] = {}
    dispatched: list[str] = []

    monkeypatch.setattr(async_job_service, "get_latest_report_artifact_for_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        async_job_service,
        "get_latest_job_for_resource",
        lambda db, *, resource_type, resource_id: None,
    )

    def fake_create_async_job(db, **kwargs):  # noqa: ANN001, ANN003
        created_payload.update(kwargs)
        return SimpleNamespace(id="report-job-1")

    monkeypatch.setattr(async_job_service, "create_async_job", fake_create_async_job)
    monkeypatch.setattr(async_job_service, "dispatch_job_if_enabled", lambda job_id: dispatched.append(job_id))

    decision = async_job_service.ensure_default_diagnosis_report_job(
        SimpleNamespace(),
        run=_completed_run(),
        owner_user_id="owner-1",
        fallback_target_university="Uni",
        fallback_target_major="Major",
    )

    assert decision == "queued"
    assert created_payload["resource_type"] == "diagnosis_report"
    assert created_payload["resource_id"] == "run-1"
    assert created_payload["payload"]["report_mode"] == "premium_10p"
    assert created_payload["payload"]["trigger"] == "diagnosis_auto"
    assert dispatched == ["report-job-1"]


def test_ensure_default_report_job_reuses_ready_artifact(monkeypatch) -> None:
    ready_artifact = SimpleNamespace(id="artifact-1", status="READY")
    monkeypatch.setattr(async_job_service, "get_latest_report_artifact_for_run", lambda *args, **kwargs: ready_artifact)
    monkeypatch.setattr(async_job_service, "report_artifact_storage_key", lambda artifact: "exports/report.pdf")
    monkeypatch.setattr(
        async_job_service,
        "get_latest_job_for_resource",
        lambda db, *, resource_type, resource_id: None,
    )

    decision = async_job_service.ensure_default_diagnosis_report_job(
        SimpleNamespace(),
        run=_completed_run(),
        owner_user_id=None,
        fallback_target_university=None,
        fallback_target_major=None,
    )

    assert decision == "reused_ready_artifact"


def test_ensure_default_report_job_does_not_requeue_after_failure(monkeypatch) -> None:
    failed_artifact = SimpleNamespace(id="artifact-fail", status="FAILED")
    monkeypatch.setattr(async_job_service, "get_latest_report_artifact_for_run", lambda *args, **kwargs: failed_artifact)
    monkeypatch.setattr(async_job_service, "report_artifact_storage_key", lambda artifact: None)

    decision = async_job_service.ensure_default_diagnosis_report_job(
        SimpleNamespace(),
        run=_completed_run(),
        owner_user_id=None,
        fallback_target_university=None,
        fallback_target_major=None,
    )

    assert decision == "already_failed_artifact"


def test_ensure_default_report_job_respects_existing_report_job(monkeypatch) -> None:
    monkeypatch.setattr(async_job_service, "get_latest_report_artifact_for_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(async_job_service, "report_artifact_storage_key", lambda artifact: None)
    monkeypatch.setattr(
        async_job_service,
        "get_latest_job_for_resource",
        lambda db, *, resource_type, resource_id: SimpleNamespace(
            id="job-2",
            status=AsyncJobStatus.RUNNING.value,
        ),
    )

    decision = async_job_service.ensure_default_diagnosis_report_job(
        SimpleNamespace(),
        run=_completed_run(),
        owner_user_id=None,
        fallback_target_university=None,
        fallback_target_major=None,
    )

    assert decision == "job_in_progress"


def test_dispatch_diagnosis_job_does_not_fail_when_report_bootstrap_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        async_job_service,
        "_run_async_callable",
        lambda func, *args, **kwargs: _completed_run(),
    )
    monkeypatch.setattr(
        async_job_service,
        "ensure_default_diagnosis_report_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bootstrap error")),
    )

    diagnosis_job = SimpleNamespace(
        job_type="diagnosis",
        resource_id="run-1",
        project_id="project-1",
        payload={
            "run_id": "run-1",
            "project_id": "project-1",
            "owner_user_id": "owner-1",
            "auto_report_mode": "premium_10p",
            "auto_report_include_appendix": True,
            "auto_report_include_citations": True,
        },
    )

    async_job_service._dispatch_job(SimpleNamespace(), diagnosis_job)
