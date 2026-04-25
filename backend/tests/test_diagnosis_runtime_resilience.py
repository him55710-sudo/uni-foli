from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from unifoli_api.services.diagnosis_runtime_service import (
    SEMANTIC_EXTRACTION_TIMEOUT_SECONDS,
    _apply_llm_invocation_metadata,
    run_diagnosis_run,
)


def test_semantic_timeout_budget_is_expanded() -> None:
    assert SEMANTIC_EXTRACTION_TIMEOUT_SECONDS >= 60.0


def test_diagnosis_invocation_metadata_reads_runtime_tracking_keys() -> None:
    strategy = {
        "actual_llm_provider": "gemini",
        "actual_llm_model": "gemini-requested",
        "fallback_used": False,
        "fallback_reason": None,
    }

    model = _apply_llm_invocation_metadata(
        strategy,
        {
            "last_provider_used": "ollama",
            "last_model_used": "gemma4-fallback",
            "fallback_used": True,
            "fallback_reason": "primary_failed:TimeoutError",
        },
    )

    assert model == "gemma4-fallback"
    assert strategy["actual_llm_provider"] == "ollama"
    assert strategy["actual_llm_model"] == "gemma4-fallback"
    assert strategy["fallback_used"] is True
    assert strategy["fallback_reason"] == "primary_failed:TimeoutError"


def test_runtime_marks_run_failed_when_unhandled_error_occurs(monkeypatch) -> None:
    run = SimpleNamespace(
        id="run-fail-1",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        status_message=None,
        error_message=None,
        project_id="project-1",
    )
    project = SimpleNamespace(id="project-1", title="diagnosis project", target_major="Computer Science", owner_user_id="owner-1")
    owner = SimpleNamespace(id="owner-1", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-1",
        sha256="sha-doc-1",
        content_text="student record evidence text for runtime resilience",
        content_markdown="",
        stored_path=None,
        source_extension=".txt",
        parse_metadata={},
    )

    class _FakeDB:
        def __init__(self) -> None:
            self.commit_count = 0
            self.rollback_count = 0

        def get(self, model, identifier):  # noqa: ANN001, ARG002
            return owner

        def add(self, obj):  # noqa: ANN001, ARG002
            return None

        def commit(self) -> None:
            self.commit_count += 1

        def refresh(self, obj):  # noqa: ANN001, ARG002
            return None

        def rollback(self) -> None:
            self.rollback_count += 1

    fake_db = _FakeDB()

    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_run_with_relations", lambda db, run_id: run)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.get_project", lambda db, project_id, owner_user_id: project)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.combine_project_text", lambda project_id, db: ([document], document.content_text))
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", lambda db, project_id: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service.detect_policy_flags",
        lambda text: (_ for _ in ()).throw(RuntimeError("forced runtime crash")),
    )

    with pytest.raises(RuntimeError, match="forced runtime crash"):
        asyncio.run(
            run_diagnosis_run(
                fake_db,
                run_id="run-fail-1",
                project_id="project-1",
                owner_user_id="owner-1",
                fallback_target_university="Test Univ",
                fallback_target_major="Computer Science",
            )
        )

    assert run.status == "FAILED"
    assert run.status_message == "진단 실행이 실패했습니다."
    assert run.error_message
    assert fake_db.commit_count >= 1
    assert fake_db.rollback_count >= 1

