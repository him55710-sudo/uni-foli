from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from unifoli_api.core.config import Settings, get_settings
from unifoli_api.core.database import SessionLocal
from unifoli_api.db.models.citation import Citation
from unifoli_api.db.models.policy_flag import PolicyFlag
from unifoli_api.db.models.response_trace import ResponseTrace
from unifoli_api.db.models.review_task import ReviewTask
from unifoli_api.main import app
from unifoli_api.services.diagnosis_runtime_service import combine_project_text, run_diagnosis_run
from unifoli_api.services.diagnosis_service import DiagnosisGenerationError, DiagnosisResult
from backend.tests.auth_helpers import auth_headers


def test_projects_are_scoped_by_current_jwt_subject() -> None:
    user_a = auth_headers(f"user-a-{uuid4().hex}")
    user_b = auth_headers(f"user-b-{uuid4().hex}")

    with TestClient(app) as client:
        project_a = client.post(
            "/api/v1/projects",
            json={"title": f"Scoped A {uuid4()}", "description": "tenant-a"},
            headers=user_a,
        )
        assert project_a.status_code == 201
        project_a_id = project_a.json()["id"]

        project_b = client.post(
            "/api/v1/projects",
            json={"title": f"Scoped B {uuid4()}", "description": "tenant-b"},
            headers=user_b,
        )
        assert project_b.status_code == 201
        project_b_id = project_b.json()["id"]

        list_a = client.get("/api/v1/projects", headers=user_a)
        assert list_a.status_code == 200
        project_ids = {item["id"] for item in list_a.json()}
        assert project_a_id in project_ids
        assert project_b_id not in project_ids

        forbidden = client.get(f"/api/v1/projects/{project_b_id}", headers=user_a)
        assert forbidden.status_code == 404


