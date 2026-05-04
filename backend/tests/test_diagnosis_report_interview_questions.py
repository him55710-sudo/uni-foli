from __future__ import annotations

from unifoli_api.schemas.diagnosis import ConsultantSubjectMetricScores, ConsultantSubjectSpecialtyAnalysis
from unifoli_api.services.diagnosis_report_service import _build_interview_questions


def _analysis(summary: str) -> ConsultantSubjectSpecialtyAnalysis:
    return ConsultantSubjectSpecialtyAnalysis.model_validate(
        {
            "subject": "사회",
            "core_record_summary": summary,
            "strengths": ["자료를 비교하고 결론의 한계를 정리함"],
            "weaknesses": ["후속 검증 질문 보완 필요"],
            "score": 78,
            "metric_scores": ConsultantSubjectMetricScores(
                academic_concept_density=76,
                inquiry_process=78,
                student_agency=80,
                major_connection=74,
                expansion_potential=77,
                differentiation=72,
                interview_defense=73,
            ),
            "level": "강함",
            "admissions_meaning": "자료 기반 탐구 역량이 보임",
            "major_connection": "경영학의 시장 분석과 연결 가능",
            "sentence_to_improve": "자료 선택 근거를 더 구체화해야 함",
            "recommended_follow_up": "표본과 지표 신뢰도 검증",
            "interview_question": "자료 선택 기준은 무엇인가요?",
            "evidence_refs": ["사회 p.3"],
        }
    )


def test_report_interview_questions_include_major_specific_business_pressure() -> None:
    questions = _build_interview_questions(
        result={},  # type: ignore[arg-type]
        target_context="목표 전공: 경영학과",
        subject_analyses=[_analysis("소비자 데이터 분석과 ESG 경영 딜레마를 비교함")],
        research_topics=[],
        report_mode="basic",
    )

    assert len(questions) == 6
    questions_text = "\n".join(item.question for item in questions)
    assert "소외시킬 수 있는 계층" in questions_text
    assert any("이해관계자" in item.good_direction or "이해관계자" in item.answer_frame for item in questions)
    assert all(item.answer_frame for item in questions)
