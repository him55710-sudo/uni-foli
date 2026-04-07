from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from polio_api.services.student_record_feature_service import StudentRecordFeatures

AdmissionAxisKey = Literal[
    "major_alignment",
    "inquiry_continuity",
    "evidence_density",
    "process_explanation",
    "authenticity_risk",
]
RiskLevel = Literal["safe", "warning", "danger"]

_SECTION_LABELS: dict[str, str] = {
    "교과학습발달상황": "교과학습발달상황",
    "창의적체험활동": "창의적체험활동",
    "행동특성 및 종합의견": "행동특성 및 종합의견",
    "독서활동": "독서활동",
    "수상경력": "수상경력",
}
_POSITIVE_AXIS_LABELS: dict[str, str] = {
    "major_alignment": "전공 적합성",
    "inquiry_continuity": "탐구 연속성",
    "evidence_density": "증거 밀도",
    "process_explanation": "과정 설명력",
}


class AdmissionAxisResult(BaseModel):
    key: AdmissionAxisKey
    label: str
    score: int = Field(ge=0, le=100)
    band: str
    severity: Literal["low", "medium", "high"]
    rationale: str
    evidence_hints: list[str] = Field(default_factory=list)


class SectionAnalysisItem(BaseModel):
    key: str
    label: str
    present: bool
    record_count: int = Field(ge=0)
    note: str


class DocumentQualitySummary(BaseModel):
    source_mode: str
    parse_reliability_score: int = Field(ge=0, le=100)
    parse_reliability_band: str
    needs_review: bool
    needs_review_documents: int = Field(ge=0)
    total_records: int = Field(ge=0)
    total_word_count: int = Field(ge=0)
    narrative_density: float = Field(ge=0.0, le=1.0)
    evidence_density: float = Field(ge=0.0, le=1.0)
    summary: str


class DiagnosisScoringSheet(BaseModel):
    overview: str
    document_quality: DocumentQualitySummary
    section_analysis: list[SectionAnalysisItem] = Field(default_factory=list)
    admission_axes: list[AdmissionAxisResult] = Field(default_factory=list)
    strengths_candidates: list[str] = Field(default_factory=list)
    gap_candidates: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    next_action_seeds: list[str] = Field(default_factory=list)
    recommended_topics: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    recommended_focus: str


def build_diagnosis_scoring_sheet(
    *,
    features: StudentRecordFeatures,
    project_title: str,
    target_major: str | None,
    target_university: str | None,
) -> DiagnosisScoringSheet:
    section_analysis = _build_section_analysis(features)
    document_quality = _build_document_quality(features)
    admission_axes = _build_admission_axes(features)
    risk_level = _derive_risk_level(admission_axes=admission_axes)

    strengths = _build_strengths(features=features, admission_axes=admission_axes)
    gaps = _build_gaps(features=features, admission_axes=admission_axes)
    risk_flags = _build_risk_flags(features=features, admission_axes=admission_axes)
    next_actions = _build_next_action_seeds(
        features=features,
        admission_axes=admission_axes,
        target_major=target_major,
    )
    recommended_topics = _build_recommended_topics(features=features, target_major=target_major)

    weakest_axis = min(
        (axis for axis in admission_axes if axis.key != "authenticity_risk"),
        key=lambda axis: axis.score,
        default=None,
    )
    weakest_label = weakest_axis.label if weakest_axis else "핵심 평가축"
    target_context = f"{target_university} {target_major}".strip() or target_major or "목표 전공"
    overview = (
        f"{project_title} 기준으로 문서 신뢰도는 {document_quality.parse_reliability_band} 수준이며, "
        f"현재는 {weakest_label} 보강이 우선입니다."
    )
    recommended_focus = (
        f"{target_context} 지원 맥락에서 {weakest_label}을 먼저 보강하세요. "
        "점수는 현재 기록 근거를 기준으로 결정론적으로 계산되었습니다."
    )

    return DiagnosisScoringSheet(
        overview=overview,
        document_quality=document_quality,
        section_analysis=section_analysis,
        admission_axes=admission_axes,
        strengths_candidates=strengths,
        gap_candidates=gaps,
        risk_flags=risk_flags,
        next_action_seeds=next_actions,
        recommended_topics=recommended_topics,
        risk_level=risk_level,
        recommended_focus=recommended_focus,
    )


