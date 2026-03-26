# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from polio_domain.enums import QualityLevel, TurnType


@dataclass(frozen=True)
class QualityControlProfile:
    level: str
    label: str
    emoji: str
    color: str
    description: str
    detail: str
    student_fit: str
    safety_posture: str
    authenticity_policy: str
    hallucination_guardrail: str
    starter_mode: str
    followup_mode: str
    reference_policy: str
    reference_intensity: str
    render_depth: str
    expression_policy: str
    advanced_features_allowed: bool
    max_output_chars: int
    temperature: float
    minimum_turn_count: int
    minimum_reference_count: int
    render_threshold: int


QUALITY_CONTROL_SCHEMA_VERSION = "2026-03-23"


QUALITY_PROFILES: dict[str, QualityControlProfile] = {
    QualityLevel.LOW.value: QualityControlProfile(
        level=QualityLevel.LOW.value,
        label="안전형",
        emoji="🛡️",
        color="emerald",
        description="교과 개념에 충실하고 학생이 실제로 수행 가능한 범위만 사용합니다.",
        detail="낯선 전문어와 과장된 결론을 줄이고, 검증 가능한 사실과 직접 확인 가능한 활동만 남깁니다.",
        student_fit="교과 개념 충실, 안전형",
        safety_posture="교과 개념과 검증 가능성을 최우선으로 둡니다.",
        authenticity_policy="학생이 실제로 한 활동과 확인된 사실만 남깁니다.",
        hallucination_guardrail="없는 실험, 없는 수치, 없는 경험은 자동 차단합니다.",
        starter_mode="핵심 개념 정리와 수행 가능 범위 확인부터 시작",
        followup_mode="용어를 쉽게 풀고, 다음 행동을 좁게 제안",
        reference_policy="optional",
        reference_intensity="none",
        render_depth="교과 개념 설명 + 실제로 가능한 활동 정리",
        expression_policy="짧고 정확한 문장, 과장 없는 1인칭/학생 맥락 중심",
        advanced_features_allowed=False,
        max_output_chars=900,
        temperature=0.2,
        minimum_turn_count=2,
        minimum_reference_count=0,
        render_threshold=45,
    ),
    QualityLevel.MID.value: QualityControlProfile(
        level=QualityLevel.MID.value,
        label="표준형",
        emoji="📝",
        color="blue",
        description="교과 응용과 간단한 확장을 포함하되 학생 수준을 넘지 않게 조절합니다.",
        detail="한 학기 안에 마무리할 수 있는 탐구 질문과 근거 계획을 만들고, 결론의 세기를 통제합니다.",
        student_fit="교과 응용 + 간단한 확장",
        safety_posture="응용은 허용하되 결론의 세기를 보수적으로 유지합니다.",
        authenticity_policy="학생이 말한 활동과 간단한 자료 해석만 허용합니다.",
        hallucination_guardrail="수행과 계획, 사실과 해석을 분리해서 서술합니다.",
        starter_mode="질문 구체화와 증거 계획 설계 중심",
        followup_mode="근거 보강과 결론 세기 조절 중심",
        reference_policy="recommended",
        reference_intensity="light",
        render_depth="교과 응용 + 간단한 분석/소결론",
        expression_policy="설명과 해석의 균형, 안전한 확장만 허용",
        advanced_features_allowed=False,
        max_output_chars=1300,
        temperature=0.35,
        minimum_turn_count=3,
        minimum_reference_count=0,
        render_threshold=60,
    ),
    QualityLevel.HIGH.value: QualityControlProfile(
        level=QualityLevel.HIGH.value,
        label="심화형",
        emoji="🔬",
        color="violet",
        description="심화형이지만 학생이 실제로 말한 맥락과 근거에만 기대어 작성합니다.",
        detail="출처와 학생 실제 경험을 분리해서 쓰며, 근거가 빈약하면 자동으로 더 안전한 수준으로 낮춥니다.",
        student_fit="심화형이지만 학생 실제 맥락 기반",
        safety_posture="심화 연결은 허용하지만 학생 맥락과 출처 분리를 강제합니다.",
        authenticity_policy="학생 경험, 해석, 외부 근거를 반드시 분리합니다.",
        hallucination_guardrail="근거가 빈약하면 자동 강등 후 안전 재작성합니다.",
        starter_mode="심화 질문을 실제 경험과 자료로 좁히는 방식",
        followup_mode="주장·근거·출처를 분리해 심화를 안전하게 유지",
        reference_policy="required",
        reference_intensity="required",
        render_depth="심화 연결 + 출처 기반 해석, 단 학생 실제 맥락 한정",
        expression_policy="전문성보다 학생 현실감 우선, 고교 맥락 밖 비약 금지",
        advanced_features_allowed=True,
        max_output_chars=1700,
        temperature=0.45,
        minimum_turn_count=4,
        minimum_reference_count=1,
        render_threshold=75,
    ),
}


