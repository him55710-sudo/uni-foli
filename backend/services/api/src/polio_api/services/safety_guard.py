# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from polio_api.services.quality_control import (
    get_quality_profile,
    normalize_quality_level,
    serialize_quality_level_info,
)
from polio_domain.enums import QualityLevel


class SafetyFlag(str, Enum):
    LEVEL_OVERFLOW = "level_overflow"
    FEASIBILITY_RISK = "feasibility_risk"
    FABRICATION_RISK = "fabrication_risk"
    AI_SMELL_HIGH = "ai_smell_high"
    REFERENCE_UNSUPPORTED = "reference_unsupported"


@dataclass(frozen=True)
class SafetyDimension:
    key: str
    label: str
    score: int
    status: str
    detail: str
    matched_count: int = 0
    unsupported_count: int = 0


@dataclass
class SafetyCheckResult:
    safety_score: int
    flags: dict[str, str]
    recommended_level: str
    downgraded: bool = False
    summary: str = ""
    checks: dict[str, SafetyDimension] = field(default_factory=dict)


_ADVANCED_TERMS = [
    r"편미분",
    r"양자역학",
    r"리만",
    r"라그랑지안",
    r"베이지안",
    r"확률분포",
    r"미분방정식",
    r"신경망",
    r"머신러닝 모델",
    r"SCI",
    r"논문 게재",
    r"학회 발표",
]

_FEASIBILITY_PATTERNS = [
    r"대규모 설문",
    r"수백 명",
    r"대학 연구실",
    r"장기 추적",
    r"직접 제작했다",
    r"직접 실험을 진행했다",
    r"실험군",
    r"대조군",
    r"현장 인터뷰",
    r"전문 장비",
]

_EXPERIENCE_PATTERNS = [
    r"직접 실험",
    r"실험을 진행",
    r"실험을 수행",
    r"인터뷰를 진행",
    r"설문을 진행",
    r"측정했다",
    r"직접 제작",
    r"데이터를 수집",
    r"현장을 방문",
    r"논문을 읽고 분석",
]

_AI_SMELL_PATTERNS = [
    r"특히 주목할 만한 점은",
    r"종합적으로 살펴보면",
    r"이러한 맥락에서",
    r"한편으로는",
    r"시사하는 바가 크다",
    r"의미 있는 인사이트",
    r"확장 가능성을 보여준다",
    r"다층적으로 분석",
]

_REFERENCE_PATTERNS = [
    r"연구에 따르면",
    r"논문",
    r"저널",
    r"출처",
    r"참고문헌",
    r"선행연구",
]

_NUMERIC_PATTERN = re.compile(r"p\s*[<=>]\s*0\.\d+|\d+(?:\.\d+)?%|\d+(?:\.\d+)?명|\d+(?:\.\d+)?회")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _collect_matches(text: str, patterns: list[str]) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(match.group(0) for match in re.finditer(pattern, text, flags=re.IGNORECASE))
    return matches


def _dimension_status(score: int) -> str:
    if score >= 80:
        return "ok"
    if score >= 60:
        return "warning"
    return "critical"


def _build_dimension(
    *,
    key: str,
    label: str,
    score: int,
    detail: str,
    matched_count: int = 0,
    unsupported_count: int = 0,
) -> SafetyDimension:
    return SafetyDimension(
        key=key,
        label=label,
        score=max(0, min(score, 100)),
        status=_dimension_status(score),
        detail=detail,
        matched_count=matched_count,
        unsupported_count=unsupported_count,
    )


def _unsupported_terms(text: str, context_text: str, patterns: list[str]) -> list[str]:
    normalized_context = _normalize_text(context_text)
    hits = _collect_matches(text, patterns)
    return [hit for hit in hits if _normalize_text(hit) not in normalized_context]


def _unsupported_numeric_claims(text: str, context_text: str) -> list[str]:
    report_tokens = {token.group(0).lower() for token in _NUMERIC_PATTERN.finditer(text)}
    context_tokens = {token.group(0).lower() for token in _NUMERIC_PATTERN.finditer(context_text)}
    return sorted(report_tokens - context_tokens)