def _build_section_analysis(features: StudentRecordFeatures) -> list[SectionAnalysisItem]:
    rows: list[SectionAnalysisItem] = []
    for key, label in _SECTION_LABELS.items():
        present = bool(features.section_presence.get(key))
        count = int(features.section_record_counts.get(key) or 0)
        if present and count >= 3:
            note = "기록 수가 충분해 심화 근거로 활용 가능합니다."
        elif present:
            note = "기록은 존재하지만 수가 적어 보강 여지가 있습니다."
        else:
            note = "해당 섹션 기록이 확인되지 않아 보강이 필요합니다."
        rows.append(
            SectionAnalysisItem(
                key=key,
                label=label,
                present=present,
                record_count=max(0, count),
                note=note,
            )
        )
    return rows


def _build_document_quality(features: StudentRecordFeatures) -> DocumentQualitySummary:
    reliability_score = _bounded_int(features.reliability_score * 100.0)
    if reliability_score >= 80:
        reliability_band = "높음"
    elif reliability_score >= 60:
        reliability_band = "보통"
    else:
        reliability_band = "주의"

    summary = (
        f"{features.document_count}개 문서, 총 {features.total_records}개 레코드 기준 "
        f"파싱 신뢰도 {reliability_score}점으로 평가했습니다."
    )
    return DocumentQualitySummary(
        source_mode=features.source_mode,
        parse_reliability_score=reliability_score,
        parse_reliability_band=reliability_band,
        needs_review=features.needs_review,
        needs_review_documents=features.needs_review_documents,
        total_records=max(0, features.total_records),
        total_word_count=max(0, features.total_word_count),
        narrative_density=_clamp(features.narrative_density),
        evidence_density=_clamp(features.evidence_density),
        summary=summary,
    )


def _build_admission_axes(features: StudentRecordFeatures) -> list[AdmissionAxisResult]:
    major_alignment = _bounded_int(
        20
        + features.major_term_overlap_ratio * 58
        + min(features.unique_subject_count, 10) * 2.8
        + (8 if features.section_presence.get("교과학습발달상황") else 0)
    )
    inquiry_continuity = _bounded_int(
        24
        + features.repeated_subject_ratio * 52
        + min(features.total_records, 40) * 0.9
        + (6 if features.section_presence.get("창의적체험활동") else 0)
    )
    evidence_density = _bounded_int(
        20
        + features.evidence_density * 56
        + min(features.evidence_reference_count, 25) * 1.0
    )
    process_explanation = _bounded_int(
        22
        + features.narrative_density * 60
        + min(features.section_record_counts.get("행동특성 및 종합의견", 0), 8) * 2.0
    )
    authenticity_risk = _bounded_int(
        78
        - features.reliability_score * 44
        - features.evidence_density * 20
        - features.repeated_subject_ratio * 10
        + (16 if features.needs_review else 0)
        + (10 if features.total_records < 5 else 0)
    )

    axes: list[AdmissionAxisResult] = []
    axes.append(
        _positive_axis(
            key="major_alignment",
            score=major_alignment,
            rationale=_major_alignment_rationale(major_alignment),
            hints=[
                f"전공 키워드 중첩 비율: {round(features.major_term_overlap_ratio, 3)}",
                f"고유 과목 수: {features.unique_subject_count}",
            ],
        )
    )
    axes.append(
        _positive_axis(
            key="inquiry_continuity",
            score=inquiry_continuity,
            rationale=_inquiry_rationale(inquiry_continuity),
            hints=[
                f"반복 과목 비율: {round(features.repeated_subject_ratio, 3)}",
                f"총 레코드 수: {features.total_records}",
            ],
        )
    )
    axes.append(
        _positive_axis(
            key="evidence_density",
            score=evidence_density,
            rationale=_evidence_rationale(evidence_density),
            hints=[
                f"증거 밀도: {round(features.evidence_density, 3)}",
                f"증거 참조 수: {features.evidence_reference_count}",
            ],
        )
    )
    axes.append(
        _positive_axis(
            key="process_explanation",
            score=process_explanation,
            rationale=_process_rationale(process_explanation),
            hints=[
                f"서술 밀도: {round(features.narrative_density, 3)}",
                f"행동특성/종합의견 레코드: {features.section_record_counts.get('행동특성 및 종합의견', 0)}",
            ],
        )
    )
    axes.append(
        _authenticity_risk_axis(
            score=authenticity_risk,
            hints=[
                f"파싱 신뢰도: {round(features.reliability_score, 3)}",
                f"needs_review 문서 수: {features.needs_review_documents}",
            ],
        )
    )
    return axes