def normalize_quality_level(level: str | None) -> str:
    if not level:
        return QualityLevel.MID.value
    normalized = level.strip().lower()
    if normalized in QUALITY_PROFILES:
        return normalized
    return QualityLevel.MID.value


def get_quality_profile(level: str | None) -> QualityControlProfile:
    return QUALITY_PROFILES[normalize_quality_level(level)]


def list_quality_level_info() -> list[dict[str, object]]:
    return [serialize_quality_level_info(profile) for profile in QUALITY_PROFILES.values()]


def serialize_quality_level_info(profile: QualityControlProfile) -> dict[str, object]:
    return {
        "level": profile.level,
        "label": profile.label,
        "emoji": profile.emoji,
        "color": profile.color,
        "description": profile.description,
        "detail": profile.detail,
        "student_fit": profile.student_fit,
        "safety_posture": profile.safety_posture,
        "authenticity_policy": profile.authenticity_policy,
        "hallucination_guardrail": profile.hallucination_guardrail,
        "starter_mode": profile.starter_mode,
        "followup_mode": profile.followup_mode,
        "reference_policy": profile.reference_policy,
        "reference_intensity": profile.reference_intensity,
        "render_depth": profile.render_depth,
        "expression_policy": profile.expression_policy,
        "advanced_features_allowed": profile.advanced_features_allowed,
        "minimum_turn_count": profile.minimum_turn_count,
        "minimum_reference_count": profile.minimum_reference_count,
        "render_threshold": profile.render_threshold,
    }


def build_render_requirements(
    *,
    quality_level: str | None,
    context_score: int,
    turn_count: int,
    reference_count: int,
) -> dict[str, object]:
    profile = get_quality_profile(quality_level)
    missing: list[str] = []
    if context_score < profile.render_threshold:
        missing.append(f"맥락 점수 {profile.render_threshold - context_score}점 부족")
    if turn_count < profile.minimum_turn_count:
        missing.append(f"대화 턴 {profile.minimum_turn_count - turn_count}개 부족")
    if reference_count < profile.minimum_reference_count:
        missing.append(f"참고자료 {profile.minimum_reference_count - reference_count}개 부족")

    return {
        "required_context_score": profile.render_threshold,
        "minimum_turn_count": profile.minimum_turn_count,
        "minimum_reference_count": profile.minimum_reference_count,
        "current_context_score": context_score,
        "current_turn_count": turn_count,
        "current_reference_count": reference_count,
        "can_render": not missing,
        "missing": missing,
    }


