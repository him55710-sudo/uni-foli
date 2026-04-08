from __future__ import annotations

from polio_api.services.chat_fallback_service import build_conversational_fallback


def test_conversational_fallback_is_contextual_and_not_overly_restrictive() -> None:
    text = build_conversational_fallback(
        user_message="개요를 조금 더 자연스럽게 다듬어줘",
        reason="llm_unavailable",
        summary={
            "selected_topic": "도시 열섬 완화 탐구",
            "thesis_question": "학교 주변 온도 차이를 어떻게 설명할 수 있는가?",
            "confirmed_evidence_points": ["기상청 시간대별 온도 로그", "교내 관측 기록"],
            "unresolved_evidence_gaps": ["샘플 수가 적음"],
        },
    )

    assert "요청 요약" in text
    assert "지금 바로 쓸 수 있는 초안 가이드" in text
    assert "도시 열섬 완화 탐구" in text
    assert "반드시 근거가 필요한 핵심 주장 1개를 먼저 지정하세요." not in text

