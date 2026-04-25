from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from unifoli_api.services.diagnosis_axis_schema import AdmissionAxisKey, POSITIVE_AXIS_LABELS, PositiveAxisKey
from unifoli_api.services.student_record_feature_service import StudentRecordFeatures

RiskLevel = Literal["safe", "warning", "danger"]

_SECTION_CONSULTING_LABELS: dict[str, str] = {
    "교과학습발달상황": "교과 성취·세특 기반",
    "창의적 체험활동": "창체 활동 서사",
    "행동특성 및 종합의견": "행특·종합의견 신뢰도",
    "독서활동": "독서/지적 확장성",
    "수상경력": "수상·성과 근거",
}


class AxisSemanticGrade(BaseModel):
    score: int = Field(ge=0, le=100, description="0~100점 사이의 정량 점수")
    rationale: str = Field(description="점수 부여 근거 (전문적인 입학사정관 톤의 한국어)")
    evidence_hints: list[str] = Field(default_factory=list, description="점수의 근거가 된 학생부 내 핵심 문구 및 단서")


class ContinuityLink(BaseModel):
    title: str = Field(description="탐구 연속성 헤드라인 (예: 1학년 수학에서 2학년 심화수학으로의 연계)")
    description: str = Field(description="학년별/기록별로 탐구가 어떻게 심화되거나 연결되었는지에 대한 상세 설명")
    evidence_hooks: list[str] = Field(default_factory=list, description="연속성을 증명하는 학생부 내 핵심 추출 문구")


class ThemeCluster(BaseModel):
    theme_name: str = Field(description="융합 탐구 테마 명칭 (예: '신재생 에너지의 경제적 타당성')")
    description: str = Field(description="서로 다른 과목이나 활동이 이 테마를 중심으로 어떻게 융합되었는지에 대한 설명")
    subjects_involved: list[str] = Field(default_factory=list, description="관여된 교과목 목록")
    evidence_hooks: list[str] = Field(default_factory=list, description="융합을 증명하는 학생부 내 핵심 추출 문구")


class OutlierActivity(BaseModel):
    activity_name: str
    description: str = Field(description="이 활동이 왜 핵심 학업 역량과 단절되어 보이거나 표면적으로 느껴지는지에 대한 사유")


class RelationalGraph(BaseModel):
    continuity_links: list[ContinuityLink] = Field(default_factory=list)
    theme_clusters: list[ThemeCluster] = Field(default_factory=list)
    unlinked_outliers: list[OutlierActivity] = Field(default_factory=list)


class SemanticDiagnosisExtraction(BaseModel):
    universal_rigor: AxisSemanticGrade = Field(description="학업 및 근거 엄밀성: 기록의 신뢰도와 학업 성취 수준")
    universal_specificity: AxisSemanticGrade = Field(description="근거 구체성: 구체적 사실, 수치, 방법론의 기재 정도")
    relational_narrative: AxisSemanticGrade = Field(description="서사적 발전성: 섹션 간 조화와 성장 서사의 풍부함")
    relational_continuity: AxisSemanticGrade = Field(description="탐구의 연속성: 학년별/과목별 탐구 주제의 반복 및 심화 과정")
    cluster_depth: AxisSemanticGrade = Field(description="전공 심층성: 목표 전공 관련 심화 활동 및 지적 호기심의 깊이")
    cluster_suitability: AxisSemanticGrade = Field(description="전공 적합성: 기록 전반에 나타난 진로 지향성과 계열 적합 인성")
    relational_graph: RelationalGraph | None = Field(None, description="기록 간의 관계망 (연속성, 융합, 단절 활동)")
    summary_insight: str = Field(description="전체 진단 요약 및 총평 (입학사정관 스타일의 전문적 조언)")
    strengths: list[str] = Field(default_factory=list, description="발굴된 강점 후보군 리스트")
    gaps: list[str] = Field(default_factory=list, description="보강이 필요한 약점/공백 후보군 리스트")


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
    relational_graph: RelationalGraph | None = None