def test_diagnosis_run_persists_policy_review_and_citations() -> None:
    headers = auth_headers(f"diagnosis-user-{uuid4().hex}")
    settings = get_settings()
    previous_inline = settings.async_jobs_inline_dispatch
    settings.async_jobs_inline_dispatch = False
    txt_payload = (
        "??뉗쓰 20240001\n"
        "?怨뺤뵭筌?010-1234-5678\n"
        "??李??student@example.com\n"
        "??용뮉 ??뺣짗??筌띾슢諭?野껉퍔荑????μ㉭.\n"
        "??苡?疫꿸퀡以?? measure compare analysis reflect improve feedback evidence inquiry ?癒?カ????釉??뺣뼄.\n"
        "??덇문?? ?怨쀬뵠????쑨??? 獄쎻뫖苡???볧롧몴??類ｂ봺??뉙???쇱벉 ??뺣짗 ?④쑵????怨몃선 ?癒????\n"
    ).encode("utf-8")

    try:
        with TestClient(app) as client:
            project_response = client.post(
                "/api/v1/projects",
                json={
                    "title": f"Diagnosis Runtime {uuid4()}",
                    "description": "runtime safety integration test",
                    "target_major": "Computer Science",
                },
                headers=headers,
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            upload_response = client.post(
                f"/api/v1/projects/{project_id}/uploads",
                files={"file": ("student-record.txt", txt_payload, "text/plain")},
                headers=headers,
            )
            assert upload_response.status_code == 201

            run_response = client.post(
                "/api/v1/diagnosis/runs",
                json={"project_id": project_id},
                headers=headers,
            )
            assert run_response.status_code == 200
            run_payload = run_response.json()
            run_id = run_payload["id"]
            job_id = run_payload["async_job_id"]
            assert run_payload["review_required"] is True
            assert {flag["code"] for flag in run_payload["policy_flags"]} >= {
                "sensitive_email",
                "sensitive_phone",
                "sensitive_student_id",
                "fabrication_request",
            }
            assert job_id

            process_response = client.post(f"/api/v1/jobs/{job_id}/process", headers=headers)
            assert process_response.status_code == 200
            assert process_response.json()["status"] == "succeeded"

            status_response = client.get(f"/api/v1/diagnosis/{run_id}", headers=headers)
            assert status_response.status_code == 200
            status_payload = status_response.json()
            assert status_payload["status"] == "COMPLETED"
            assert status_payload["async_job_status"] == "succeeded"
            assert status_payload["response_trace_id"]
            assert status_payload["citations"]
    finally:
        settings.async_jobs_inline_dispatch = previous_inline

    with SessionLocal() as db:
        flags = list(db.scalars(select(PolicyFlag).where(PolicyFlag.diagnosis_run_id == run_id)))
        review_task = db.scalar(select(ReviewTask).where(ReviewTask.diagnosis_run_id == run_id))
        trace = db.scalar(select(ResponseTrace).where(ResponseTrace.diagnosis_run_id == run_id))
        citations = list(db.scalars(select(Citation).where(Citation.diagnosis_run_id == run_id)))

        assert len(flags) >= 4
        assert review_task is not None
        assert trace is not None
        assert citations


def _build_minimal_result(headline: str) -> DiagnosisResult:
    return DiagnosisResult(
        headline=headline,
        strengths=["grounded strength"],
        gaps=["grounded gap"],
        recommended_focus="next grounded focus",
        risk_level="warning",
    )


def test_runtime_uses_ollama_llm_path_when_configured(monkeypatch) -> None:
    settings = Settings(llm_provider="ollama", ollama_model="gemma4-test", gemini_api_key=None)
    run = SimpleNamespace(
        id="run-1",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        error_message=None,
    )
    project = SimpleNamespace(id="project-1", title="diagnosis project", target_major="Computer Science")
    owner = SimpleNamespace(id="owner-1", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-1",
        sha256="sha-doc-1",
        content_text="grounded evidence text for diagnosis runtime",
        content_markdown="",
        stored_path=None,
        source_extension=".pdf",
        parse_metadata={"parse_confidence": 0.8, "needs_review": False},
    )

    class _FakeDB:
        def get(self, model, user_id):  # noqa: ANN001, ARG002
            return owner

        def add(self, obj):  # noqa: ANN001, ARG002
            return None

        def commit(self):
            return None

        def refresh(self, obj):  # noqa: ANN001, ARG002
            return None

    calls: dict[str, object] = {"llm": 0, "fallback": 0, "model_name": None}

    async def fake_evaluate_student_record(**kwargs):  # noqa: ANN003
        calls["llm"] = int(calls["llm"]) + 1
        return _build_minimal_result("llm path")

    async def fake_extract_semantic_diagnosis(**kwargs):  # noqa: ANN003
        return None

    def fake_build_grounded_diagnosis_result(**kwargs):  # noqa: ANN003
        calls["fallback"] = int(calls["fallback"]) + 1
        return _build_minimal_result("fallback path")

    def fake_create_response_trace(db, **kwargs):  # noqa: ANN001, ANN003
        calls["model_name"] = kwargs["model_name"]
        return SimpleNamespace(id="trace-1"), []

    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_settings", lambda: settings)
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service._diagnosis_llm_strategy",
        lambda: {
            "requested_llm_provider": "ollama",
            "requested_llm_model": "gemma4-test",
            "actual_llm_provider": "ollama",
            "actual_llm_model": "gemma4-test",
            "llm_profile_used": "standard",
            "should_use_llm": True,
            "fallback_used": False,
            "fallback_reason": None,
        },
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_run_with_relations", lambda db, run_id: run)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_project", lambda db, project_id, owner_user_id: project)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.combine_project_text", lambda project_id, db: ([document], document.content_text))
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", lambda db, project_id: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.detect_policy_flags", lambda text: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.evaluate_student_record", fake_evaluate_student_record)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_grounded_diagnosis_result", fake_build_grounded_diagnosis_result)
    monkeypatch.setattr("unifoli_api.services.diagnosis_scoring_service.extract_semantic_diagnosis", fake_extract_semantic_diagnosis)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_response_trace", fake_create_response_trace)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_blueprint_from_signals", lambda db, project, diagnosis_run_id, signals: None)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_blueprint_signals", lambda **kwargs: {})

    completed = asyncio.run(
        run_diagnosis_run(
            _FakeDB(),
            run_id="run-1",
            project_id="project-1",
            owner_user_id="owner-1",
            fallback_target_university="Test Univ",
            fallback_target_major="Computer Science",
        )
    )

    assert completed.status == "COMPLETED"
    assert calls["llm"] == 1
    assert calls["fallback"] == 0
    assert calls["model_name"] == "gemma4-test"


