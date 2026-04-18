from __future__ import annotations

from types import SimpleNamespace

from unifoli_api.services.diagnosis_artifact_service import build_diagnosis_artifact_bundle


def _build_score_ready_payload() -> dict[str, object]:
    return {
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
            },
            {
                "key": "universal_specificity",
                "label": "근거 구체성",
                "score": 68,
                "band": "watch",
                "severity": "medium",
                "rationale": "근거 문장 구체성이 확보되었습니다.",
            },
            {
                "key": "relational_narrative",
                "label": "서사적 발전성",
                "score": 72,
                "band": "watch",
                "severity": "medium",
                "rationale": "활동 간 연결성이 확인됩니다.",
            },
            {
                "key": "relational_continuity",
                "label": "탐구의 연속성",
                "score": 70,
                "band": "watch",
                "severity": "medium",
                "rationale": "탐구 흐름이 이어집니다.",
            },
            {
                "key": "cluster_depth",
                "label": "전공 심층성",
                "score": 66,
                "band": "watch",
                "severity": "medium",
                "rationale": "전공 심화 단서가 일부 존재합니다.",
            },
            {
                "key": "cluster_suitability",
                "label": "전공 적합성",
                "score": 74,
                "band": "watch",
                "severity": "medium",
                "rationale": "전공 적합성이 관찰됩니다.",
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
            },
            {
                "id": "major-fit-b",
                "label": "탐구 심화 방향",
                "summary": "탐구 연속성을 보강하는 방향",
            },
            {
                "id": "major-fit-c",
                "label": "근거 밀도 강화",
                "summary": "근거 구체성을 높이는 방향",
            },
            {
                "id": "major-fit-d",
                "label": "예비 후보",
                "summary": "4번째 후보",
            },
        ],
    }


def test_score_ready_fields_exclude_awards_and_keep_private_formula() -> None:
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
        result=_build_score_ready_payload(),
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
    assert summary["scoring_policy"]["awards_excluded"] is True
    assert summary["scoring_policy"]["grade_trend_analysis_included"] is False
    assert summary["scoring_policy"]["recommended_universities_included"] is False
    assert "formula" not in str(summary).lower()
    assert "weight" not in str(summary).lower()
    assert len(summary["major_direction_candidates_top3"]) == 3

    assert "score_snapshot" in chatbot_context
    assert chatbot_context["score_snapshot"]["total_score"] == summary["total_score"]


def test_score_ready_fields_preserve_legacy_summary_shape() -> None:
    bundle = build_diagnosis_artifact_bundle(
        run_id="run-compat",
        project_id="project-compat",
        result={
            "headline": "Compatibility diagnosis",
            "overview": "Narrative overview",
            "strengths": ["strength-1"],
            "gaps": ["gap-1"],
            "recommended_focus": "focus-1",
            "risk_level": "warning",
            "next_actions": ["action-1"],
            "recommended_topics": ["topic-1"],
            "record_completion_state": "finalized",
        },
        documents=[],
    )
    summary = bundle["diagnosis_summary_json"]

    for key in (
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
        assert key in summary

    assert summary["headline"] == "Compatibility diagnosis"
    assert summary["recommended_focus"] == "focus-1"
    assert summary["risk_level"] == "warning"
    assert summary["completion_state"] == "finalized"
    assert summary["stage_aware_recommendation_mode"] == "finalized"
