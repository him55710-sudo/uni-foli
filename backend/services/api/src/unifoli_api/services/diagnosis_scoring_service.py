from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, Field

from unifoli_api.core.config import get_settings
from unifoli_api.services.admissions_criteria_service import (
    AdmissionsCriteriaProfile,
    confidence_note_for_axis,
    criteria_refs_for_axis,
    input_factors_for_axis,
    resolve_admissions_criteria_profile,
)
from unifoli_api.services.diagnosis_axis_schema import AdmissionAxisKey, POSITIVE_AXIS_LABELS, PositiveAxisKey
from unifoli_api.services.student_record_feature_service import StudentRecordFeatures

RiskLevel = Literal["safe", "warning", "danger"]

_LEGACY_MOJIBAKE_SECTION_CONSULTING_LABELS: dict[str, str] = {
    "援먭낵?숈뒿諛쒕떖?곹솴": "교과 성취·세부능력",
    "李쎌쓽??泥댄뿕?쒕룞": "창의적 체험활동",
    "?됰룞?뱀꽦 諛?醫낇빀?섍껄": "행동특성·종합의견",
    "?낆꽌?쒕룞": "독서/지식 확장",
    "?섏긽寃쎈젰": "수상·성과 기록",
}

_SECTION_CONSULTING_LABELS: dict[str, str] = {
    **_LEGACY_MOJIBAKE_SECTION_CONSULTING_LABELS,
    "교과학습발달상황": "교과 성취·세부능력",
    "창의적 체험활동": "창의적 체험활동",
    "행동특성 및 종합의견": "행동특성·종합의견",
    "독서활동": "독서/지식 확장",
}


class AxisSemanticGrade(BaseModel):
    score: int = Field(ge=0, le=100, description="0~100 사이의 정성 점수")
    rationale: str = Field(description="점수 부여 근거")
    evidence_hints: list[str] = Field(default_factory=list, description="점수 근거가 되는 학생부 문구나 단서")


class ContinuityLink(BaseModel):
    title: str = Field(description="탐구 연속성 라인")
    description: str = Field(description="학년별·과목별 기록이 어떻게 이어지는지 설명")
    evidence_hooks: list[str] = Field(default_factory=list, description="연속성을 보여주는 학생부 단서")


class ThemeCluster(BaseModel):
    theme_name: str = Field(description="통합 탐구 테마명")
    description: str = Field(description="서로 다른 과목이나 활동이 하나의 테마로 연결되는 방식")
    subjects_involved: list[str] = Field(default_factory=list, description="관련 교과목")
    evidence_hooks: list[str] = Field(default_factory=list, description="통합성을 보여주는 학생부 단서")


class OutlierActivity(BaseModel):
    activity_name: str
    description: str = Field(description="주요 학업·진로 흐름과 분리되어 보이는 이유")


class RelationalGraph(BaseModel):
    continuity_links: list[ContinuityLink] = Field(default_factory=list)
    theme_clusters: list[ThemeCluster] = Field(default_factory=list)
    unlinked_outliers: list[OutlierActivity] = Field(default_factory=list)


class SemanticDiagnosisExtraction(BaseModel):
    universal_rigor: AxisSemanticGrade = Field(description="학업 엄밀성")
    universal_specificity: AxisSemanticGrade = Field(description="근거 구체성")
    relational_narrative: AxisSemanticGrade = Field(description="성장/탐구 과정")
    relational_continuity: AxisSemanticGrade = Field(description="진로 탐색 연속성")
    cluster_depth: AxisSemanticGrade = Field(description="전공 탐구 깊이")
    cluster_suitability: AxisSemanticGrade = Field(description="전공/계열 적합성")
    community_contribution: AxisSemanticGrade | None = Field(default=None, description="공동체 기여")
    relational_graph: RelationalGraph | None = Field(None, description="기록 간 관계망")
    summary_insight: str = Field(description="전체 진단 요약")
    strengths: list[str] = Field(default_factory=list, description="강점 후보")
    gaps: list[str] = Field(default_factory=list, description="보완이 필요한 약점/공백 후보")