async def normalize_major_name(major_name: str | None) -> str | None:
    """사용자가 입력한 전공 명칭의 오타를 교정하거나 표준 명칭으로 변환합니다."""
    if not major_name or len(major_name.strip()) < 2:
        return major_name

    from unifoli_api.core.llm import get_llm_client
    try:
        llm = get_llm_client(profile="fast", concern="diagnosis") # 빠른 응답을 위해 fast 프로필 사용
    except Exception:
        return major_name

    prompt = (
        f"다음은 사용자가 입력한 대학교 희망 전공 명칭입니다: '{major_name}'\n"
        "만약 오타가 있다면 올바른 명칭으로 교정하고, 줄임말이나 비표준 명칭이라면 "
        "한국 대학교에서 사용하는 표준 학과 명칭으로 변환해 주세요.\n"
        "결과는 다른 부연 설명 없이 오직 교정된 전공 명칭만 출력하십시오.\n"
        "만약 이미 표준 명칭이거나 교정이 불필요하다면 원문 그대로 출력하십시오."
    )

    try:
        # stream_chat 대신 단순 생성을 위해 generate_json을 활용하거나 
        # 간단한 텍스트 반환을 위해 직접 호출 로직을 사용 (llm.py의 구조에 따라)
        # 여기서는 generate_json 스키마 대신 일반 텍스트가 필요할 수 있으나 
        # 현재 llm 클라이언트는 generate_json 위주이므로 스카마 정의
        class NormalizationResult(BaseModel):
            corrected_name: str

        res = await llm.generate_json(
            prompt=prompt,
            response_model=NormalizationResult,
            temperature=0.0
        )
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
    registry = get_prompt_registry()

    # Get base instruction from registry
    base_instruction = registry.compose_prompt("diagnosis.semantic-scoring")

    interest_context = ""
    if interest_universities:
        interest_context = f" / 추가 목표 대학: {', '.join(interest_universities)}"

    # Perform variable substitution
    system_instruction = (
        base_instruction.replace("{{target_major}}", target_major or "미정")
        .replace("{{target_university}}", target_university or "미정")
        .replace("{{interest_context}}", interest_context)
    )

    prompt = (
        "다음 학생부 텍스트를 바탕으로 심층적인 의미론적 진단을 수행하십시오. "
        "반드시 부여된 SemanticDiagnosisExtraction 스키마를 엄격히 준수하여 JSON 형태로 출력하십시오.\n\n"
        f"분석 대상 텍스트:\n{masked_text[:15000]}"
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
    section_analysis = _build_section_analysis(features)
    document_quality = _build_document_quality(features)
    admission_axes = _build_admission_axes(features, semantic=semantic)
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
    weakest_label = weakest_axis.label if weakest_axis else "핵심 축"

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
        f"{project_title} 기준 문서 신뢰도는 {document_quality.parse_reliability_band} 수준이며, "
        f"현재는 {weakest_label} 보강이 우선입니다."
    )
    recommended_focus = (
        f"{target_context} 맥락에서 {weakest_label}을 먼저 보강하세요. "
        "점수는 현재 기록 근거를 기준으로 보수적으로 계산했습니다."
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
            note = "근거 총량이 좋아 대표 사례 2개를 선별해 강점 축으로 전환할 수 있습니다."
        elif present and count >= 3:
            note = "활용 가능한 기록은 있으나 전공 연결 문장과 과정 설명을 붙이면 설득력이 올라갑니다."
        elif present:
            note = "기록은 확인되지만 단독 근거로는 약합니다. 페이지 앵커와 보완 활동을 함께 묶어야 합니다."
        else:
            note = "해당 섹션 근거가 부족합니다. 원문 누락 여부를 확인하고 최소 1개 방어 가능한 문장을 확보하세요."
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
        f"{features.document_count}개 문서, 총 {features.total_records}개 기록 기준 파싱 신뢰도 {reliability_score}점입니다. "
        f"근거 밀도 {round(features.evidence_density, 2)}, 서사 밀도 {round(features.narrative_density, 2)}로 "
        "진단서는 확인 가능한 기록과 보완 필요 기록을 분리해 해석합니다."
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
    semantic: SemanticDiagnosisExtraction | None = None,
) -> list[AdmissionAxisResult]:
    # Layer 1: Universal
    rigor_base = _bounded_int(15 + features.reliability_score * 45 + min(features.total_records, 30) * 1.3)
    spec_base = _bounded_int(10 + features.evidence_density * 60 + min(features.evidence_reference_count, 20) * 1.5)
    
    # Layer 2: Relational
    narrative_base = _bounded_int(20 + features.narrative_density * 50 + len(features.section_presence) * 4)
    continuity_base = _bounded_int(15 + features.repeated_subject_ratio * 65 + min(features.unique_subject_count, 12) * 1.5)
    
    # Layer 3: Cluster (Major-specific)
    depth_base = _bounded_int(10 + features.major_term_overlap_ratio * 75 + min(features.unique_subject_count, 8) * 2.0)
    suitability_base = depth_base # Heuristic fallback matches depth unless semantic provides better

    def _merge(base: int, semantic_grade: AxisSemanticGrade | None) -> tuple[int, str, list[str]]:
        if semantic_grade is None:
            return base, "", []
        score = _bounded_int(base * 0.3 + semantic_grade.score * 0.7)
        return score, semantic_grade.rationale, semantic_grade.evidence_hints

    u_rigor_score, u_rigor_rat, u_rigor_hints = _merge(rigor_base, semantic.universal_rigor if semantic else None)
    u_spec_score, u_spec_rat, u_spec_hints = _merge(spec_base, semantic.universal_specificity if semantic else None)
    r_narr_score, r_narr_rat, r_narr_hints = _merge(narrative_base, semantic.relational_narrative if semantic else None)
    r_cont_score, r_cont_rat, r_cont_hints = _merge(continuity_base, semantic.relational_continuity if semantic else None)
    c_depth_score, c_depth_rat, c_depth_hints = _merge(depth_base, semantic.cluster_depth if semantic else None)
    c_suit_score, c_suit_rat, c_suit_hints = _merge(suitability_base, semantic.cluster_suitability if semantic else None)

    authenticity_risk = _bounded_int(
        80 - features.reliability_score * 40 - features.evidence_density * 25 - features.repeated_subject_ratio * 15
        + (20 if features.needs_review else 0)
    )

    return [
        _positive_axis(
            key="universal_rigor",
            score=u_rigor_score,
            rationale=u_rigor_rat or "학업 성취와 기록의 신뢰도를 바탕으로 산출된 학업 엄밀성입니다.",
            hints=u_rigor_hints or [f"신뢰도 점수: {round(features.reliability_score, 2)}", f"전체 기록 수: {features.total_records}"],
        ),
        _positive_axis(
            key="universal_specificity",
            score=u_spec_score,
            rationale=u_spec_rat or "기록 내 구체적 사실과 근거 참조 빈도를 분석한 결과입니다.",
            hints=u_spec_hints or [f"근거 밀도: {round(features.evidence_density, 2)}", f"근거 참조 수: {features.evidence_reference_count}"],
        ),
        _positive_axis(
            key="relational_narrative",
            score=r_narr_score,
            rationale=r_narr_rat or "섹션 간 조화와 서술의 풍부함을 바탕으로 평가한 서사 발전성입니다.",
            hints=r_narr_hints or [f"서술 밀도: {round(features.narrative_density, 2)}", f"활성화 섹션 수: {sum(1 for p in features.section_presence.values() if p)}"],
        ),
        _positive_axis(
            key="relational_continuity",
            score=r_cont_score,
            rationale=r_cont_rat or "학년별/과목별 탐구 주제의 반복과 심화 과정을 분석했습니다.",
            hints=r_cont_hints or [f"반복 과목 비율: {round(features.repeated_subject_ratio, 2)}", f"고유 과목 수: {features.unique_subject_count}"],
        ),
        _positive_axis(
            key="cluster_depth",
            score=c_depth_score,
            rationale=c_depth_rat or "목표 전공 관련 키워드와 심화 활동의 깊이를 평가했습니다.",
            hints=c_depth_hints or [f"전공 키워드 중첩도: {round(features.major_term_overlap_ratio, 2)}"],
        ),
        _positive_axis(
            key="cluster_suitability",
            score=c_suit_score,
            rationale=c_suit_rat or "기록 전반에 나타난 진로 지향성과 전공 적합성을 종합 분석했습니다.",
            hints=c_suit_hints or [f"전공 일치 단서 존재 여부", f"진로 탐색 구체성"],
        ),
        _authenticity_risk_axis(
            score=authenticity_risk,
            hints=[f"파싱 신뢰도: {round(features.reliability_score, 2)}", f"검토 필요 문서: {features.needs_review_documents}"],
        ),
    ]


