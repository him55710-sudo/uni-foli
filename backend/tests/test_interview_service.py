from __future__ import annotations

import asyncio
from types import SimpleNamespace

from unifoli_api.services.diagnosis_service import DiagnosisResult
from unifoli_api.services.interview_service import InterviewEvaluation, InterviewQuestionSet, InterviewService
from unifoli_api.services.interview_question_strategy import (
    infer_major_track_from_texts,
    major_strategy_prompt_block,
)


def _diagnosis() -> DiagnosisResult:
    return DiagnosisResult.model_validate(
        {
            "headline": "로봇 센서 탐구가 강점인 학생부",
            "strengths": ["로봇 센서 오차를 비교하고 한계를 기록함"],
            "gaps": ["전공 연결 설명이 짧음"],
            "recommended_focus": "대표 활동의 방법과 한계를 면접 답변으로 압축",
            "risk_level": "warning",
            "record_completion_state": "finalized",
            "citations": [
                {
                    "source_label": "학생부",
                    "page_number": 2,
                    "excerpt": "로봇 센서 오차를 비교하고 보정 방법의 한계를 기록함",
                    "relevance_score": 0.82,
                }
            ],
        }
    )


def test_generate_questions_uses_structured_llm_response(monkeypatch) -> None:
    class FakeClient:
        async def generate_json(self, *, response_model, prompt, **kwargs):  # noqa: ANN003
            assert "로봇 센서 오차" in prompt
            assert "Killer Questions" in prompt
            assert "Logic Trap" in prompt
            assert "전공별 질문 전략" in prompt
            assert "조건 A가 바뀌었다면" in prompt
            assert "전문 용어의 근본 원리" in prompt
            assert response_model is InterviewQuestionSet
            return response_model.model_validate(
                {
                    "questions": [
                        {
                            "id": "llm-q1",
                            "category": "탐구 과정 검증",
                            "strategy": "Logic Trap",
                            "question": "로봇 센서 오차 비교 활동에서 본인이 직접 바꾼 실험 조건은 무엇인가요?",
                            "rationale": "학생부 직접 근거를 면접 답변으로 방어하는지 확인합니다.",
                            "answer_frame": "조건 - 판단 - 결과 - 한계 순서로 답변합니다.",
                            "avoid": "결과만 말하는 답변",
                            "expected_evidence_ids": ["학생부 p.2"],
                        }
                    ]
                }
            )

    monkeypatch.setattr(
        "unifoli_api.services.interview_service.resolve_llm_runtime",
        lambda **kwargs: SimpleNamespace(client=FakeClient()),
    )

    questions = asyncio.run(InterviewService().generate_questions(_diagnosis()))

    assert questions[0].id == "llm-q1"
    assert questions[0].strategy == "Logic Trap"
    assert questions[0].answer_frame
    assert "로봇 센서" in questions[0].question
    assert len(questions) >= 3


def test_generate_questions_falls_back_to_grounded_questions_when_llm_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        "unifoli_api.services.interview_service.resolve_llm_runtime",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no model")),
    )

    questions = asyncio.run(InterviewService().generate_questions(_diagnosis()))

    assert questions
    assert any("로봇 센서" in question.question for question in questions)
    assert any(question.strategy in {"Logic Trap", "전공 철학"} for question in questions)
    assert all("..." not in question.question for question in questions)


def test_evaluate_answer_uses_llm_rubric_and_normalizes_axes(monkeypatch) -> None:
    class FakeClient:
        async def generate_json(self, *, response_model, prompt, **kwargs):  # noqa: ANN003
            assert response_model is InterviewEvaluation
            assert "구체성" in prompt
            assert "follow_up_questions" in prompt
            assert "치명적인 한계" in prompt
            return response_model.model_validate(
                {
                    "score": 95,
                    "axes_scores": {
                        "구체성": 90,
                        "진정성": 84,
                        "학생부 근거 활용": 88,
                        "전공 연결성": 82,
                        "논리적 인과관계": 86,
                    },
                    "feedback": "학생부 근거와 본인 역할을 잘 연결했습니다.",
                    "coaching_advice": "결과의 한계를 한 문장 더 붙이세요.",
                    "follow_up_questions": [
                        "로봇 센서 오차의 근본 원리를 어떤 자료로 확인했나요?",
                        "조건이 달라졌다면 보정 결과는 어떻게 바뀌었나요?",
                    ],
                }
            )

    monkeypatch.setattr(
        "unifoli_api.services.interview_service.resolve_llm_runtime",
        lambda **kwargs: SimpleNamespace(client=FakeClient()),
    )

    evaluation = asyncio.run(
        InterviewService().evaluate_answer(
            question="활동을 설명해 주세요.",
            answer="로봇 센서 오차 비교 활동에서 조건을 바꾸고 한계를 배웠으며 전공과 연결했습니다.",
            context="로봇 센서 오차를 비교하고 보정 방법의 한계를 기록함",
        )
    )

    assert evaluation.score == 86
    assert evaluation.grade == "A"
    assert "A 등급" in evaluation.grade_label
    assert evaluation.axes_scores["학생부 근거 활용"] == 88
    assert evaluation.axes_scores["논리적 인과관계"] == 86
    assert len(evaluation.follow_up_questions) == 2


def test_evaluate_answer_fallback_is_not_constant(monkeypatch) -> None:
    monkeypatch.setattr(
        "unifoli_api.services.interview_service.resolve_llm_runtime",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no model")),
    )

    weak = asyncio.run(InterviewService().evaluate_answer(question="질문", answer="열심히 했습니다.", context=""))
    strong = asyncio.run(
        InterviewService().evaluate_answer(
            question="질문",
            answer=(
                "로봇 센서 오차 비교 활동에서 실험 조건을 바꾸고 보고서에 한계를 기록했습니다. "
                "이 과정에서 전공에서 필요한 데이터 해석 역량을 배웠습니다."
            ),
            context="로봇 센서 오차 비교 활동 보고서 한계 기록",
        )
    )

    assert strong.score > weak.score
    assert strong.grade in {"B", "C"}
    assert strong.feedback != weak.feedback
    assert strong.follow_up_questions
    assert any("조건" in item or "한계" in item for item in strong.follow_up_questions)


def test_major_strategy_detects_medical_and_builds_ethics_prompt() -> None:
    assert infer_major_track_from_texts("목표 전공: 의예과", "세포와 면역 탐구") == "bio_medical"

    prompt_block = major_strategy_prompt_block(
        target_context="목표 전공: 의예과",
        evidence_texts=["세포 실험에서 변인 통제를 기록함"],
    )

    assert "의학·보건·생명" in prompt_block
    assert "자기결정권" in prompt_block
    assert "생물학적 변이성" in prompt_block
