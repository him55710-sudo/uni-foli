from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import HTTPException

from unifoli_api.core.config import Settings
from unifoli_api.services.diagnosis_artifact_service import build_diagnosis_artifact_bundle
from unifoli_api.services.diagnosis_copilot_service import build_diagnosis_copilot_brief
from unifoli_api.services.diagnosis_runtime_service import combine_project_text, run_diagnosis_run
from unifoli_api.services.diagnosis_service import DiagnosisResult


def _build_minimal_result(headline: str) -> DiagnosisResult:
    return DiagnosisResult(
        headline=headline,
        strengths=["grounded strength"],
        gaps=["grounded gap"],
        recommended_focus="next grounded focus",
        risk_level="warning",
    )


def test_combine_project_text_returns_structured_error_when_documents_are_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service.list_documents_for_project",
        lambda db, project_id: [],
    )

    try:
        combine_project_text("project-empty", db=SimpleNamespace())
    except HTTPException as exc:
        assert exc.status_code == 400
        assert isinstance(exc.detail, dict)
        assert exc.detail["code"] == "DIAGNOSIS_INPUT_EMPTY"
        assert exc.detail["stage"] == "combine_project_text"
    else:  # pragma: no cover - defensive branch
        raise AssertionError("combine_project_text should raise when no documents are available")


def test_runtime_persists_artifacts_and_survives_trace_persistence_failure(monkeypatch) -> None:
    settings = Settings(llm_provider="ollama", ollama_model="gemma4-test", gemini_api_key=None)
    run = SimpleNamespace(
        id="run-trace-failure",
        policy_flags=[],
        review_tasks=[],
        result_payload=None,
        status="PENDING",
        error_message=None,
        project_id="project-trace-failure",
    )
    project = SimpleNamespace(id="project-trace-failure", title="diagnosis project", target_major="Computer Science")
    owner = SimpleNamespace(id="owner-trace-failure", career="AI Engineering")
    document = SimpleNamespace(
        id="doc-trace-failure",
        sha256="sha-doc-trace-failure",
        content_text="grounded evidence text for persisted diagnosis artifacts",
        content_markdown="",
        stored_path=None,
        source_extension=".pdf",
        parse_metadata={
            "student_record_canonical": {
                "section_coverage": {"missing_sections": ["behavior_opinion"]},
                "major_alignment_hints": [{"hint": "Robotics inquiry aligns with engineering majors."}],
                "timeline_signals": [{"signal": "Grade 2 research activity deepened prototype testing."}],
            }
        },
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

        def scalar(self, stmt):  # noqa: ANN001, ARG002
            return None

    fake_db = _FakeDB()

    async def fake_evaluate_student_record(**kwargs):  # noqa: ANN003
        return _build_minimal_result("artifact-rich diagnosis")

    async def fake_extract_semantic_diagnosis(**kwargs):  # noqa: ANN003
        return None

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
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service.combine_project_text",
        lambda project_id, db: ([document], document.content_text),
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.list_chunks_for_project", lambda db, project_id: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_policy_scan_text", lambda documents: "")
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.detect_policy_flags", lambda text: [])
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.evaluate_student_record", fake_evaluate_student_record)
    monkeypatch.setattr("unifoli_api.services.diagnosis_scoring_service.extract_semantic_diagnosis", fake_extract_semantic_diagnosis)
    monkeypatch.setattr(
        "unifoli_api.services.diagnosis_runtime_service.create_response_trace",
        lambda db, **kwargs: (_ for _ in ()).throw(RuntimeError("trace persistence unavailable")),
    )
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.create_blueprint_from_signals", lambda db, project, diagnosis_run_id, signals: None)
    monkeypatch.setattr("unifoli_api.services.diagnosis_runtime_service.build_blueprint_signals", lambda **kwargs: {})

    completed = asyncio.run(
        run_diagnosis_run(
            fake_db,
            run_id="run-trace-failure",
            project_id="project-trace-failure",
            owner_user_id="owner-trace-failure",
            fallback_target_university="Test Univ",
            fallback_target_major="Computer Science",
        )
    )

    payload = DiagnosisResult.model_validate_json(completed.result_payload)
    assert completed.status == "COMPLETED"
    assert payload.response_trace_id is None
    assert payload.diagnosis_result_json is not None
    assert payload.diagnosis_summary_json is not None
    assert payload.diagnosis_report_markdown
    assert payload.chatbot_context_json is not None
    assert payload.chatbot_context_json["major_alignment_hints"] == ["Robotics inquiry aligns with engineering majors."]
    assert payload.chatbot_context_json["missing_sections"] == ["behavior_opinion"]
    assert "artifact-rich diagnosis" in payload.diagnosis_report_markdown
    assert completed.status_message.startswith("Diagnosis completed")
    assert fake_db.rollback_count >= 1