def _positive_axis(
    *,
    key: PositiveAxisKey,
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
        label=POSITIVE_AXIS_LABELS[key],
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
        rationale = "근거 대비 주장 과장 가능성이 높아 보수적 서술과 근거 보강이 필요합니다."
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
        return "전공 연계 단서가 있으나 기록 전반에서 반복 노출이 더 필요합니다."
    return "전공 연결 신호가 약해 핵심 과목/활동 근거를 보강해야 합니다."


def _inquiry_rationale(score: int) -> str:
    if score >= 80:
        return "탐구 흐름이 단발성이 아니라 후속 활동으로 이어집니다."
    if score >= 60:
        return "탐구 연속성 단서가 일부 있으나 문제-시도-개선 흐름을 더 명확히 해야 합니다."
    return "활동이 분절적으로 보일 수 있어 비교·연속·심화 흐름 보강이 필요합니다."


def _evidence_rationale(score: int) -> str:
    if score >= 80:
        return "수치/관찰 기록 근거가 충분해 주장을 방어하기 유리합니다."
    if score >= 60:
        return "핵심 근거는 있으나 주장 대비 근거 밀도를 단계적으로 높일 필요가 있습니다."
    return "근거 밀도가 낮아 결론 주장보다 관찰 사실 축적이 우선입니다."


def _process_rationale(score: int) -> str:
    if score >= 80:
        return "과정 설명과 반성 기록이 구체적으로 드러납니다."
    if score >= 60:
        return "과정 서술은 있으나 방법-한계-개선 연결을 더 선명히 해야 합니다."
    return "무엇을 했는지는 보이나 왜/어떻게 했는지의 과정 설명이 부족합니다."


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
    semantic: SemanticDiagnosisExtraction | None = None,
) -> list[str]:
    strengths: list[str] = []
    if semantic and semantic.strengths:
        strengths.extend(semantic.strengths)
    for axis in admission_axes:
        if axis.key != "authenticity_risk" and axis.band == "strong":
            strengths.append(f"{axis.label}: {axis.rationale}")
    if not strengths:
        strengths.append("핵심 섹션 기반의 기본 근거는 확보되어 있습니다.")
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
    for axis in admission_axes:
        if axis.key != "authenticity_risk" and axis.band in {"weak", "watch"}:
            gaps.append(f"{axis.label}: {axis.rationale}")
    if features.total_records < 5:
        gaps.append("기록 총량이 적어 근거 확보가 필요합니다.")
    if not gaps:
        gaps.append("현재 구조를 유지하되 수치·비교·반성 근거를 추가하면 완성도가 높아집니다.")
    return _dedupe_keep_order(gaps)[:10]