class AdmissionAxisResult(BaseModel):
    key: AdmissionAxisKey
    label: str
    score: int = Field(ge=0, le=100)
    band: str
    severity: Literal["low", "medium", "high"]
    rationale: str
    evidence_hints: list[str] = Field(default_factory=list)
    criteria_refs: list[str] = Field(default_factory=list)
    input_factors: list[str] = Field(default_factory=list)
    confidence_note: str | None = None


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
    relational_graph: RelationalGraph | None = None


async def normalize_major_name(major_name: str | None) -> str | None:
    """Normalize a free-form major name with an LLM when available."""
    if not major_name or len(major_name.strip()) < 2:
        return major_name

    from unifoli_api.core.llm import get_llm_client

    try:
        llm = get_llm_client(profile="fast", concern="diagnosis")
    except Exception:
        return major_name

    class NormalizationResult(BaseModel):
        corrected_name: str

    prompt = (
        f"사용자가 입력한 전공명은 '{major_name}'입니다.\n"
        "한국 대학 입시 맥락에서 쓰는 표준 학과/전공명으로만 정리하세요. "
        "확신할 수 없으면 원문을 그대로 반환하세요."
    )

    try:
        res = await llm.generate_json(prompt=prompt, response_model=NormalizationResult, temperature=0.0)
        return res.corrected_name.strip()
    except Exception:
        return major_name


async def extract_semantic_diagnosis(
    *,
    masked_text: str,
    target_major: str | None,
    target_university: str | None,
    interest_universities: list[str] | None = None,
) -> SemanticDiagnosisExtraction:
    from unifoli_api.core.llm import get_llm_client
    from unifoli_api.services.prompt_registry import get_prompt_registry

    try:
        llm = get_llm_client(profile="standard", concern="diagnosis")
    except TypeError:
        llm = get_llm_client()  # type: ignore[call-arg]

    criteria_profile = resolve_admissions_criteria_profile(
        target_university=target_university,
        interest_universities=interest_universities,
    )
    base_instruction = get_prompt_registry().compose_prompt("diagnosis.semantic-scoring")
    interest_context = f" / 추가 목표 대학: {', '.join(interest_universities)}" if interest_universities else ""
    system_instruction = (
        base_instruction.replace("{{target_major}}", target_major or "미정")
        .replace("{{target_university}}", target_university or "미정")
        .replace("{{interest_context}}", interest_context)
        .replace("{{criteria_context}}", _criteria_context_block(criteria_profile))
    )

    prompt = (
        "다음 학생부 텍스트를 바탕으로 보수적인 의미 기반 진단을 수행하세요. "
        "공식 기준은 평가 맥락으로만 사용하고, 학생 행동 주장은 반드시 학생부 텍스트에 근거해야 합니다. "
        "반드시 SemanticDiagnosisExtraction JSON 스키마를 따르세요.\n\n"
        f"[학생부 텍스트]\n{masked_text[:get_settings().semantic_extraction_max_input_chars]}"
    )
    return await llm.generate_json(
        prompt=prompt,
        response_model=SemanticDiagnosisExtraction,
        system_instruction=system_instruction,
        temperature=0.1,
    )


def build_diagnosis_scoring_sheet(
    *,
    features: StudentRecordFeatures,
    project_title: str,
    target_major: str | None,
    target_university: str | None,
    interest_universities: list[str] | None = None,
    semantic: SemanticDiagnosisExtraction | None = None,
) -> DiagnosisScoringSheet:
    criteria_profile = resolve_admissions_criteria_profile(
        target_university=target_university,
        interest_universities=interest_universities,
    )
    section_analysis = _build_section_analysis(features)
    document_quality = _build_document_quality(features)
    admission_axes = _build_admission_axes(
        features,
        criteria_profile=criteria_profile,
        semantic=semantic,
    )
    risk_level = _derive_risk_level(admission_axes=admission_axes)

    strengths = _build_strengths(features=features, admission_axes=admission_axes, semantic=semantic)
    gaps = _build_gaps(features=features, admission_axes=admission_axes, semantic=semantic)
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
    weakest_label = weakest_axis.label if weakest_axis else "학생부 근거"

    targets: list[str] = []
    if target_university:
        targets.append(f"{target_university} {target_major or ''}".strip())
    if interest_universities:
        targets.extend(interest_universities)
    target_context = " · ".join(targets[:2])
    if len(targets) > 2:
        target_context = f"{target_context} 외 {len(targets) - 2}개"
    if not target_context:
        target_context = target_major or "목표 전공"

    overview = (
        f"{project_title} 기준 학생부 해석 신뢰도는 {document_quality.parse_reliability_band}이며, "
        f"2026 학종 기준상 현재는 {weakest_label} 보완이 우선입니다."
    )
    recommended_focus = (
        f"{target_context} 맥락에서 {weakest_label}을 먼저 보완하세요. "
        "점수는 공식 기준과 학생부 기록 근거를 분리해 보수적으로 산출했습니다."
    )
    if features.target_major_alignment_note and features.target_major_alignment_level in {"mismatch", "weak"}:
        overview = f"{overview} {features.target_major_alignment_note}"
        recommended_focus = (
            f"{features.target_major_alignment_note} "
            "기존 관심을 목표 전공 문제로 전환하는 탐구 설계가 우선입니다."
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
        relational_graph=semantic.relational_graph if semantic else None,
    )