def _positive_axis(
    *,
    key: Literal["major_alignment", "inquiry_continuity", "evidence_density", "process_explanation"],
    score: int,
    rationale: str,
    hints: list[str],
) -> AdmissionAxisResult:
    if score >= 80:
        band = "strong"
        severity: Literal["low", "medium", "high"] = "low"
    elif score >= 60:
        band = "watch"
        severity = "medium"
    else:
        band = "weak"
        severity = "high"
    return AdmissionAxisResult(
        key=key,
        label=_POSITIVE_AXIS_LABELS[key],
        score=score,
        band=band,
        severity=severity,
        rationale=rationale,
        evidence_hints=hints,
    )


def _authenticity_risk_axis(*, score: int, hints: list[str]) -> AdmissionAxisResult:
    if score <= 35:
        band = "stable"
        severity: Literal["low", "medium", "high"] = "low"
        rationale = "근거 대비 과장 위험이 낮고 기록 일관성이 유지됩니다."
    elif score <= 60:
        band = "watch"
        severity = "medium"
        rationale = "일부 구간에서 근거 밀도와 설명 일관성을 추가 확인해야 합니다."
    else:
        band = "high_risk"
        severity = "high"
        rationale = "근거 대비 주장 과장 가능성이 있어 보수적 서술과 증거 보강이 필요합니다."
    return AdmissionAxisResult(
        key="authenticity_risk",
        label="진정성·과장 위험",
        score=score,
        band=band,
        severity=severity,
        rationale=rationale,
        evidence_hints=hints,
    )


def _major_alignment_rationale(score: int) -> str:
    if score >= 80:
        return "전공 연계 키워드와 과목 분포가 비교적 안정적으로 연결됩니다."
    if score >= 60:
        return "전공 연계 단서는 있으나 기록 전반에서 반복 노출이 더 필요합니다."
    return "전공 연결 신호가 약해 핵심 과목/활동 근거를 명시적으로 보강해야 합니다."


def _inquiry_rationale(score: int) -> str:
    if score >= 80:
        return "탐구 흐름이 단발성이 아니라 후속 활동으로 이어지는 패턴이 확인됩니다."
    if score >= 60:
        return "탐구 연속성 단서가 일부 있으나 과목/주제 재등장 흐름을 더 명확히 해야 합니다."
    return "활동이 단편적으로 보일 수 있어 비교·후속·심화 흐름을 의도적으로 연결해야 합니다."


def _evidence_rationale(score: int) -> str:
    if score >= 80:
        return "수치/관찰/기록 근거가 충분해 주장을 방어하기 좋습니다."
    if score >= 60:
        return "핵심 근거는 있으나 주장 대비 증거 밀도를 한 단계 더 높일 필요가 있습니다."
    return "근거 밀도가 낮아 결과 주장보다 관찰 사실을 먼저 축적하는 것이 안전합니다."


def _process_rationale(score: int) -> str:
    if score >= 80:
        return "과정 설명과 반성 기록이 비교적 구체적으로 드러납니다."
    if score >= 60:
        return "과정 서술은 있으나 방법-한계-개선의 연결을 더 또렷하게 적어야 합니다."
    return "무엇을 했는지는 보이지만 왜 그렇게 했는지와 한계 설명이 부족합니다."


def _derive_risk_level(*, admission_axes: list[AdmissionAxisResult]) -> RiskLevel:
    positive_axes = [axis for axis in admission_axes if axis.key != "authenticity_risk"]
    weak_count = sum(1 for axis in positive_axes if axis.band == "weak")
    watch_count = sum(1 for axis in positive_axes if axis.band == "watch")
    authenticity = next((axis for axis in admission_axes if axis.key == "authenticity_risk"), None)
    authenticity_score = authenticity.score if authenticity else 50

    if authenticity_score >= 70 or weak_count >= 2:
        return "danger"
    if authenticity_score >= 50 or weak_count >= 1 or watch_count >= 2:
        return "warning"
    return "safe"