def _build_risk_flags(
    *,
    features: StudentRecordFeatures,
    admission_axes: list[AdmissionAxisResult],
) -> list[str]:
    flags = list(features.risk_flags)
    authenticity = next((axis for axis in admission_axes if axis.key == "authenticity_risk"), None)
    if authenticity and authenticity.band == "high_risk":
        flags.append("진정성·과장 위험 축이 높아 보수적 문장 운영이 필요합니다.")
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
            actions.append("핵심 주장 3개마다 페이지 앵커, 관찰값, 비교 기준을 1개씩 붙여 추상 표현을 줄이세요.")
        elif axis.key == "cluster_depth":
            actions.append("가장 강한 탐구 1개를 선택해 방법-한계-개선-후속 질문 순서로 4문장 보강안을 만드세요.")
        elif axis.key == "universal_rigor":
            actions.append("교과 개념 또는 이론어 2개를 실제 활동 결과와 연결해 학업 엄밀성 문장을 보강하세요.")
        elif axis.key == "relational_narrative":
            actions.append("활동 간 전환 이유를 한 문장씩 추가해 단순 나열이 아닌 성장 서사로 재배열하세요.")
    if features.needs_review:
        actions.append("검토 필요 문서는 원문 대조 후 핵심 문장을 보수적으로 재작성하세요.")
    if target_major:
        actions.append(f"{target_major} 맥락에 맞는 활동 1개를 선정해 기존 근거로 방어 가능한 심화 보고서 주제를 만드세요.")
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