def test_runtime_falls_back_when_provider_not_usable(monkeypatch) -> None:
    settings = Settings(llm_provider="gemini", gemini_api_key="DUMMY_KEY")
    run = SimpleNamespace(
        id="run-2",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        error_message=None,
    )
    project = SimpleNamespace(id="project-2", title="diagnosis project", target_major="Computer Science")
    owner = SimpleNamespace(id="owner-2", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-2",
        sha256="sha-doc-2",
        content_text="grounded fallback evidence text",
        content_markdown="",
        stored_path=None,
        source_extension=".txt",
        parse_metadata={"parse_confidence": 0.7, "needs_review": False},
    )

    class _FakeDB:
        def get(self, model, user_id):  # noqa: ANN001, ARG002
            return owner

        def add(self, obj):  # noqa: ANN001, ARG002
            return None

        def commit(self):
            return None

        def refresh(self, obj):  # noqa: ANN001, ARG002
            return None

    calls: dict[str, object] = {"llm": 0, "fallback": 0, "model_name": None}

    async def fake_evaluate_student_record(**kwargs):  # noqa: ANN003
        calls["llm"] = int(calls["llm"]) + 1
        return _build_minimal_result("llm path")

    async def fake_extract_semantic_diagnosis(**kwargs):  # noqa: ANN003
        return None

    def fake_build_grounded_diagnosis_result(**kwargs):  # noqa: ANN003
        calls["fallback"] = int(calls["fallback"]) + 1
        return _build_minimal_result("fallback path")

    def fake_create_response_trace(db, **kwargs):  # noqa: ANN001, ANN003
        calls["model_name"] = kwargs["model_name"]
        return SimpleNamespace(id="trace-2"), []

    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_settings", lambda: settings)
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service._diagnosis_llm_strategy",
        lambda: {
            "requested_llm_provider": "gemini",
            "requested_llm_model": "gemini-1.5-pro",
            "actual_llm_provider": None,
            "actual_llm_model": None,
            "llm_profile_used": "standard",
            "should_use_llm": False,
            "fallback_used": True,
            "fallback_reason": "llm_unavailable",
        },
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_run_with_relations", lambda db, run_id: run)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_project", lambda db, project_id, owner_user_id: project)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.combine_project_text", lambda project_id, db: ([document], document.content_text))
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", lambda db, project_id: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.detect_policy_flags", lambda text: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.evaluate_student_record", fake_evaluate_student_record)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_grounded_diagnosis_result", fake_build_grounded_diagnosis_result)
    monkeypatch.setattr("unifoli_api.services.diagnosis_scoring_service.extract_semantic_diagnosis", fake_extract_semantic_diagnosis)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_response_trace", fake_create_response_trace)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_blueprint_from_signals", lambda db, project, diagnosis_run_id, signals: None)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_blueprint_signals", lambda **kwargs: {})

    completed = asyncio.run(
        run_diagnosis_run(
            _FakeDB(),
            run_id="run-2",
            project_id="project-2",
            owner_user_id="owner-2",
            fallback_target_university="Test Univ",
            fallback_target_major="Computer Science",
        )
    )

    assert completed.status == "COMPLETED"
    assert calls["llm"] == 0
    assert calls["fallback"] == 1
    assert calls["model_name"] == "grounded-fallback"


