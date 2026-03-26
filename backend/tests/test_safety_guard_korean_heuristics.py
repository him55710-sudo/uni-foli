# -*- coding: utf-8 -*-
from __future__ import annotations

from polio_api.services.safety_guard import SafetyFlag, run_safety_check


def test_safety_guard_matches_ungrounded_korean_heuristics() -> None:
    result = run_safety_check(
        report_markdown=(
            "베이지안 개념을 활용해 직접 실험을 진행했다. "
            "대규모 설문 결과 120명 중 83%가 긍정적이었다. "
            "특히 주목할 만한 점은 확장 가능성을 보여준다는 것이다. "
            "연구에 따르면 해당 접근이 효과적이다."
        ),
        teacher_summary="학생은 자료를 읽고 탐구 방향을 정리했다고만 설명했다.",
        requested_level="high",
        turn_count=1,
        reference_count=0,
        turns_text="학생은 자료를 읽고 탐구 방향을 정리했다.",
        references_text="",
    )

    assert result.recommended_level == "low"
    assert SafetyFlag.LEVEL_OVERFLOW.value in result.flags
    assert SafetyFlag.FEASIBILITY_RISK.value in result.flags
    assert SafetyFlag.FABRICATION_RISK.value in result.flags
    assert SafetyFlag.AI_SMELL_HIGH.value in result.flags
    assert SafetyFlag.REFERENCE_UNSUPPORTED.value in result.flags
    assert result.checks["student_fit"].matched_count >= 1
    assert result.checks["student_fit"].unsupported_count == 1
    assert result.checks["style"].matched_count == 2
    assert result.checks["fabrication"].unsupported_count >= 3


def test_safety_guard_preserves_grounded_korean_terms() -> None:
    result = run_safety_check(
        report_markdown=(
            "양자역학 개념을 정리하고, 연구에 따르면 해당 주제와 관련된 선행연구가 있다는 점을 참고했다."
        ),
        teacher_summary="학생은 양자역학 개념을 읽고 핵심 내용을 정리했다.",
        requested_level="high",
        turn_count=4,
        reference_count=1,
        turns_text="학생은 양자역학 개념을 읽고 핵심 내용을 정리했다.",
        references_text="연구에 따르면 해당 주제와 관련된 선행연구가 존재한다.",
    )

    assert result.downgraded is False
    assert result.checks["student_fit"].matched_count >= 1
    assert result.checks["student_fit"].unsupported_count == 0
    assert result.checks["references"].status == "ok"
    assert SafetyFlag.REFERENCE_UNSUPPORTED.value not in result.flags
    assert SafetyFlag.FABRICATION_RISK.value not in result.flags