def _build_section_analysis(features: StudentRecordFeatures) -> list[SectionAnalysisItem]:
    rows: list[SectionAnalysisItem] = []
    keys = list(features.section_record_counts.keys()) or list(features.section_presence.keys())
    for key in keys[:6]:
        present = bool(features.section_presence.get(key))
        count = int(features.section_record_counts.get(key) or 0)
        label = _SECTION_CONSULTING_LABELS.get(str(key), str(key))
        if present and count >= 5:
            note = "근거량이 충분해 강점 후보로 전환할 수 있습니다."
        elif present and count >= 3:
            note = "활용 가능한 기록이 있으므로 전공 연결 문장과 과정 설명을 붙이면 밀도가 올라갑니다."
        elif present:
            note = "기록은 확인되지만 단독 근거로는 약합니다. 페이지 단서와 보완 활동을 함께 묶어야 합니다."
        else:
            note = "해당 섹션 근거가 부족합니다. 원문 누락 여부를 확인하고 방어 가능한 문장을 확보하세요."
        rows.append(
            SectionAnalysisItem(
                key=str(key),
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
        f"{features.document_count}개 문서, 총 {features.total_records}개 기록 기준 원문 인식 정확도는 {reliability_score}점입니다. "
        f"근거 구체성 {round(features.evidence_density, 2)}, 활동 연결성 {round(features.narrative_density, 2)}로 "
        "확인 가능한 학생부 근거와 보완 필요 기록을 분리해 해석합니다."
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


def _build_admission_axes(
    features: StudentRecordFeatures,
    *,
    criteria_profile: AdmissionsCriteriaProfile,
    semantic: SemanticDiagnosisExtraction | None = None,
) -> list[AdmissionAxisResult]:
    active_sections = sum(1 for present in features.section_presence.values() if present)

    rigor_base = _bounded_int(18 + features.reliability_score * 47 + min(features.total_records, 30) * 1.35)
    spec_base = _bounded_int(13 + features.evidence_density * 60 + min(features.evidence_reference_count, 20) * 1.6)
    narrative_base = _bounded_int(23 + features.narrative_density * 52 + active_sections * 4.2)
    continuity_base = _bounded_int(18 + features.repeated_subject_ratio * 65 + min(features.unique_subject_count, 12) * 1.6)
    depth_base = _bounded_int(13 + features.major_term_overlap_ratio * 80 + min(features.unique_subject_count, 8) * 2.1)
    suitability_base = depth_base
    community_base = _community_base_score(features=features, active_sections=active_sections)
    alignment_penalty = _major_alignment_score_penalty(features)
    if alignment_penalty:
        depth_base = _bounded_int(depth_base - alignment_penalty)
        suitability_base = _bounded_int(suitability_base - alignment_penalty - 4)

    def _merge(
        key: PositiveAxisKey,
        base: int,
        semantic_grade: AxisSemanticGrade | None,
    ) -> tuple[int, str, list[str]]:
        if semantic_grade is None:
            return _calibrate_positive_axis_score(key=key, score=base, features=features), "", []
        score = _bounded_int(base * 0.3 + semantic_grade.score * 0.7)
        score = _calibrate_positive_axis_score(key=key, score=score, features=features)
        return score, semantic_grade.rationale, semantic_grade.evidence_hints

    u_rigor_score, u_rigor_rat, u_rigor_hints = _merge(
        "universal_rigor",
        rigor_base,
        semantic.universal_rigor if semantic else None,
    )
    u_spec_score, u_spec_rat, u_spec_hints = _merge(
        "universal_specificity",
        spec_base,
        semantic.universal_specificity if semantic else None,
    )
    r_narr_score, r_narr_rat, r_narr_hints = _merge(
        "relational_narrative",
        narrative_base,
        semantic.relational_narrative if semantic else None,
    )
    r_cont_score, r_cont_rat, r_cont_hints = _merge(
        "relational_continuity",
        continuity_base,
        semantic.relational_continuity if semantic else None,
    )
    c_depth_score, c_depth_rat, c_depth_hints = _merge(
        "cluster_depth",
        depth_base,
        semantic.cluster_depth if semantic else None,
    )
    c_suit_score, c_suit_rat, c_suit_hints = _merge(
        "cluster_suitability",
        suitability_base,
        semantic.cluster_suitability if semantic else None,
    )
    community_score, community_rat, community_hints = _merge(
        "community_contribution",
        community_base,
        semantic.community_contribution if semantic else None,
    )

    authenticity_risk = _bounded_int(
        78
        - features.reliability_score * 40
        - features.evidence_density * 26
        - features.repeated_subject_ratio * 16
        + (20 if features.needs_review else 0)
        + _policy_risk_penalty(features.risk_flags)
    )

    return [
        _positive_axis(
            key="universal_rigor",
            score=u_rigor_score,
            rationale=u_rigor_rat or "교과 성취와 세부능력 기록의 신뢰도, 기록량, 학업 맥락을 바탕으로 산출한 학업 엄밀성입니다.",
            hints=u_rigor_hints or [f"원문 인식 정확도: {round(features.reliability_score, 2)}", f"전체 기록 수: {features.total_records}"],
            criteria_profile=criteria_profile,
        ),
        _positive_axis(
            key="universal_specificity",
            score=u_spec_score,
            rationale=u_spec_rat or "구체적인 관찰·수치·결과·근거 참조 빈도를 바탕으로 학생부 주장의 방어 가능성을 평가했습니다.",
            hints=u_spec_hints or [f"근거 구체성: {round(features.evidence_density, 2)}", f"근거 참조 수: {features.evidence_reference_count}"],
            criteria_profile=criteria_profile,
        ),
        _positive_axis(
            key="relational_narrative",
            score=r_narr_score,
            rationale=r_narr_rat or "활동을 나열하는 수준을 넘어 과정, 시행착오, 배운 점이 연결되는지 평가했습니다.",
            hints=r_narr_hints or [f"서사 밀도: {round(features.narrative_density, 2)}", f"활성 섹션 수: {active_sections}"],
            criteria_profile=criteria_profile,
        ),
        _positive_axis(
            key="relational_continuity",
            score=r_cont_score,
            rationale=r_cont_rat or "학년별·과목별 탐구 주제가 반복되고 확장되는 흐름을 평가했습니다.",
            hints=r_cont_hints or [f"반복 과목 비율: {round(features.repeated_subject_ratio, 2)}", f"고유 과목 수: {features.unique_subject_count}"],
            criteria_profile=criteria_profile,
        ),
        _positive_axis(
            key="cluster_depth",
            score=c_depth_score,
            rationale=c_depth_rat
            or features.target_major_alignment_note
            or "목표 전공·계열과 관련된 개념, 방법, 산출물의 깊이를 평가했습니다.",
            hints=c_depth_hints or _major_alignment_hints(features),
            criteria_profile=criteria_profile,
        ),
        _positive_axis(
            key="cluster_suitability",
            score=c_suit_score,
            rationale=c_suit_rat
            or features.target_major_alignment_note
            or "기록 전반이 목표 진로와 계열에 자연스럽게 이어지는지 종합적으로 평가했습니다.",
            hints=c_suit_hints or _major_alignment_hints(features),
            criteria_profile=criteria_profile,
        ),
        _positive_axis(
            key="community_contribution",
            score=community_score,
            rationale=community_rat or "행동특성, 창체, 출결·역할 수행 단서에서 협업·책임감·소통과 공동체 기여가 드러나는지 평가했습니다.",
            hints=community_hints or _community_hints(features=features, active_sections=active_sections),
            criteria_profile=criteria_profile,
        ),
        _authenticity_risk_axis(
            score=authenticity_risk,
            hints=[f"원문 인식 정확도: {round(features.reliability_score, 2)}", f"검토 필요 문서: {features.needs_review_documents}"],
            criteria_profile=criteria_profile,
        ),
    ]


def _calibrate_positive_axis_score(
    *,
    key: PositiveAxisKey,
    score: int,
    features: StudentRecordFeatures,
) -> int:
    """Apply evidence-gated calibration based on 2026 admissions criteria."""

    bonus = 0
    if features.reliability_score >= 0.65:
        bonus += 2
    if features.evidence_density >= 0.45:
        bonus += 2
    if features.total_records >= 12:
        bonus += 1
    if not features.needs_review:
        bonus += 1

    active_sections = sum(1 for present in features.section_presence.values() if present)
    if key == "universal_rigor" and features.reliability_score >= 0.72 and features.total_records >= 10:
        bonus += 2
    elif key == "universal_specificity" and features.evidence_reference_count >= 8:
        bonus += 2
    elif key == "relational_narrative" and features.narrative_density >= 0.45 and active_sections >= 3:
        bonus += 2
    elif key == "relational_continuity" and features.repeated_subject_ratio >= 0.4:
        bonus += 3
    elif key in {"cluster_depth", "cluster_suitability"} and features.major_term_overlap_ratio >= 0.32:
        bonus += 3
    elif key == "community_contribution" and _community_base_signal(features):
        bonus += 2

    if score < 45:
        bonus = min(bonus, 2)
    elif score < 60:
        bonus = min(bonus, 4)

    calibrated = _bounded_int(score + bonus)
    cap = _positive_axis_score_cap(key=key, features=features, active_sections=active_sections)
    calibrated = min(calibrated, cap)

    if calibrated >= 90 and not _positive_axis_allows_90(key=key, features=features, active_sections=active_sections):
        calibrated = 89
    if calibrated >= 80 and not _positive_axis_allows_80(key=key, features=features, active_sections=active_sections):
        calibrated = 79
    return calibrated


def _major_alignment_score_penalty(features: StudentRecordFeatures) -> int:
    if features.target_major_alignment_level == "mismatch":
        return 18
    if features.target_major_alignment_level == "weak":
        return 12
    if features.target_major_alignment_level == "partial":
        return 5
    return 0


def _major_alignment_hints(features: StudentRecordFeatures) -> list[str]:
    hints: list[str] = []
    if features.target_major_track_label:
        hints.append(
            f"목표 전공 단서: {features.target_major_track_label} "
            f"{features.target_major_evidence_count}회 확인"
        )
    if features.dominant_major_track_label:
        dominant_count = features.major_signal_counts.get(features.dominant_major_track or "", 0)
        hints.append(f"학생부 우세 계열: {features.dominant_major_track_label} {dominant_count}회 확인")
    if features.target_major_alignment_note:
        hints.append(features.target_major_alignment_note)
    if not hints:
        hints.append(f"목표 전공 키워드 중첩도: {round(features.major_term_overlap_ratio, 2)}")
    return hints[:4]


def _positive_axis_score_cap(
    *,
    key: PositiveAxisKey,
    features: StudentRecordFeatures,
    active_sections: int,
) -> int:
    cap = 100
    if features.needs_review:
        cap = min(cap, 76)
    if features.reliability_score < 0.55 or features.total_records < 5:
        cap = min(cap, 64)
    elif features.reliability_score < 0.65 or features.evidence_density < 0.2:
        cap = min(cap, 72)
    if key == "universal_specificity" and features.evidence_reference_count < 6:
        cap = min(cap, 74)
    if key == "relational_narrative" and active_sections < 3:
        cap = min(cap, 74)
    if key == "relational_continuity" and features.repeated_subject_ratio < 0.22 and features.unique_subject_count < 4:
        cap = min(cap, 74)
    if key in {"cluster_depth", "cluster_suitability"} and features.major_term_overlap_ratio < 0.18:
        cap = min(cap, 74)
    if key in {"cluster_depth", "cluster_suitability"}:
        if features.target_major_alignment_level == "mismatch":
            cap = min(cap, 58)
        elif features.target_major_alignment_level == "weak":
            cap = min(cap, 64)
    if key == "community_contribution" and not _community_base_signal(features):
        cap = min(cap, 74)
    return cap


def _positive_axis_allows_80(
    *,
    key: PositiveAxisKey,
    features: StudentRecordFeatures,
    active_sections: int,
) -> bool:
    if features.needs_review:
        return False
    if features.reliability_score < 0.68 or features.evidence_density < 0.3 or features.total_records < 10:
        return False
    if key == "universal_rigor":
        return features.reliability_score >= 0.72
    if key == "universal_specificity":
        return features.evidence_reference_count >= 8 and features.evidence_density >= 0.38
    if key == "relational_narrative":
        return features.narrative_density >= 0.45 and active_sections >= 3
    if key == "relational_continuity":
        return features.repeated_subject_ratio >= 0.35
    if key in {"cluster_depth", "cluster_suitability"}:
        if features.target_major_alignment_level in {"mismatch", "weak"}:
            return False
        return features.major_term_overlap_ratio >= 0.32 and features.evidence_reference_count >= 6
    if key == "community_contribution":
        return _community_base_signal(features) and active_sections >= 3
    return True


def _positive_axis_allows_90(
    *,
    key: PositiveAxisKey,
    features: StudentRecordFeatures,
    active_sections: int,
) -> bool:
    if (
        features.needs_review
        or features.reliability_score < 0.85
        or features.evidence_density < 0.55
        or features.total_records < 18
        or active_sections < 4
    ):
        return False
    if key == "universal_specificity":
        return features.evidence_reference_count >= 12
    if key == "relational_continuity":
        return features.repeated_subject_ratio >= 0.5
    if key in {"cluster_depth", "cluster_suitability"}:
        if features.target_major_alignment_level in {"mismatch", "weak", "partial"}:
            return False
        return features.major_term_overlap_ratio >= 0.55
    if key == "community_contribution":
        return _section_count_matching(features, "행동", "종합", "?됰룞", "醫낇빀") >= 2
    return True


def _positive_axis(
    *,
    key: PositiveAxisKey,
    score: int,
    rationale: str,
    hints: list[str],
    criteria_profile: AdmissionsCriteriaProfile,
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
    axis_key = cast(AdmissionAxisKey, key)
    return AdmissionAxisResult(
        key=axis_key,
        label=POSITIVE_AXIS_LABELS[key],
        score=score,
        band=band,
        severity=severity,
        rationale=rationale,
        evidence_hints=hints,
        criteria_refs=criteria_refs_for_axis(criteria_profile, axis_key),
        input_factors=input_factors_for_axis(criteria_profile, axis_key),
        confidence_note=confidence_note_for_axis(criteria_profile, axis_key),
    )


def _authenticity_risk_axis(
    *,
    score: int,
    hints: list[str],
    criteria_profile: AdmissionsCriteriaProfile,
) -> AdmissionAxisResult:
    if score <= 35:
        band = "stable"
        severity: Literal["low", "medium", "high"] = "low"
        rationale = "근거 대비 과장 위험이 낮고 기록 일관성이 비교적 안정적입니다."
    elif score <= 60:
        band = "watch"
        severity = "medium"
        rationale = "일부 구간에서 근거의 충분성이나 해석 일관성을 추가 확인해야 합니다."
    else:
        band = "high_risk"
        severity = "high"
        rationale = "근거 대비 주장 과장 가능성이 높아 보수적 서술과 근거 보강이 필요합니다."
    return AdmissionAxisResult(
        key="authenticity_risk",
        label="진정성 위험",
        score=score,
        band=band,
        severity=severity,
        rationale=rationale,
        evidence_hints=hints,
        criteria_refs=criteria_refs_for_axis(criteria_profile, "authenticity_risk"),
        input_factors=input_factors_for_axis(criteria_profile, "authenticity_risk"),
        confidence_note=confidence_note_for_axis(criteria_profile, "authenticity_risk"),
    )


def _derive_risk_level(*, admission_axes: list[AdmissionAxisResult]) -> RiskLevel:
    positive_axes = [axis for axis in admission_axes if axis.key != "authenticity_risk"]
    weak_count = sum(1 for axis in positive_axes if axis.band == "weak")
    watch_count = sum(1 for axis in positive_axes if axis.band == "watch")
    authenticity = next((axis for axis in admission_axes if axis.key == "authenticity_risk"), None)
    authenticity_score = authenticity.score if authenticity else 50

    if authenticity_score >= 70 or weak_count >= 2:
        return "danger"
    if authenticity_score >= 50 or weak_count >= 1 or watch_count >= 3:
        return "warning"
    return "safe"


def _build_strengths(
    *,
    features: StudentRecordFeatures,
    admission_axes: list[AdmissionAxisResult],
    semantic: SemanticDiagnosisExtraction | None = None,
) -> list[str]:
    strengths: list[str] = []
    if semantic and semantic.strengths:
        strengths.extend(semantic.strengths)
    if features.dominant_major_track_label and features.dominant_major_track != features.target_major_track:
        strengths.append(f"학생부 원문에서는 {features.dominant_major_track_label} 계열 관심이 반복적으로 확인됩니다.")
    for axis in admission_axes:
        if axis.key != "authenticity_risk" and axis.band == "strong":
            strengths.append(f"{axis.label}: {axis.rationale}")
    if not strengths:
        strengths.append("학생부 섹션 기반의 기본 근거는 확보되어 있습니다.")
    return _dedupe_keep_order(strengths)[:8]


def _build_gaps(
    *,
    features: StudentRecordFeatures,
    admission_axes: list[AdmissionAxisResult],
    semantic: SemanticDiagnosisExtraction | None = None,
) -> list[str]:
    gaps: list[str] = []
    if semantic and semantic.gaps:
        gaps.extend(semantic.gaps)
    if features.target_major_alignment_note and features.target_major_alignment_level in {"mismatch", "weak", "partial"}:
        gaps.append(features.target_major_alignment_note)
    for axis in admission_axes:
        if axis.key != "authenticity_risk" and axis.band in {"weak", "watch"}:
            gaps.append(f"{axis.label}: {axis.rationale}")
    if features.total_records < 5:
        gaps.append("기록 총량이 적어 근거 확보가 필요합니다.")
    if not gaps:
        gaps.append("현재 구조를 유지하되 수치·비교·반성 근거를 더하면 완성도가 올라갑니다.")
    return _dedupe_keep_order(gaps)[:10]


def _build_risk_flags(
    *,
    features: StudentRecordFeatures,
    admission_axes: list[AdmissionAxisResult],
) -> list[str]:
    flags = list(features.risk_flags)
    authenticity = next((axis for axis in admission_axes if axis.key == "authenticity_risk"), None)
    if authenticity and authenticity.band == "high_risk":
        flags.append("진정성 위험 축이 높아 보수적 문장 운영이 필요합니다.")
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
        if axis.key == "cluster_suitability":
            actions.append("전공 관련 과목/활동 3개를 골라 '근거 문장-증명 역량-전공 연결' 표로 재정리하세요.")
        elif axis.key == "relational_continuity":
            actions.append("학년별 활동을 같은 주제 1개로 묶고 '문제-시도-개선-다음 질문' 흐름을 작성하세요.")
        elif axis.key == "universal_specificity":
            actions.append("핵심 주장 3개마다 페이지 단서, 관찰값, 비교 기준을 1개씩 붙여 추상 표현을 줄이세요.")
        elif axis.key == "cluster_depth":
            actions.append("가장 강한 탐구 1개를 선택해 방법-한계-개선-후속 질문 순서로 4문장 보강안을 만드세요.")
        elif axis.key == "universal_rigor":
            actions.append("교과 개념이나 이론 2개를 실제 활동 결과와 연결해 학업 엄밀성 문장을 보강하세요.")
        elif axis.key == "relational_narrative":
            actions.append("활동 간 전환 이유를 한 문장씩 추가해 단순 나열이 아닌 성장 서사로 배열하세요.")
        elif axis.key == "community_contribution":
            actions.append("협업·책임·소통이 드러나는 창체/행특 근거를 골라 공동체 기여 문장으로 정리하세요.")
    if features.needs_review:
        actions.append("검토 필요 문서가 있으므로 원문 대조 후 핵심 문장을 보수적으로 시작하세요.")
    if features.target_major_alignment_note and features.target_major_alignment_level in {"mismatch", "weak"}:
        source_label = features.dominant_major_track_label or "현재 강한 관심"
        target_label = target_major or features.target_major_track_label or "목표 전공"
        actions.append(
            f"{source_label} 관심을 {target_label} 문제로 전환하는 탐구 주제 3개를 먼저 설계하세요."
        )
    if target_major:
        actions.append(f"{target_major} 맥락에 맞는 활동 1개를 선정해 기존 근거로 방어 가능한 심화 보고서 주제를 만드세요.")
    return _dedupe_keep_order(actions)[:8]


def _build_recommended_topics(
    *,
    features: StudentRecordFeatures,
    target_major: str | None,
) -> list[str]:
    topics: list[str] = []
    if (
        features.target_major_track == "architecture"
        and features.dominant_major_track == "mechanical_computer"
    ):
        topics.extend(
            [
                "스마트빌딩 센서 데이터 기반 실내 환경 제어 탐구",
                "건물 에너지 저장 시스템의 열관리 방식 비교",
                "건축물 안전 모니터링용 MEMS 센서 활용 가능성 탐구",
                "전동화 기술 관심을 건축 설비 에너지 제어로 전환하는 보고서",
            ]
        )
    elif features.target_major_alignment_level in {"mismatch", "weak"}:
        source_label = features.dominant_major_track_label or "기존 관심"
        target_label = target_major or features.target_major_track_label or "목표 전공"
        topics.extend(
            [
                f"{source_label} 관심을 {target_label} 문제로 전환하는 탐구 설계",
                f"{target_label} 지원 서사를 보완하는 원문 근거 재해석 보고서",
            ]
        )
    elif target_major:
        topics.append(f"{target_major} 지원 근거를 새 질문으로 확장한 심화탐구")
    topics.extend([subject for subject, _ in features.subject_distribution.items()][:5])
    if not topics:
        topics = ["교과 기반 심화탐구", "진로 연계 프로젝트", "비교·분석형 활동"]
    return _dedupe_keep_order(topics)[:6]


def _community_base_score(*, features: StudentRecordFeatures, active_sections: int) -> int:
    community_records = _section_count_matching(features, "행동", "종합", "?됰룞", "醫낇빀", "behavior", "opinion")
    creative_records = _section_count_matching(features, "창", "체험", "李", "creative", "activity")
    risk_penalty = _policy_risk_penalty(features.risk_flags)
    return _bounded_int(
        18
        + min(community_records, 6) * 6
        + min(creative_records, 6) * 4
        + active_sections * 3.5
        + features.narrative_density * 24
        + features.reliability_score * 14
        - risk_penalty
    )


def _community_base_signal(features: StudentRecordFeatures) -> bool:
    return (
        _section_count_matching(features, "행동", "종합", "?됰룞", "醫낇빀", "behavior", "opinion") > 0
        or _section_count_matching(features, "창", "체험", "李", "creative", "activity") >= 2
    )


def _community_hints(*, features: StudentRecordFeatures, active_sections: int) -> list[str]:
    return [
        f"행동/종합의견 단서 수: {_section_count_matching(features, '행동', '종합', '?됰룞', '醫낇빀', 'behavior', 'opinion')}",
        f"창체 단서 수: {_section_count_matching(features, '창', '체험', '李', 'creative', 'activity')}",
        f"활성 섹션 수: {active_sections}",
    ]


def _section_count_matching(features: StudentRecordFeatures, *hints: str) -> int:
    total = 0
    lowered_hints = [hint.lower() for hint in hints if hint]
    for key, count in features.section_record_counts.items():
        key_text = str(key).lower()
        if any(hint in key_text for hint in lowered_hints):
            total += max(0, int(count or 0))
    return total


def _policy_risk_penalty(flags: list[str]) -> int:
    text = " ".join(flags).lower()
    penalty = 0
    for marker in ("학교폭력", "폭력", "school violence", "fabrication", "허위", "과장"):
        if marker in text:
            penalty += 12
    return penalty


def _criteria_context_block(criteria_profile: AdmissionsCriteriaProfile) -> str:
    lines = ["[2026 학생부종합전형 평가 기준 요약]"]
    for criterion in criteria_profile.criteria:
        refs = ", ".join(source_id for source_id in criterion.source_ids if source_id in criteria_profile.source_ids)
        if not refs:
            continue
        lines.append(f"- {criterion.label}: {criterion.summary} (sources: {refs})")
    lines.append("공식 기준은 평가 맥락으로만 사용하고, 학생 행동의 증거는 업로드된 학생부에서만 인정한다.")
    return "\n".join(lines)


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