def test_runtime_falls_back_when_diagnosis_generation_times_out(monkeypatch) -> None:
    settings = Settings(
        llm_provider="ollama",
        ollama_model="gemma4-test",
        gemini_api_key=None,
        diagnosis_generation_timeout_seconds=0.01,
    )
    run = SimpleNamespace(
        id="run-timeout-1",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        error_message=None,
    )
    project = SimpleNamespace(id="project-timeout-1", title="diagnosis project", target_major="Computer Science")
    owner = SimpleNamespace(id="owner-timeout-1", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-timeout-1",
        sha256="sha-doc-timeout-1",
        content_text="timeout fallback coverage text",
        content_markdown="",
        stored_path=None,
        source_extension=".pdf",
        parse_metadata={"parse_confidence": 0.8, "needs_review": False},
    )

    class _FakeDB:
        def get(self, model, user_id):  # noqa: ANN001, ARG002
            return owner

        def add(self, obj):  # noqa: ANN001, ARG002
            return None

        def commit(self):
            return None

        def refresh(self, obj):  # noqa: ANN001, ARG002
            return None

    async def fake_evaluate_student_record(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        return _build_minimal_result("llm path should timeout")

    def fake_build_grounded_diagnosis_result(**kwargs):  # noqa: ANN003
        return _build_minimal_result("fallback path")

    def fake_create_response_trace(db, **kwargs):  # noqa: ANN001, ANN003
        return SimpleNamespace(id="trace-timeout-1"), []

    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_settings", lambda: settings)
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service._diagnosis_llm_strategy",
        lambda: {
            "requested_llm_provider": "ollama",
            "requested_llm_model": "gemma4-test",
            "actual_llm_provider": "ollama",
            "actual_llm_model": "gemma4-test",
            "llm_profile_used": "standard",
            "should_use_llm": True,
            "fallback_used": False,
            "fallback_reason": None,
        },
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_run_with_relations", lambda db, run_id: run)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_project", lambda db, project_id, owner_user_id: project)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.combine_project_text", lambda project_id, db: ([document], document.content_text))
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", lambda db, project_id: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.detect_policy_flags", lambda text: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.evaluate_student_record", fake_evaluate_student_record)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_grounded_diagnosis_result", fake_build_grounded_diagnosis_result)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_response_trace", fake_create_response_trace)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_blueprint_from_signals", lambda db, project, diagnosis_run_id, signals: None)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_blueprint_signals", lambda **kwargs: {})

    completed = asyncio.run(
        run_diagnosis_run(
            _FakeDB(),
            run_id="run-timeout-1",
            project_id="project-timeout-1",
            owner_user_id="owner-timeout-1",
            fallback_target_university="Test Univ",
            fallback_target_major="Computer Science",
        )
    )

    payload = DiagnosisResult.model_validate_json(completed.result_payload)
    assert completed.status == "COMPLETED"
    assert completed.status != "RUNNING"
    assert payload.fallback_used is True
    assert payload.fallback_reason == "diagnosis_generation_timeout"
    assert payload.actual_llm_provider == "deterministic_fallback"
    assert payload.actual_llm_model == "grounded-fallback"