def build_quality_control_metadata(
    *,
    requested_level: str,
    applied_level: str,
    turn_count: int,
    reference_count: int,
    safety_score: int | None = None,
    downgraded: bool = False,
    summary: str | None = None,
    flags: dict[str, str] | None = None,
    checks: dict[str, dict[str, object]] | None = None,
    repair_applied: bool = False,
    repair_strategy: str | None = None,
    advanced_features_requested: bool = False,
    advanced_features_applied: bool = False,
    advanced_features_reason: str | None = None,
) -> dict[str, object]:
    requested_profile = get_quality_profile(requested_level)
    applied_profile = get_quality_profile(applied_level)
    return {
        "schema_version": QUALITY_CONTROL_SCHEMA_VERSION,
        "requested_level": requested_profile.level,
        "requested_label": requested_profile.label,
        "applied_level": applied_profile.level,
        "applied_label": applied_profile.label,
        "student_fit": applied_profile.student_fit,
        "safety_posture": applied_profile.safety_posture,
        "authenticity_policy": applied_profile.authenticity_policy,
        "hallucination_guardrail": applied_profile.hallucination_guardrail,
        "starter_mode": applied_profile.starter_mode,
        "followup_mode": applied_profile.followup_mode,
        "reference_policy": applied_profile.reference_policy,
        "reference_intensity": applied_profile.reference_intensity,
        "render_depth": applied_profile.render_depth,
        "expression_policy": applied_profile.expression_policy,
        "advanced_features_allowed": applied_profile.advanced_features_allowed,
        "advanced_features_requested": advanced_features_requested,
        "advanced_features_applied": advanced_features_applied,
        "advanced_features_reason": advanced_features_reason,
        "minimum_turn_count": applied_profile.minimum_turn_count,
        "minimum_reference_count": applied_profile.minimum_reference_count,
        "turn_count": turn_count,
        "reference_count": reference_count,
        "safety_score": safety_score,
        "downgraded": downgraded,
        "summary": summary,
        "flags": flags or {},
        "checks": checks or {},
        "repair_applied": repair_applied,
        "repair_strategy": repair_strategy,
    }


def resolve_advanced_features(
    *,
    requested: bool,
    quality_level: str | None,
    reference_count: int,
) -> tuple[bool, str]:
    profile = get_quality_profile(quality_level)
    if not requested:
        return False, "고급 확장을 요청하지 않았습니다."
    if not profile.advanced_features_allowed:
        return False, f"{profile.label}에서는 고급 확장을 허용하지 않습니다."
    if reference_count < profile.minimum_reference_count:
        return (
            False,
            f"{profile.label}에서는 참고자료 {profile.minimum_reference_count}개 이상이 있을 때만 고급 확장을 적용합니다.",
        )
    return True, f"{profile.label} 기준과 참고자료 조건을 충족해 고급 확장을 적용합니다."