def run_safety_check(
    report_markdown: str,
    teacher_summary: str,
    requested_level: str,
    turn_count: int,
    reference_count: int,
    turns_text: str = "",
    references_text: str = "",
) -> SafetyCheckResult:
    requested_level = normalize_quality_level(requested_level)
    profile = get_quality_profile(requested_level)

    full_text = "\n".join(part for part in [report_markdown, teacher_summary] if part).strip()
    grounding_text = "\n".join(part for part in [turns_text, references_text] if part).strip()

    flags: dict[str, str] = {}
    checks: dict[str, SafetyDimension] = {}

    advanced_hits = _collect_matches(full_text, _ADVANCED_TERMS)
    unsupported_advanced_hits = _unsupported_terms(full_text, grounding_text, _ADVANCED_TERMS)
    level_score = 100
    if requested_level == QualityLevel.LOW.value:
        level_score -= len(advanced_hits) * 22
    elif requested_level == QualityLevel.MID.value:
        level_score -= max(0, len(advanced_hits) - 1) * 18
    else:
        level_score -= max(0, len(unsupported_advanced_hits) - 1) * 14
    if turn_count < profile.minimum_turn_count:
        level_score -= (profile.minimum_turn_count - turn_count) * 8
    level_detail = (
        "학생 수준에 맞는 표현이 유지되었습니다."
        if level_score >= 80
        else f"심화 표현 {len(advanced_hits)}건이 감지되었고, 학생 맥락으로 확인되지 않은 항목이 {len(unsupported_advanced_hits)}건 있습니다."
    )
    checks["student_fit"] = _build_dimension(
        key=SafetyFlag.LEVEL_OVERFLOW.value,
        label="학생 수준 적합성",
        score=level_score,
        detail=level_detail,
        matched_count=len(advanced_hits),
        unsupported_count=len(unsupported_advanced_hits),
    )
    if checks["student_fit"].status != "ok":
        flags[SafetyFlag.LEVEL_OVERFLOW.value] = level_detail

    feasibility_hits = _unsupported_terms(full_text, grounding_text, _FEASIBILITY_PATTERNS)
    feasibility_score = 100 - len(feasibility_hits) * 18
    if turn_count < profile.minimum_turn_count:
        feasibility_score -= (profile.minimum_turn_count - turn_count) * 10
    feasibility_detail = (
        "학생이 실제로 수행 가능한 범위로 보입니다."
        if feasibility_score >= 80
        else f"수행 난도가 높은 활동 표현 {len(feasibility_hits)}건 또는 맥락 부족이 감지되었습니다."
    )
    checks["feasibility"] = _build_dimension(
        key=SafetyFlag.FEASIBILITY_RISK.value,
        label="수행 가능성",
        score=feasibility_score,
        detail=feasibility_detail,
        matched_count=len(feasibility_hits),
        unsupported_count=len(feasibility_hits),
    )
    if checks["feasibility"].status != "ok":
        flags[SafetyFlag.FEASIBILITY_RISK.value] = feasibility_detail

    unsupported_experience_hits = _unsupported_terms(full_text, grounding_text, _EXPERIENCE_PATTERNS)
    unsupported_numeric = _unsupported_numeric_claims(full_text, grounding_text)
    fabrication_score = 100 - len(unsupported_experience_hits) * 22 - len(unsupported_numeric) * 12
    fabrication_detail = (
        "허위 경험이나 과장된 수치가 확인되지 않았습니다."
        if fabrication_score >= 80
        else (
            f"근거가 확인되지 않은 경험 서술 {len(unsupported_experience_hits)}건, "
            f"맥락에 없는 수치 표현 {len(unsupported_numeric)}건이 감지되었습니다."
        )
    )
    checks["fabrication"] = _build_dimension(
        key=SafetyFlag.FABRICATION_RISK.value,
        label="허위/과장 위험",
        score=fabrication_score,
        detail=fabrication_detail,
        matched_count=len(unsupported_experience_hits) + len(unsupported_numeric),
        unsupported_count=len(unsupported_experience_hits) + len(unsupported_numeric),
    )
    if checks["fabrication"].status != "ok":
        flags[SafetyFlag.FABRICATION_RISK.value] = fabrication_detail

    ai_hits = _collect_matches(full_text, _AI_SMELL_PATTERNS)
    ai_score = 100 - len(ai_hits) * 12
    ai_detail = (
        "학생 말투와 가까운 표현입니다."
        if ai_score >= 80
        else f"범용적이고 AI 냄새가 나는 문구 {len(ai_hits)}건이 감지되었습니다."
    )
    checks["style"] = _build_dimension(
        key=SafetyFlag.AI_SMELL_HIGH.value,
        label="AI 냄새 과다 여부",
        score=ai_score,
        detail=ai_detail,
        matched_count=len(ai_hits),
        unsupported_count=0,
    )
    if checks["style"].status != "ok":
        flags[SafetyFlag.AI_SMELL_HIGH.value] = ai_detail

    reference_mentions = _collect_matches(full_text, _REFERENCE_PATTERNS)
    reference_score = 100
    if reference_count < profile.minimum_reference_count:
        reference_score -= (profile.minimum_reference_count - reference_count) * 30
    if reference_mentions and reference_count == 0:
        reference_score -= 20
    reference_detail = (
        "참고자료 사용 강도가 현재 수준에 맞습니다."
        if reference_score >= 80
        else (
            f"현재 수준은 최소 {profile.minimum_reference_count}개의 참고자료를 요구하거나, "
            "출처 표현에 비해 실제 참고자료가 부족합니다."
        )
    )
    checks["references"] = _build_dimension(
        key=SafetyFlag.REFERENCE_UNSUPPORTED.value,
        label="참고자료 지지 여부",
        score=reference_score,
        detail=reference_detail,
        matched_count=len(reference_mentions),
        unsupported_count=max(profile.minimum_reference_count - reference_count, 0),
    )
    if checks["references"].status != "ok":
        flags[SafetyFlag.REFERENCE_UNSUPPORTED.value] = reference_detail

    safety_score = round(
        sum(
            [
                checks["student_fit"].score,
                checks["feasibility"].score,
                checks["fabrication"].score,
                checks["style"].score,
                checks["references"].score,
            ]
        )
        / 5
    )

    recommended_level = requested_level
    if checks["fabrication"].status == "critical" or safety_score < 45:
        recommended_level = QualityLevel.LOW.value
    elif requested_level == QualityLevel.HIGH.value and (
        checks["student_fit"].status != "ok"
        or checks["feasibility"].status != "ok"
        or checks["references"].status != "ok"
        or safety_score < 70
    ):
        recommended_level = QualityLevel.MID.value
    elif requested_level == QualityLevel.MID.value and (
        checks["student_fit"].status == "critical"
        or checks["fabrication"].status != "ok"
        or safety_score < 60
    ):
        recommended_level = QualityLevel.LOW.value

    downgraded = recommended_level != requested_level
    recommended_profile = get_quality_profile(recommended_level)

    if not flags:
        summary = (
            f"학생 수준과 실제 맥락에 맞는 {recommended_profile.label} 결과입니다. "
            "허위 경험이나 과장 위험이 크게 보이지 않습니다."
        )
    else:
        summary = (
            f"안전성 점검에서 {len(flags)}개의 주의 항목이 감지되었습니다. "
            f"최종 적용 수준은 {recommended_profile.label}입니다."
        )

    return SafetyCheckResult(
        safety_score=safety_score,
        flags=flags,
        recommended_level=recommended_level,
        downgraded=downgraded,
        summary=summary,
        checks=checks,
    )


QUALITY_LEVEL_META = {
    level: serialize_quality_level_info(get_quality_profile(level))
    for level in [QualityLevel.LOW.value, QualityLevel.MID.value, QualityLevel.HIGH.value]
}


def get_quality_meta(level: str | None) -> dict[str, object]:
    return QUALITY_LEVEL_META[normalize_quality_level(level)]