def test_runtime_falls_back_when_diagnosis_provider_raises(monkeypatch) -> None:
    settings = Settings(llm_provider="ollama", ollama_model="gemma4-test", gemini_api_key=None)
    run = SimpleNamespace(
        id="run-provider-1",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        error_message=None,
    )
    project = SimpleNamespace(id="project-provider-1", title="diagnosis project", target_major="Computer Science")
    owner = SimpleNamespace(id="owner-provider-1", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-provider-1",
        sha256="sha-doc-provider-1",
        content_text="provider fallback coverage text",
        content_markdown="",
        stored_path=None,
        source_extension=".pdf",
        parse_metadata={"parse_confidence": 0.8, "needs_review": False},
    )

    class _FakeDB:
        def get(self, model, user_id):  # noqa: ANN001, ARG002
            return owner

        def add(self, obj):  # noqa: ANN001, ARG002
            return None

        def commit(self):
            return None

        def refresh(self, obj):  # noqa: ANN001, ARG002
            return None

    async def fake_evaluate_student_record(**kwargs):  # noqa: ANN003
        raise DiagnosisGenerationError(reason_code="provider_error", detail="forced provider error")

    def fake_build_grounded_diagnosis_result(**kwargs):  # noqa: ANN003
        return _build_minimal_result("fallback path")

    def fake_create_response_trace(db, **kwargs):  # noqa: ANN001, ANN003
        return SimpleNamespace(id="trace-provider-1"), []

    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_settings", lambda: settings)
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service._diagnosis_llm_strategy",
        lambda: {
            "requested_llm_provider": "ollama",
            "requested_llm_model": "gemma4-test",
            "actual_llm_provider": "ollama",
            "actual_llm_model": "gemma4-test",
            "llm_profile_used": "standard",
            "should_use_llm": True,
            "fallback_used": False,
            "fallback_reason": None,
        },
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_run_with_relations", lambda db, run_id: run)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_project", lambda db, project_id, owner_user_id: project)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.combine_project_text", lambda project_id, db: ([document], document.content_text))
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", lambda db, project_id: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.detect_policy_flags", lambda text: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.evaluate_student_record", fake_evaluate_student_record)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_grounded_diagnosis_result", fake_build_grounded_diagnosis_result)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_response_trace", fake_create_response_trace)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_blueprint_from_signals", lambda db, project, diagnosis_run_id, signals: None)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_blueprint_signals", lambda **kwargs: {})

    completed = asyncio.run(
        run_diagnosis_run(
            _FakeDB(),
            run_id="run-provider-1",
            project_id="project-provider-1",
            owner_user_id="owner-provider-1",
            fallback_target_university="Test Univ",
            fallback_target_major="Computer Science",
        )
    )

    payload = DiagnosisResult.model_validate_json(completed.result_payload)
    assert completed.status == "COMPLETED"
    assert completed.status != "RUNNING"
    assert payload.fallback_used is True
    assert payload.fallback_reason == "diagnosis_generation_provider_error"
    assert payload.actual_llm_provider == "deterministic_fallback"
    assert payload.actual_llm_model == "grounded-fallback"


def test_runtime_falls_back_when_diagnosis_model_not_found(monkeypatch) -> None:
    settings = Settings(llm_provider="ollama", ollama_model="missing-model", gemini_api_key=None)
    run = SimpleNamespace(
        id="run-model-not-found-1",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        error_message=None,
    )
    project = SimpleNamespace(id="project-model-not-found-1", title="diagnosis project", target_major="Computer Science")
    owner = SimpleNamespace(id="owner-model-not-found-1", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-model-not-found-1",
        sha256="sha-doc-model-not-found-1",
        content_text="model not found fallback coverage text",
        content_markdown="",
        stored_path=None,
        source_extension=".pdf",
        parse_metadata={"parse_confidence": 0.8, "needs_review": False},
    )

    class _FakeDB:
        def get(self, model, user_id):  # noqa: ANN001, ARG002
            return owner

        def add(self, obj):  # noqa: ANN001, ARG002
            return None

        def commit(self):
            return None

        def refresh(self, obj):  # noqa: ANN001, ARG002
            return None

    async def fake_evaluate_student_record(**kwargs):  # noqa: ANN003
        raise DiagnosisGenerationError(reason_code="model_not_found", detail="forced missing model")

    def fake_build_grounded_diagnosis_result(**kwargs):  # noqa: ANN003
        return _build_minimal_result("fallback path")

    def fake_create_response_trace(db, **kwargs):  # noqa: ANN001, ANN003
        return SimpleNamespace(id="trace-model-not-found-1"), []

    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_settings", lambda: settings)
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service._diagnosis_llm_strategy",
        lambda: {
            "requested_llm_provider": "ollama",
            "requested_llm_model": "missing-model",
            "actual_llm_provider": "ollama",
            "actual_llm_model": "missing-model",
            "llm_profile_used": "standard",
            "should_use_llm": True,
            "fallback_used": False,
            "fallback_reason": None,
        },
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_run_with_relations", lambda db, run_id: run)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_project", lambda db, project_id, owner_user_id: project)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.combine_project_text", lambda project_id, db: ([document], document.content_text))
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", lambda db, project_id: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.detect_policy_flags", lambda text: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.evaluate_student_record", fake_evaluate_student_record)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_grounded_diagnosis_result", fake_build_grounded_diagnosis_result)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_response_trace", fake_create_response_trace)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_blueprint_from_signals", lambda db, project, diagnosis_run_id, signals: None)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_blueprint_signals", lambda **kwargs: {})

    completed = asyncio.run(
        run_diagnosis_run(
            _FakeDB(),
            run_id="run-model-not-found-1",
            project_id="project-model-not-found-1",
            owner_user_id="owner-model-not-found-1",
            fallback_target_university="Test Univ",
            fallback_target_major="Computer Science",
        )
    )

    payload = DiagnosisResult.model_validate_json(completed.result_payload)
    assert completed.status == "COMPLETED"
    assert payload.fallback_used is True
    assert payload.fallback_reason == "diagnosis_generation_model_not_found"
    assert payload.actual_llm_provider == "deterministic_fallback"
    assert payload.actual_llm_model == "grounded-fallback"