def build_starter_choices(
    *,
    quality_level: str | None,
    quest_title: str | None,
    target_major: str | None,
    recommended_output_type: str | None,
) -> list[dict[str, object]]:
    profile = get_quality_profile(quality_level)
    quest_label = quest_title or "이번 탐구"
    major_label = target_major or "희망 전공"
    output_label = (recommended_output_type or "탐구 결과물").lower()

    if profile.level == QualityLevel.LOW.value:
        return [
            {
                "id": "low_core_concept",
                "label": "핵심 개념부터 정리",
                "description": "교과 개념과 실제로 가능한 활동 범위를 먼저 맞춥니다.",
                "payload": {
                    "prompt": f"'{quest_label}'에서 먼저 확인해야 할 교과 개념 2개와, 이번 학기 안에 실제로 할 수 있는 활동만 골라 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.STARTER.value,
                },
            },
            {
                "id": "low_finishable_scope",
                "label": "가능한 방법 고르기",
                "description": "학생 수준에서 끝낼 수 있는 방법만 좁힙니다.",
                "payload": {
                    "prompt": f"'{quest_label}'를 {major_label}와 연결하되 학교 안에서 마칠 수 있는 방법 3가지만 좁혀 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.STARTER.value,
                },
            },
            {
                "id": "low_record_sentence",
                "label": "기록 문장 방향 잡기",
                "description": "과장 없는 세특 문장 톤을 먼저 정합니다.",
                "payload": {
                    "prompt": f"'{quest_label}'를 바탕으로 실제 학생 맥락에서 쓸 수 있는 기록 문장 방향만 안전하게 정리해 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.STARTER.value,
                },
            },
        ]

    if profile.level == QualityLevel.HIGH.value:
        return [
            {
                "id": "high_narrow_question",
                "label": "심화 질문 좁히기",
                "description": "심화 질문을 학생 실제 맥락 안으로 좁힙니다.",
                "payload": {
                    "prompt": f"'{quest_label}'를 심화형으로 다루되 학생이 실제로 수행하거나 말한 범위 안에서만 질문을 좁혀 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.STARTER.value,
                },
            },
            {
                "id": "high_source_frame",
                "label": "출처 기반 분석 틀",
                "description": "핵심 주장과 필요한 출처를 먼저 분리합니다.",
                "payload": {
                    "prompt": f"'{quest_label}'로 {output_label}을 만들 때 학생 경험, 해석, 외부 출처를 각각 어떻게 나눌지 틀을 잡아 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.STARTER.value,
                },
            },
            {
                "id": "high_grounded_depth",
                "label": "경험과 심화 연결",
                "description": "실제 활동과 심화 개념의 연결만 남깁니다.",
                "payload": {
                    "prompt": f"'{quest_label}'에서 학생이 직접 한 것과 심화 해석을 구분해, {major_label} 맥락에 맞는 연결만 남겨 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.STARTER.value,
                },
            },
        ]

    return [
        {
            "id": "mid_question",
            "label": "탐구 질문 구체화",
            "description": "교과 응용 질문을 한 학기 안에 끝낼 수 있게 좁힙니다.",
            "payload": {
                "prompt": f"'{quest_label}'를 {major_label}와 연결되는 하나의 구체적인 탐구 질문으로 좁혀 줘.",
                "quality_level": profile.level,
                "choice_kind": TurnType.STARTER.value,
            },
        },
        {
            "id": "mid_evidence_plan",
            "label": "증거 계획 세우기",
            "description": "관찰·자료·비교 포인트를 3개 안팎으로 정리합니다.",
            "payload": {
                "prompt": f"'{quest_label}'로 {output_label}을 만들기 위해 필요한 근거와 기록 포인트를 3개로 정리해 줘.",
                "quality_level": profile.level,
                "choice_kind": TurnType.STARTER.value,
            },
        },
        {
            "id": "mid_safe_conclusion",
            "label": "안전한 결론 톤 잡기",
            "description": "결론은 세게 쓰지 않고 학생 수준으로 맞춥니다.",
            "payload": {
                "prompt": f"'{quest_label}'의 결론을 과장 없이 쓰려면 어떤 표현까지 허용되는지 안전한 기준을 잡아 줘.",
                "quality_level": profile.level,
                "choice_kind": TurnType.STARTER.value,
            },
        },
    ]