def test_artifact_summary_exposes_score_fields_without_leaking_formula_and_excludes_awards() -> None:
    result = DiagnosisResult.model_validate(
        {
            "headline": "Score-ready diagnosis",
            "overview": "Grounded narrative overview",
            "strengths": ["evidence-backed strength"],
            "gaps": ["missing evidence gap"],
            "recommended_focus": "next focus",
            "risk_level": "warning",
            "next_actions": ["next action"],
            "recommended_topics": ["recommended topic"],
            "record_completion_state": "ongoing",
            "admission_axes": [
                {
                    "key": "universal_rigor",
                    "label": "학업 및 근거 엄밀성",
                    "score": 76,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "학업 기록 근거가 안정적입니다.",
                    "evidence_hints": [],
                },
                {
                    "key": "universal_specificity",
                    "label": "근거 구체성",
                    "score": 68,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "근거 문장 구체성이 확보되었습니다.",
                    "evidence_hints": [],
                },
                {
                    "key": "relational_narrative",
                    "label": "서사적 발전성",
                    "score": 72,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "활동 간 연결성이 확인됩니다.",
                    "evidence_hints": [],
                },
                {
                    "key": "relational_continuity",
                    "label": "탐구의 연속성",
                    "score": 70,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "탐구 흐름이 이어집니다.",
                    "evidence_hints": [],
                },
                {
                    "key": "cluster_depth",
                    "label": "전공 심층성",
                    "score": 66,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "전공 심화 단서가 일부 존재합니다.",
                    "evidence_hints": [],
                },
                {
                    "key": "cluster_suitability",
                    "label": "전공 적합성",
                    "score": 74,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "전공 적합성이 관찰됩니다.",
                    "evidence_hints": [],
                },
            ],
            "section_analysis": [
                {
                    "key": "교과학습발달상황",
                    "label": "교과학습발달상황",
                    "present": True,
                    "record_count": 5,
                    "note": "기록 충분",
                },
                {
                    "key": "창의적 체험활동",
                    "label": "창의적 체험활동",
                    "present": True,
                    "record_count": 4,
                    "note": "기록 충분",
                },
                {
                    "key": "수상경력",
                    "label": "수상경력",
                    "present": True,
                    "record_count": 9,
                    "note": "제외 대상",
                },
            ],
            "recommended_directions": [
                {
                    "id": "major-fit-a",
                    "label": "AI 융합 방향",
                    "summary": "전공 연계 활동을 강화하는 방향",
                    "why_now": "근거 확보",
                    "complexity": "balanced",
                    "related_axes": ["cluster_suitability"],
                    "topic_candidates": [],
                    "page_count_options": [],
                    "format_recommendations": [],
                    "template_candidates": [],
                },
                {
                    "id": "major-fit-b",
                    "label": "탐구 심화 방향",
                    "summary": "탐구 연속성을 보강하는 방향",
                    "why_now": "연계 강화",
                    "complexity": "balanced",
                    "related_axes": ["relational_continuity"],
                    "topic_candidates": [],
                    "page_count_options": [],
                    "format_recommendations": [],
                    "template_candidates": [],
                },
                {
                    "id": "major-fit-c",
                    "label": "근거 밀도 강화",
                    "summary": "근거 구체성을 높이는 방향",
                    "why_now": "서류 설득력",
                    "complexity": "lighter",
                    "related_axes": ["universal_specificity"],
                    "topic_candidates": [],
                    "page_count_options": [],
                    "format_recommendations": [],
                    "template_candidates": [],
                },
                {
                    "id": "major-fit-d",
                    "label": "예비 후보",
                    "summary": "4번째 후보",
                    "why_now": "후순위",
                    "complexity": "lighter",
                    "related_axes": ["universal_rigor"],
                    "topic_candidates": [],
                    "page_count_options": [],
                    "format_recommendations": [],
                    "template_candidates": [],
                },
            ],
        }
    )
    document = SimpleNamespace(
        parse_metadata={
            "student_record_canonical": {
                "attendance": [{"grade": "1"}, {"grade": "2"}],
                "awards": [{"award_name": "교내상"}],
            }
        }
    )

    bundle = build_diagnosis_artifact_bundle(
        run_id="run-score-ready",
        project_id="project-score-ready",
        result=result,
        documents=[document],
    )

    summary = bundle["diagnosis_summary_json"]
    chatbot_context = bundle["chatbot_context_json"]

    assert isinstance(summary["total_score"], int)
    assert 0 <= summary["total_score"] <= 100
    assert set(summary["category_scores"].keys()) == {
        "교과/세특",
        "창체",
        "행동특성/종합의견",
        "독서",
        "출결",
        "항목 간 연계성",
        "종합 진로연계성",
    }
    assert "수상경력" not in summary["category_scores"]
    assert len(summary["major_direction_candidates_top3"]) == 3
    assert summary["completion_state"] == "ongoing"
    assert summary["stage_aware_recommendation_mode"] == "ongoing"
    assert summary["scoring_policy"]["awards_excluded"] is True
    assert summary["scoring_policy"]["grade_trend_analysis_included"] is False
    assert summary["scoring_policy"]["recommended_universities_included"] is False
    assert "weight" not in str(summary).lower()
    assert "formula" not in str(summary).lower()

    assert "score_snapshot" in chatbot_context
    assert chatbot_context["score_snapshot"]["total_score"] == summary["total_score"]


