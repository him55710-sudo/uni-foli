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