def test_runtime_keeps_completed_diagnosis_when_blueprint_generation_fails(monkeypatch) -> None:
    settings = Settings(llm_provider="gemini", gemini_api_key="DUMMY_KEY")
    run = SimpleNamespace(
        id="run-3",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        error_message=None,
        project_id="project-3",
    )
    project = SimpleNamespace(id="project-3", title="diagnosis project", target_major="Computer Science")
    owner = SimpleNamespace(id="owner-3", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-3",
        sha256="sha-doc-3",
        content_text="grounded fallback evidence text",
        content_markdown="",
        stored_path=None,
        source_extension=".txt",
        parse_metadata={"parse_confidence": 0.7, "needs_review": False},
    )

    class _FakeDB:
        def __init__(self) -> None:
            self.commit_count = 0
            self.rollback_count = 0

        def get(self, model, user_id):  # noqa: ANN001, ARG002
            return owner

        def add(self, obj):  # noqa: ANN001, ARG002
            return None

        def commit(self):
            self.commit_count += 1

        def refresh(self, obj):  # noqa: ANN001, ARG002
            return None

        def rollback(self):
            self.rollback_count += 1

    fake_db = _FakeDB()

    def fake_build_grounded_diagnosis_result(**kwargs):  # noqa: ANN003
        return _build_minimal_result("fallback path")

    def fake_create_response_trace(db, **kwargs):  # noqa: ANN001, ANN003
        return SimpleNamespace(id="trace-3"), []

    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_settings", lambda: settings)
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service._diagnosis_llm_strategy",
        lambda: {
            "requested_llm_provider": "gemini",
            "requested_llm_model": "gemini-1.5-pro",
            "actual_llm_provider": None,
            "actual_llm_model": None,
            "llm_profile_used": "standard",
            "should_use_llm": False,
            "fallback_used": True,
            "fallback_reason": "llm_unavailable",
        },
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_run_with_relations", lambda db, run_id: run)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_project", lambda db, project_id, owner_user_id: project)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.combine_project_text", lambda project_id, db: ([document], document.content_text))
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", lambda db, project_id: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.detect_policy_flags", lambda text: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_grounded_diagnosis_result", fake_build_grounded_diagnosis_result)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_response_trace", fake_create_response_trace)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_blueprint_signals", lambda **kwargs: {})
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service.create_blueprint_from_signals",
        lambda db, project, diagnosis_run_id, signals: (_ for _ in ()).throw(RuntimeError("blueprint unavailable")),
    )

    completed = asyncio.run(
        run_diagnosis_run(
            fake_db,
            run_id="run-3",
            project_id="project-3",
            owner_user_id="owner-3",
            fallback_target_university="Test Univ",
            fallback_target_major="Computer Science",
        )
    )

    assert completed.status == "COMPLETED"
    assert fake_db.commit_count >= 1
    assert fake_db.rollback_count == 1