def test_artifact_summary_schema_is_backward_compatible_with_existing_narrative_fields() -> None:
    result = DiagnosisResult.model_validate(
        {
            "headline": "Compatibility diagnosis",
            "overview": "Narrative overview",
            "strengths": ["strength-1"],
            "gaps": ["gap-1"],
            "recommended_focus": "focus-1",
            "risk_level": "warning",
            "next_actions": ["action-1"],
            "recommended_topics": ["topic-1"],
            "record_completion_state": "finalized",
        }
    )
    bundle = build_diagnosis_artifact_bundle(
        run_id="run-compat",
        project_id="project-compat",
        result=result,
        documents=[],
    )

    summary = bundle["diagnosis_summary_json"]
    for legacy_key in (
        "headline",
        "overview",
        "recommended_focus",
        "risk_level",
        "strengths",
        "gaps",
        "next_actions",
        "recommended_topics",
        "fallback_used",
        "fallback_reason",
        "evidence_references",
    ):
        assert legacy_key in summary

    assert summary["headline"] == "Compatibility diagnosis"
    assert summary["recommended_focus"] == "focus-1"
    assert summary["risk_level"] == "warning"
    assert summary["completion_state"] == "finalized"
    assert summary["stage_aware_recommendation_mode"] == "finalized"


def test_copilot_brief_uses_persisted_artifact_bundle() -> None:
    payload = DiagnosisResult.model_validate(
        {
            "headline": "Grounded diagnosis headline",
            "strengths": ["evidence-backed strength"],
            "gaps": ["missing evidence gap"],
            "recommended_focus": "next focus",
            "risk_level": "warning",
            "diagnosis_summary_json": {
                "headline": "Grounded diagnosis headline",
                "recommended_focus": "next focus",
                "strengths": ["evidence-backed strength"],
            },
            "chatbot_context_json": {
                "key_strengths": ["evidence-backed strength"],
                "key_weaknesses": ["missing evidence gap"],
                "target_risks": ["target risk"],
                "recommended_activity_topics": ["robotics ethics inquiry"],
                "caution_points": ["needs more verified evidence"],
                "evidence_references": [
                    {
                        "source_label": "Student record",
                        "page_number": 2,
                        "excerpt": "Documented robotics experiment reflection",
                        "relevance_score": 0.81,
                    }
                ],
            },
        }
    )

    class _FakeDB:
        def scalar(self, stmt):  # noqa: ANN001, ARG002
            return SimpleNamespace(result_payload=payload.model_dump_json())

    brief = build_diagnosis_copilot_brief(_FakeDB(), project_id="project-1")

    assert "[Diagnosis Artifact Brief]" in brief
    assert "Grounded diagnosis headline" in brief
    assert "robotics ethics inquiry" in brief
    assert "Student record p.2" in brief


def test_copilot_brief_fallback_text_is_readable_without_artifact_bundle() -> None:
    payload = DiagnosisResult.model_validate(
        {
            "headline": "Grounded diagnosis headline",
            "strengths": ["evidence-backed strength"],
            "gaps": ["missing evidence gap"],
            "recommended_focus": "next focus",
            "risk_level": "warning",
            "next_actions": ["build a better evidence trail"],
            "recommended_topics": ["robotics ethics inquiry"],
            "fallback_used": True,
            "citations": [
                {
                    "source_label": "Student record",
                    "page_number": 3,
                    "excerpt": "Documented lab reflection",
                    "relevance_score": 0.74,
                }
            ],
            "document_quality": {
                "source_mode": "mixed",
                "parse_reliability_score": 62,
                "parse_reliability_band": "medium",
                "needs_review": True,
                "needs_review_documents": 1,
                "total_records": 12,
                "total_word_count": 420,
                "narrative_density": 0.58,
                "evidence_density": 0.61,
                "summary": "Document extraction needs manual review.",
            },
        }
    )

    class _FakeDB:
        def scalar(self, stmt):  # noqa: ANN001, ARG002
            return SimpleNamespace(result_payload=payload.model_dump_json())

        def scalars(self, stmt):  # noqa: ANN001, ARG002
            return []

    brief = build_diagnosis_copilot_brief(_FakeDB(), project_id="project-2")

    assert "[Diagnosis Copilot Brief]" in brief
    assert "Grounded diagnosis headline" in brief
    assert "manual review" in brief
    assert "deterministic fallback mode" in brief
    assert "Student record p.3" in brief