def _build_strengths(
    *,
    features: StudentRecordFeatures,
    admission_axes: list[AdmissionAxisResult],
) -> list[str]:
    strengths: list[str] = []
    for axis in admission_axes:
        if axis.key == "authenticity_risk":
            continue
        if axis.band == "strong":
            strengths.append(f"{axis.label}: {axis.rationale}")
    if features.section_presence.get("교과학습발달상황") and features.section_record_counts.get("교과학습발달상황", 0) >= 3:
        strengths.append("교과학습발달상황 기록량이 충분해 학업 근거 제시에 유리합니다.")
    if not strengths:
        strengths.append("핵심 섹션을 기반으로 확장 가능한 최소 근거는 확보되어 있습니다.")
    return _dedupe_keep_order(strengths)[:6]


def _build_gaps(
    *,
    features: StudentRecordFeatures,
    admission_axes: list[AdmissionAxisResult],
) -> list[str]:
    gaps: list[str] = []
    for axis in admission_axes:
        if axis.key == "authenticity_risk":
            continue
        if axis.band in {"weak", "watch"}:
            gaps.append(f"{axis.label}: {axis.rationale}")
    for section_key, present in features.section_presence.items():
        if not present and section_key in _SECTION_LABELS:
            gaps.append(f"{section_key} 섹션 근거가 부족합니다.")
    if not gaps:
        gaps.append("현재 구조를 유지하면서 세부 증거(수치, 비교, 반성)를 추가하면 완성도가 높아집니다.")
    return _dedupe_keep_order(gaps)[:8]


def _build_risk_flags(
    *,
    features: StudentRecordFeatures,
    admission_axes: list[AdmissionAxisResult],
) -> list[str]:
    flags = list(features.risk_flags)
    authenticity = next((axis for axis in admission_axes if axis.key == "authenticity_risk"), None)
    if authenticity and authenticity.band == "high_risk":
        flags.append("진정성·과장 위험 축이 높아 표현 수위를 보수적으로 유지해야 합니다.")
    return _dedupe_keep_order(flags)[:8]


def _build_next_action_seeds(
    *,
    features: StudentRecordFeatures,
    admission_axes: list[AdmissionAxisResult],
    target_major: str | None,
) -> list[str]:
    actions: list[str] = []
    weakest_positive = sorted(
        (axis for axis in admission_axes if axis.key != "authenticity_risk"),
        key=lambda axis: axis.score,
    )[:2]
    for axis in weakest_positive:
        if axis.key == "major_alignment":
            actions.append("현재 기록 중 전공 관련 과목/활동 문장을 한 문단으로 재정렬해 연결성을 명시하세요.")
        elif axis.key == "inquiry_continuity":
            actions.append("같은 주제를 2회 이상 이어지는 흐름(문제-시도-개선)으로 정리하세요.")
        elif axis.key == "evidence_density":
            actions.append("주장마다 관찰 근거 1개 이상을 연결하고 수치/사실 표현을 우선 배치하세요.")
        elif axis.key == "process_explanation":
            actions.append("방법-한계-개선 순서로 과정 설명을 3문장 이상 고정 템플릿으로 작성하세요.")

    if features.needs_review:
        actions.append("needs_review 표시 문서는 원문 대조 후 핵심 문장을 보수적으로 재작성하세요.")
    if target_major:
        actions.append(f"{target_major} 지원 맥락에 맞는 활동 1개를 선정해 근거 중심으로 심화 기록을 추가하세요.")
    return _dedupe_keep_order(actions)[:8]


def _build_recommended_topics(
    *,
    features: StudentRecordFeatures,
    target_major: str | None,
) -> list[str]:
    topics = [subject for subject, _ in features.subject_distribution.items()][:5]
    if target_major:
        topics.insert(0, f"{target_major} 연계 심화탐구")
    if not topics:
        topics = ["교과 기반 심화탐구", "진로 연계 프로젝트", "비교·분석형 활동"]
    return _dedupe_keep_order(topics)[:6]


def _bounded_int(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