def test_runtime_handles_sqlite_disk_full_during_chunk_hydration(monkeypatch) -> None:
    settings = Settings(llm_provider="gemini", gemini_api_key="DUMMY_KEY")
    run = SimpleNamespace(
        id="run-disk-full",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        error_message=None,
        project_id="project-disk-full",
    )
    project = SimpleNamespace(id="project-disk-full", title="diagnosis project", target_major="Computer Science")
    owner = SimpleNamespace(id="owner-disk-full", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-disk-full",
        sha256="sha-doc-disk-full",
        content_text="disk pressure fallback evidence text",
        content_markdown="",
        stored_path=None,
        source_extension=".txt",
        parse_metadata={"parse_confidence": 0.7, "needs_review": False},
    )

    class _FakeDB:
        def __init__(self) -> None:
            self.rollback_count = 0

        def get(self, model, user_id):  # noqa: ANN001, ARG002
            return owner

        def add(self, obj):  # noqa: ANN001, ARG002
            return None

        def commit(self):
            return None

        def refresh(self, obj):  # noqa: ANN001, ARG002
            return None

        def rollback(self):
            self.rollback_count += 1

    fake_db = _FakeDB()

    def fake_build_grounded_diagnosis_result(**kwargs):  # noqa: ANN003
        return _build_minimal_result("fallback path")

    def fake_create_response_trace(db, **kwargs):  # noqa: ANN001, ANN003
        assert kwargs["chunks"] == []
        return SimpleNamespace(id="trace-disk-full"), []

    def raise_disk_full(db, project_id):  # noqa: ANN001, ARG001
        raise OperationalError("SELECT ...", {"project_id": project_id}, Exception("database or disk is full"))

    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_settings", lambda: settings)
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service._diagnosis_llm_strategy",
        lambda: {
            "requested_llm_provider": "gemini",
            "requested_llm_model": "gemini-1.5-pro",
            "actual_llm_provider": None,
            "actual_llm_model": None,
            "llm_profile_used": "standard",
            "should_use_llm": False,
            "fallback_used": True,
            "fallback_reason": "llm_unavailable",
        },
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_run_with_relations", lambda db, run_id: run)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_project", lambda db, project_id, owner_user_id: project)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.combine_project_text", lambda project_id, db: ([document], document.content_text))
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", raise_disk_full)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.detect_policy_flags", lambda text: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_grounded_diagnosis_result", fake_build_grounded_diagnosis_result)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_response_trace", fake_create_response_trace)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_blueprint_signals", lambda **kwargs: {})
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_blueprint_from_signals", lambda db, project, diagnosis_run_id, signals: None)

    completed = asyncio.run(
        run_diagnosis_run(
            fake_db,
            run_id="run-disk-full",
            project_id="project-disk-full",
            owner_user_id="owner-disk-full",
            fallback_target_university="Test Univ",
            fallback_target_major="Computer Science",
        )
    )

    assert completed.status == "COMPLETED"
    assert fake_db.rollback_count == 1


def test_combine_project_text_uses_pdf_analysis_fallback(monkeypatch) -> None:
    document = SimpleNamespace(
        content_text="",
        content_markdown="",
        parse_metadata={
            "student_record_canonical": {
                "record_type": "korean_student_record_pdf",
            },
            "pdf_analysis": {
                "summary": "summary based fallback text",
                "key_points": ["???뼎 ?????A", "???뼎 ?????B"],
            }
        },
    )
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service.list_documents_for_project",
        lambda db, project_id: [document],
    )

    documents, full_text = combine_project_text("project-1", db=SimpleNamespace())

    assert len(documents) == 1
    assert "summary based fallback text" in full_text
    assert "???뼎 ?????A" in full_text