def build_followup_choices(
    *,
    quality_level: str | None,
    turn_count: int,
) -> list[dict[str, object]]:
    profile = get_quality_profile(quality_level)

    if profile.level == QualityLevel.LOW.value:
        return [
            {
                "id": f"low_followup_simple_{turn_count}",
                "label": "용어를 더 쉽게 풀기",
                "description": "어려운 표현을 교과 수준으로 낮춥니다.",
                "payload": {
                    "prompt": "방금 내용에서 어려운 표현을 교과 수준 말로 다시 풀어 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.FOLLOW_UP.value,
                },
            },
            {
                "id": f"low_followup_next_step_{turn_count}",
                "label": "지금 할 수 있는 다음 행동",
                "description": "이번 주 안에 할 수 있는 작은 행동으로 좁힙니다.",
                "payload": {
                    "prompt": "지금 수준에서 바로 해볼 수 있는 다음 행동 2가지만 골라 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.FOLLOW_UP.value,
                },
            },
            {
                "id": f"low_followup_record_{turn_count}",
                "label": "세특 문장 한 줄로",
                "description": "과장 없는 기록 문장 톤을 확인합니다.",
                "payload": {
                    "prompt": "이 내용을 세특 문장 한 줄로 쓰면 어떤 톤이 안전한지 보여 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.FOLLOW_UP.value,
                },
            },
        ]

    if profile.level == QualityLevel.HIGH.value:
        return [
            {
                "id": f"high_followup_source_{turn_count}",
                "label": "출처가 필요한 주장만 고르기",
                "description": "학생 경험과 외부 근거를 분리합니다.",
                "payload": {
                    "prompt": "지금까지 나온 내용 중에서 반드시 출처가 필요한 주장만 골라 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.FOLLOW_UP.value,
                },
            },
            {
                "id": f"high_followup_split_{turn_count}",
                "label": "학생이 한 것과 해석 분리",
                "description": "허위 경험 생성 위험을 먼저 줄입니다.",
                "payload": {
                    "prompt": "학생이 실제로 한 것과 그에 대한 해석을 분리해서 정리해 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.FOLLOW_UP.value,
                },
            },
            {
                "id": f"high_followup_school_level_{turn_count}",
                "label": "심화 표현을 고교 수준으로",
                "description": "심화는 유지하되 학생 수준을 넘지 않게 다듬습니다.",
                "payload": {
                    "prompt": "심화 개념은 유지하되 고교 학생이 실제로 쓸 수 있는 표현으로 다시 낮춰 줘.",
                    "quality_level": profile.level,
                    "choice_kind": TurnType.FOLLOW_UP.value,
                },
            },
        ]

    return [
        {
            "id": f"mid_followup_evidence_{turn_count}",
            "label": "근거를 3단계로 정리",
            "description": "주장-근거-기록 포인트를 바로 정리합니다.",
            "payload": {
                "prompt": "지금까지 나온 내용을 주장, 근거, 기록 포인트 3단계로 정리해 줘.",
                "quality_level": profile.level,
                "choice_kind": TurnType.FOLLOW_UP.value,
            },
        },
        {
            "id": f"mid_followup_compare_{turn_count}",
            "label": "비교 포인트 하나 더",
            "description": "교과 응용 범위 안에서 비교 관점을 더합니다.",
            "payload": {
                "prompt": "과하지 않은 비교 포인트를 하나 더 찾아 줘.",
                "quality_level": profile.level,
                "choice_kind": TurnType.FOLLOW_UP.value,
            },
        },
        {
            "id": f"mid_followup_tone_{turn_count}",
            "label": "결론을 안전하게 다듬기",
            "description": "결론의 세기를 학생 수준으로 맞춥니다.",
            "payload": {
                "prompt": "결론이 너무 세지 않도록 안전한 표현으로 다시 다듬어 줘.",
                "quality_level": profile.level,
                "choice_kind": TurnType.FOLLOW_UP.value,
            },
        },
    ]


def build_choice_acknowledgement(*, quality_level: str | None, label: str) -> str:
    profile = get_quality_profile(quality_level)
    return (
        f"[{profile.label}] '{label}' 방향으로 워크샵 맥락을 더 구체화했습니다. "
        f"이 수준에서는 {profile.followup_mode.lower()}에 맞춰 한 단계씩 좁혀 가겠습니다."
    )


def build_message_acknowledgement(*, quality_level: str | None, next_choice_label: str | None) -> str:
    profile = get_quality_profile(quality_level)
    guidance = f"다음으로는 '{next_choice_label}' 쪽으로 이어가면 좋습니다." if next_choice_label else ""
    return (
        f"[{profile.label}] 입력한 내용을 학생 실제 맥락으로 저장했습니다. "
        f"{profile.render_depth}을 목표로 계속 수집합니다. {guidance}".strip()
    )
