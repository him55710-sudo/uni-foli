from __future__ import annotations

import re
import asyncio
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from unifoli_api.core.llm import LLMRequestError, get_llm_client
from unifoli_api.db.models.citation import Citation
from unifoli_api.db.models.diagnosis_run import DiagnosisRun
from unifoli_api.db.models.document_chunk import DocumentChunk
from unifoli_api.db.models.policy_flag import PolicyFlag
from unifoli_api.db.models.project import Project
from unifoli_api.db.models.response_trace import ResponseTrace
from unifoli_api.db.models.review_task import ReviewTask
from unifoli_api.db.models.user import User
from unifoli_api.services.diagnosis_axis_schema import (
    POSITIVE_AXIS_LABELS,
    PositiveAxisKey,
    normalize_positive_axis_key,
)
from unifoli_api.services.diagnosis_scoring_service import (
    AdmissionAxisResult,
    DocumentQualitySummary,
    RelationalGraph,
    SectionAnalysisItem,
)
from unifoli_api.services.llm_cache_service import CacheRequest, fetch_cached_response, store_cached_response
from unifoli_api.services.prompt_registry import get_prompt_registry
from unifoli_ingest.masking import MaskingPipeline
from unifoli_domain.enums import EvidenceProvenance, RenderFormat
from unifoli_render.template_registry import RenderTemplate, get_template, list_templates, rank_templates_for_keywords


class DiagnosisCitation(BaseModel):
    id: str | None = None
    document_id: str | None = None
    document_chunk_id: str | None = None
    provenance_type: str = EvidenceProvenance.STUDENT_RECORD.value
    source_label: str
    page_number: int | None = None
    excerpt: str
    relevance_score: float


class DiagnosisGap(BaseModel):
    title: str = Field(description="Gap title")
    description: str = Field(description="Why this is a gap and what evidence is missing")
    difficulty: Literal["low", "medium", "high"] = "medium"


class DiagnosisQuest(BaseModel):
    title: str = Field(description="Actionable task title")
    description: str = Field(description="Steps the student can take right now")
    priority: Literal["low", "medium", "high"] = "medium"


class DiagnosisSummary(BaseModel):
    overview: str
    target_context: str
    reasoning: str
    authenticity_note: str


GapAxisKey = PositiveAxisKey
AxisSeverity = Literal["strong", "watch", "weak"]
DirectionComplexity = Literal["lighter", "balanced", "deeper"]


class GapAxis(BaseModel):
    key: GapAxisKey
    label: str
    score: int = Field(ge=0, le=100)
    severity: AxisSeverity
    rationale: str
    evidence_hint: str | None = None

    @field_validator("key", mode="before")
    @classmethod
    def _normalize_key(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = normalize_positive_axis_key(value)
            if normalized is None:
                raise ValueError("Unsupported gap axis key.")
            return normalized
        return value


class TopicCandidate(BaseModel):
    id: str
    title: str
    summary: str
    why_it_fits: str
    evidence_hooks: list[str] = Field(default_factory=list)


class PageCountOption(BaseModel):
    id: str
    label: str
    page_count: int = Field(ge=5, le=20)
    rationale: str


class FormatRecommendation(BaseModel):
    format: Literal["pdf", "pptx", "hwpx"]
    label: str
    rationale: str
    recommended: bool = False
    caution: str | None = None


class TemplatePreviewMetadata(BaseModel):
    accent_color: str
    surface_tone: str
    cover_title: str
    preview_sections: list[str] = Field(default_factory=list)
    thumbnail_hint: str


class TemplateCandidate(BaseModel):
    id: str
    label: str
    description: str
    supported_formats: list[Literal["pdf", "pptx", "hwpx"]] = Field(default_factory=list)
    category: str
    section_schema: list[str] = Field(default_factory=list)
    density: str
    visual_priority: str
    supports_provenance_appendix: bool
    recommended_for: list[str] = Field(default_factory=list)
    preview: TemplatePreviewMetadata
    why_it_fits: str | None = None
    recommended: bool = False


class RecommendedDirection(BaseModel):
    id: str
    label: str
    summary: str
    why_now: str
    complexity: DirectionComplexity
    related_axes: list[GapAxisKey] = Field(default_factory=list)
    topic_candidates: list[TopicCandidate] = Field(default_factory=list)
    page_count_options: list[PageCountOption] = Field(default_factory=list)
    format_recommendations: list[FormatRecommendation] = Field(default_factory=list)
    template_candidates: list[TemplateCandidate] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def _normalize_direction_id(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_positive_axis_key(value) or value
        return value

    @field_validator("related_axes", mode="before")
    @classmethod
    def _normalize_related_axes(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        for item in value:
            if isinstance(item, str):
                normalized.append(normalize_positive_axis_key(item) or item)
            else:
                normalized.append(item)
        return normalized


class RecommendedDefaultAction(BaseModel):
    direction_id: str
    topic_id: str
    page_count: int = Field(ge=5, le=20)
    export_format: Literal["pdf", "pptx", "hwpx"]
    template_id: str
    rationale: str

    @field_validator("direction_id", mode="before")
    @classmethod
    def _normalize_direction_id(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_positive_axis_key(value) or value
        return value


class GuidedOutlineSection(BaseModel):
    id: str
    title: str
    purpose: str
    evidence_plan: list[str] = Field(default_factory=list)
    authenticity_guardrail: str


class GuidedDraftOutline(BaseModel):
    title: str
    summary: str
    outline_markdown: str
    sections: list[GuidedOutlineSection] = Field(default_factory=list)
    export_format: Literal["pdf", "pptx", "hwpx"]
    template_id: str
    template_label: str
    page_count: int = Field(ge=5, le=20)
    include_provenance_appendix: bool = False
    hide_internal_provenance_on_final_export: bool = True
    draft_id: str | None = None
    draft_title: str | None = None


class DiagnosisResult(BaseModel):
    headline: str = Field(description="Short diagnosis summary headline")
    overview: str | None = Field(default=None, description="Structured diagnosis overview")
    strengths: list[str] = Field(description="Current grounded strengths in the record")
    gaps: list[str] = Field(description="Visible evidence or inquiry gaps to close next")
    detailed_gaps: list[DiagnosisGap] = Field(default_factory=list, description="Structured gap analysis")
    recommended_focus: str = Field(description="Most important next focus")
    action_plan: list[DiagnosisQuest] = Field(default_factory=list, description="Concrete next quests")
    risk_level: Literal["safe", "warning", "danger"] = Field(description="Risk tier")
    document_quality: DocumentQualitySummary | None = None
    section_analysis: list[SectionAnalysisItem] = Field(default_factory=list)
    admission_axes: list[AdmissionAxisResult] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    recommended_topics: list[str] = Field(default_factory=list)
    diagnosis_summary: DiagnosisSummary | None = None
    gap_axes: list[GapAxis] = Field(default_factory=list)
    recommended_directions: list[RecommendedDirection] = Field(default_factory=list)
    recommended_default_action: RecommendedDefaultAction | None = None
    relational_graph: RelationalGraph | None = None
    citations: list[DiagnosisCitation] = Field(default_factory=list)
    policy_codes: list[str] = Field(default_factory=list)
    review_required: bool = False
    response_trace_id: str | None = None
    requested_llm_provider: str | None = None
    requested_llm_model: str | None = None
    actual_llm_provider: str | None = None
    actual_llm_model: str | None = None
    llm_profile_used: str | None = None
    fallback_used: bool | None = None
    fallback_reason: str | None = None
    processing_duration_ms: int | None = None


@dataclass(frozen=True)
class PolicyFlagMatch:
    code: str
    severity: str
    detail: str
    matched_text: str
    match_count: int


class DiagnosisGenerationError(RuntimeError):
    def __init__(self, *, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = str(reason_code or "provider_error").strip() or "provider_error"
        self.detail = str(detail or "").strip() or None
        super().__init__(self.detail or self.reason_code)


MASKING_PIPELINE = MaskingPipeline()
TOKEN_PATTERN = re.compile(r"[가-힣A-Z?-?0-9]{2,}")
OPEN_REVIEW_STATUSES = {"open", "pending"}
AXIS_LABELS: dict[GapAxisKey, str] = dict(POSITIVE_AXIS_LABELS)
POLICY_FLAG_RULES: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "sensitive_email",
        "high",
        "Input text contains an email address.",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    ),
    (
        "sensitive_phone",
        "high",
        "Input text contains a phone number.",
        re.compile(r"\b(?:01[016789]|0[2-9]\d?)\s*[-]?\s*\d{3,4}\s*[-]?\s*\d{4}\b"),
    ),
    (
        "sensitive_rrn",
        "critical",
        "Input text contains a resident registration number.",
        re.compile(r"\b\d{6}\s*[-]?\s*[1-4]\d{6}\b"),
    ),
    (
        "sensitive_student_id",
        "medium",
        "Input text contains a student identifier.",
        re.compile(r"(?:student\s*id|learner\s*id|id)\s*[:#]?\s*[A-Za-z0-9-]{4,20}", re.IGNORECASE),
    ),
    (
        "fabrication_request",
        "critical",
        "Input text appears to request fabricated or false admissions content.",
        re.compile(r"(?:fabricat(?:e|ed|ion)|make\s+up|false\s+content|invent(?:ed)?|ghostwrit(?:e|ing))", re.IGNORECASE),
    ),
)


def _normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _clip(text: str | None, *, limit: int = 160) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _severity_for_score(score: int) -> AxisSeverity:
    if score >= 75:
        return "strong"
    if score >= 50:
        return "watch"
    return "weak"


def _difficulty_for_score(score: int) -> Literal["low", "medium", "high"]:
    if score >= 75:
        return "low"
    if score >= 50:
        return "medium"
    return "high"


def _tokenize_for_overlap(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text or "")}


def _trim_excerpt(text: str, *, limit: int = 240) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _major_terms(target_major: str | None, career_direction: str | None, universities: list[str] | None = None) -> list[str]:
    univ_str = " ".join(universities or [])
    raw = f"{target_major or ''} {career_direction or ''} {univ_str}"
    # Supports Korean (2+ chars) and English (2+ chars, like SNU, MIT)
    return [token.lower() for token in re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}", raw)]


def _score_axis(
    *,
    key: GapAxisKey,
    score: int,
    rationale: str,
    evidence_hint: str,
) -> GapAxis:
    bounded = max(0, min(score, 100))
    return GapAxis(
        key=key,
        label=AXIS_LABELS[key],
        score=bounded,
        severity=_severity_for_score(bounded),
        rationale=rationale,
        evidence_hint=evidence_hint,
    )


def _infer_gap_axes(
    *,
    full_text: str,
    target_major: str | None,
    target_university: str | None,
    interest_universities: list[str] | None = None,
    career_direction: str | None,
) -> list[GapAxis]:
    lowered = (full_text or "").lower()
    word_count = len((full_text or "").split())
    numeric_hits = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", full_text or ""))

    # Korean educational context keywords
    conceptual_terms = ["원리", "개념", "이론", "모델", "이유", "메커니즘", "왜", "principle", "mechanism", "concept"]
    application_terms = ["적용", "실험", "프로젝트", "활용", "해결", "solution", "project", "application"]
    inquiry_terms = ["비교", "차이", "경향", "분석", "후속", "심화", "comparison", "inquiry", "difference"]
    evidence_hits_terms = ["데이터", "측정", "결과", "관찰", "증거", "실증", "data", "evidence", "result"]
    process_terms = ["과정", "절차", "한계", "성찰", "피드백", "reflection", "process", "method"]

    concept_hits = sum(1 for term in conceptual_terms if term in lowered)
    application_hits = sum(1 for term in application_terms if term in lowered)
    inquiry_hits = sum(1 for term in inquiry_terms if term in lowered)
    evidence_hits = sum(1 for term in evidence_hits_terms if term in lowered)
    process_hits = sum(1 for term in process_terms if term in lowered)
    
    all_targets = []
    if target_university: all_targets.append(target_university)
    if interest_universities: all_targets.extend(interest_universities)
    
    overlap_hits = sum(1 for term in _major_terms(target_major, career_direction, all_targets) if term in lowered)

    conceptual_score = 45 + (concept_hits * 12) - max(0, application_hits - concept_hits) * 7
    continuity_score = 40 + (inquiry_hits * 12) + (10 if word_count >= 220 else 0)
    evidence_score = 35 + min(word_count // 12, 25) + min(evidence_hits * 8, 20) + min(numeric_hits * 3, 12)
    process_score = 35 + (process_hits * 12) + (8 if "성찰" in lowered or "reflect" in lowered else 0)
    depth_score = (
        38
        + (concept_hits * 8)
        + (overlap_hits * 12)
        + min(inquiry_hits * 4, 12)
        + (6 if word_count >= 220 else 0)
    )
    if target_major and overlap_hits == 0:
        depth_score -= 10

    # Alignment score considering multiple targets
    target_count = (1 if target_university else 0) + len(interest_universities or [])
    alignment_score = 40 + (overlap_hits * 15) + (min(target_count * 4, 12))

    return [
        _score_axis(
            key="universal_rigor",
            score=conceptual_score,
            rationale=(
                "활동의 기저에 있는 원리나 메커니즘을 설명하려는 시도가 확인됩니다."
                if conceptual_score >= 75
                else "활동의 '내용'은 있으나, 구체적인 원리나 이론적 근거에 대한 서술이 보안되어야 합니다."
            ),
            evidence_hint="학술용어나 원리 중심의 키워드(메커니즘, 원형 등)가 포함된 문장을 찾아보세요.",
        ),
        _score_axis(
            key="universal_specificity",
            score=evidence_score,
            rationale=(
                "탐구의 신뢰성을 뒷받침할 만한 구체적인 데이터나 수치적 근거가 포함되어 있습니다."
                if evidence_score >= 75
                else "관찰 결과나 데이터가 추상적입니다. 구체적인 수치나 명확한 팩트 위주의 서술이 필요합니다."
            ),
            evidence_hint="수치, 백분율, 데이터 소스, 구체적인 고유 명사 등의 포함 여부를 확인하세요.",
        ),
        _score_axis(
            key="relational_narrative",
            score=process_score,
            rationale=(
                "탐구 과정에서의 시행착오와 그에 따른 성찰 과정이 구체적으로 나타나 있습니다."
                if process_score >= 75
                else "활동의 한계점이나 배운 점에 대한 성찰이 부족합니다. 과정 중심의 서술을 보강하세요."
            ),
            evidence_hint="'성찰', '느낀 점', '한계점' 또는 방법론적 고민이 담긴 구문을 확인하세요.",
        ),
        _score_axis(
            key="relational_continuity",
            score=continuity_score,
            rationale=(
                "이전 활동과의 연결성이나 후속 탐구로 이어지는 흐름이 잘 보입니다."
                if continuity_score >= 75
                else "단발성 활동으로 보일 수 있습니다. 활동 간의 인과관계나 심화 질문을 통한 연결이 필요합니다."
            ),
            evidence_hint="'후속', '비교', '확장' 등 활동의 흐름을 보여주는 표현이 있는지 보세요.",
        ),
        _score_axis(
            key="cluster_depth",
            score=depth_score,
            rationale=(
                "전공과 연계된 깊이 있는 질문을 던지고 이를 학술적으로 파고든 흔적이 명확합니다."
                if depth_score >= 75
                else "전공 관련 지식의 수준이 기초적인 단계에 머물러 있습니다. 더 좁고 깊은 탐구가 필요합니다."
            ),
            evidence_hint="전공 핵심 개념(Major-Specific)이 얼마나 정교하게 사용되었는지 확인하세요.",
        ),
        _score_axis(
            key="cluster_suitability",
            score=alignment_score,
            rationale=(
                "희망 전공 및 대학의 인재상과 부합하는 탐구 방향성이 잘 정립되어 있습니다."
                if alignment_score >= 75
                else "희망 전공과의 연결 고리가 다소 작위적이거나 약합니다. 전공 역량을 더 자연스럽게 드러내야 합니다."
            ),
            evidence_hint="목표 대학/전공 키워드(SNU, 특정 학과명 등)와 활동의 정합성을 확인하세요.",
        ),
    ]


def _strengths_from_axes(gap_axes: list[GapAxis]) -> list[str]:
    strengths = [axis.rationale for axis in gap_axes if axis.severity == "strong"]
    return strengths or ["활용 가능한 기초 활동 기록이 존재하지만, 근거를 보강하고 탐구의 흐름을 더 명확히 할 필요가 있습니다."]


def _gaps_from_axes(gap_axes: list[GapAxis]) -> list[str]:
    gaps = [axis.rationale for axis in gap_axes if axis.severity != "strong"]
    return gaps or ["가장 강점이 있는 주제를 선택하여 구체적인 증거와 성찰이 담긴 후속 활동으로 심화시키세요."]


def _detailed_gaps_from_axes(gap_axes: list[GapAxis]) -> list[DiagnosisGap]:
    return [
        DiagnosisGap(
            title=axis.label,
            description=axis.rationale,
            difficulty=_difficulty_for_score(axis.score),
        )
        for axis in gap_axes
        if axis.severity != "strong"
    ]


def _risk_level_from_axes(gap_axes: list[GapAxis]) -> Literal["safe", "warning", "danger"]:
    weak_count = sum(1 for axis in gap_axes if axis.severity == "weak")
    watch_count = sum(1 for axis in gap_axes if axis.severity == "watch")
    if weak_count >= 2 or (weak_count >= 1 and watch_count >= 2):
        return "danger"
    if weak_count >= 1 or watch_count >= 2:
        return "warning"
    return "safe"


def _page_count_options_for_complexity(complexity: DirectionComplexity) -> list[PageCountOption]:
    if complexity == "lighter":
        return [
            PageCountOption(
                id="compact_5",
                label="5페이지 구성",
                page_count=5,
                rationale="최소 필수 요소를 중심으로 주장의 핵심과 근거를 간결하게 정리합니다.",
            ),
            PageCountOption(
                id="focused_6",
                label="6페이지 구성",
                page_count=6,
                rationale="핵심 탐구 기록에 한 페이지를 추가하여 증거의 구체성을 높입니다.",
            ),
        ]
    if complexity == "deeper":
        return [
            PageCountOption(
                id="full_6",
                label="6페이지 구성",
                page_count=6,
                rationale="심화 탐구의 방법론과 분석, 성찰 과정을 충분히 담아낼 수 있는 표준 구성입니다.",
            ),
            PageCountOption(
                id="extended_7",
                label="7페이지 구성",
                page_count=7,
                rationale="비교 분석이나 시계열적인 변화 등 복잡한 탐구 맥락을 상세히 기술할 때 적합합니다.",
            ),
        ]
    return [
        PageCountOption(
            id="balanced_5",
            label="5페이지 구성",
            page_count=5,
            rationale="질문, 근거, 방법론, 성찰이 균형 있게 담긴 표준 분석 리포트 형식입니다.",
        ),
        PageCountOption(
            id="balanced_6",
            label="6페이지 구성",
            page_count=6,
            rationale="심화된 비교 분석이나 한계점 분석을 위한 추가 섹션을 포함합니다.",
        ),
    ]


def _normalize_direction_page_count_options(direction: RecommendedDirection) -> None:
    normalized: list[PageCountOption] = []
    seen: set[int] = set()
    for option in direction.page_count_options:
        if option.page_count < 5:
            continue
        if option.page_count in seen:
            continue
        seen.add(option.page_count)
        normalized.append(
            PageCountOption(
                id=option.id or f"{direction.id}_{option.page_count}",
                label=option.label or f"{option.page_count}페이지 구성",
                page_count=option.page_count,
                rationale=option.rationale or "진단 리포트는 최소 5페이지 이상의 신뢰도 높은 구성을 권장합니다.",
            )
        )

    if not normalized:
        normalized = _page_count_options_for_complexity(direction.complexity)
    direction.page_count_options = normalized


def _normalize_guided_choice_constraints(result: DiagnosisResult) -> None:
    if not result.recommended_directions:
        result.recommended_default_action = None
        return

    for direction in result.recommended_directions:
        _normalize_direction_page_count_options(direction)

    fallback_default = _recommended_default_action_from_directions(result.recommended_directions)
    current_default = result.recommended_default_action
    if current_default is None:
        result.recommended_default_action = fallback_default
        return

    direction = next((item for item in result.recommended_directions if item.id == current_default.direction_id), None)
    if direction is None:
        result.recommended_default_action = fallback_default
        return

    topic_ids = {item.id for item in direction.topic_candidates}
    page_counts = {item.page_count for item in direction.page_count_options}
    formats = {item.format for item in direction.format_recommendations}
    template_ids = {
        item.id
        for item in direction.template_candidates
        if current_default.export_format in item.supported_formats
    }

    is_valid = (
        current_default.topic_id in topic_ids
        and current_default.page_count in page_counts
        and current_default.page_count >= 5
        and current_default.export_format in formats
        and current_default.template_id in template_ids
    )
    if not is_valid:
        result.recommended_default_action = fallback_default


def _format_recommendations_for_axis(axis_key: GapAxisKey, complexity: DirectionComplexity) -> list[FormatRecommendation]:
    recommendations: dict[GapAxisKey, list[FormatRecommendation]] = {
        "universal_rigor": [
            FormatRecommendation(format="pdf", label="PDF 리포트", rationale="원리 중심의 설명과 논리적 섹션 구성에 가장 적합합니다.", recommended=True),
            FormatRecommendation(format="hwpx", label="HWPX 제출용", rationale="학교 제출 양식에 맞춘 보수적인 구성에 유리합니다."),
            FormatRecommendation(format="pptx", label="발표용 덱", rationale="핵심 원리를 시각적으로 빠르게 전달해야 할 때 활용합니다.", caution="복잡한 개념이 지나치게 단순화될 위험이 있습니다."),
        ],
        "universal_specificity": [
            FormatRecommendation(format="pdf", label="PDF 리포트", rationale="풍부한 증거 자료와 수치, 출처를 한눈에 정리하기 좋습니다.", recommended=True),
            FormatRecommendation(format="hwpx", label="HWPX 제출용", rationale="선생님께 제출할 근거 중심의 보고서 형식으로 적합합니다."),
            FormatRecommendation(format="pptx", label="발표용 덱", rationale="핵심 데이터 시각화가 필요한 경우에 유용합니다.", caution="방대한 근거가 슬라이드에 다 담기지 않을 수 있습니다."),
        ],
        "relational_narrative": [
            FormatRecommendation(format="pdf", label="PDF 리포트", rationale="활동의 과정, 한계점, 성찰을 서술형으로 담기에 최적입니다.", recommended=True),
            FormatRecommendation(format="hwpx", label="HWPX 제출용", rationale="생활기록부 서술 문체와 유사한 정형화된 보고서에 좋습니다."),
            FormatRecommendation(format="pptx", label="발표용 덱", rationale="과정 중심의 스토리를 명확한 단계로 보여주고 싶을 때 사용합니다."),
        ],
        "relational_continuity": [
            FormatRecommendation(format="pptx", label="발표용 덱", rationale="탐구의 발전 단계나 전후 비교를 시각적인 흐름으로 보여주기 좋습니다.", recommended=True),
            FormatRecommendation(format="pdf", label="PDF 리포트", rationale="연속적인 탐구 맥락을 텍스트로 상세히 설명해야 할 때 사용합니다."),
            FormatRecommendation(format="hwpx", label="HWPX 제출용", rationale="학교의 연속 탐구 과제 제출 양식으로 활용 가능합니다."),
        ],
        "cluster_depth": [
            FormatRecommendation(format="pdf", label="PDF 리포트", rationale="전공 심화 탐구의 논리적 깊이와 전문성을 보여주기에 가장 좋습니다.", recommended=True),
            FormatRecommendation(format="pptx", label="발표용 덱", rationale="하나의 깊은 질문에 대한 탐구 과정을 시각적으로 증명할 때 사용합니다."),
            FormatRecommendation(format="hwpx", label="HWPX 제출용", rationale="전공 관련 과목의 심화 수행평가 보고서 양식으로 적합합니다."),
        ],
        "cluster_suitability": [
            FormatRecommendation(format="hwpx", label="HWPX 제출용", rationale="진로 희망과 연계된 활동을 정제된 학교 양식으로 담기에 가장 적합합니다.", recommended=True),
            FormatRecommendation(format="pdf", label="PDF 리포트", rationale="전공 적합성 논거를 조금 더 상세히 설명해야 할 때 유리합니다."),
            FormatRecommendation(format="pptx", label="발표용 덱", rationale="전공에 대한 관심도를 시각적 단서로 효과적으로 노출할 수 있습니다."),
        ],
    }

    selected = [item.model_copy() for item in recommendations[axis_key]]
    if complexity == "deeper":
        for item in selected:
            item.recommended = item.format == "pdf"
    return selected


def _template_candidates_for_axis(
    *,
    axis_key: GapAxisKey,
    target_major: str | None,
    preferred_formats: list[str],
) -> list[TemplateCandidate]:
    keywords = [axis_key.replace("_", " "), target_major or ""]
    preferred_render_formats = [RenderFormat(item) for item in preferred_formats]
    ranked_templates: list[RenderTemplate] = []
    seen_ids: set[str] = set()

    for render_format in preferred_render_formats:
        for template in rank_templates_for_keywords(render_format=render_format, keywords=keywords):
            if template.id in seen_ids:
                continue
            seen_ids.add(template.id)
            ranked_templates.append(template)
            if len(ranked_templates) >= 6:
                break
        if len(ranked_templates) >= 6:
            break

    return [
        TemplateCandidate(
            id=template.id,
            label=template.label,
            description=template.description,
            supported_formats=[item.value for item in template.supported_formats],
            category=template.category,
            section_schema=list(template.section_schema),
            density=template.density,
            visual_priority=template.visual_priority,
            supports_provenance_appendix=template.supports_provenance_appendix,
            recommended_for=list(template.recommended_for),
            preview=TemplatePreviewMetadata(
                accent_color=template.preview.accent_color,
                surface_tone=template.preview.surface_tone,
                cover_title=template.preview.cover_title,
                preview_sections=list(template.preview.preview_sections),
                thumbnail_hint=template.preview.thumbnail_hint,
            ),
            why_it_fits=f"이 주제는 '{AXIS_LABELS[axis_key]}' 측면을 보완하는 데 가장 적합한 레이아웃을 제공합니다.",
            recommended=index == 0,
        )
        for index, template in enumerate(ranked_templates)
    ]


def _topic_candidates_for_axis(
    *,
    axis_key: GapAxisKey,
    major_label: str,
    project_title: str,
) -> list[TopicCandidate]:
    topics: dict[GapAxisKey, list[tuple[str, str, str]]] = {
        "universal_rigor": [
            ("core_principle_reset", f"{major_label} 관련 핵심 원리 탐구", "단순 적용을 넘어 현상의 기저에 있는 원리에 집중하는 재구성"),
            ("why_this_works", f"{project_title or major_label} 내 메커니즘 분석", "실용적 활동을 원리 중심의 학술적 분석으로 전환"),
        ],
        "universal_specificity": [
            ("measure_more_clearly", f"{project_title or '현재 주제'}의 객관적 데이터 보강", "기존 주제를 유지하되 더 명확한 측정치나 관찰 기록을 추가"),
            ("evidence_matrix", f"{major_label} 탐구를 위한 증거 매트릭스", "이미 관찰된 사실과 추가 확보가 필요한 데이터를 체계적으로 정리"),
        ],
        "relational_narrative": [
            ("method_limit_map", f"{project_title or '탐구'}의 방법론 및 한계 분석", "탐구가 수행된 구체적 방법과 한계점을 명확히 기술하여 신뢰도 확보"),
            ("reflection_upgrade", f"{major_label} 성찰 중심의 기록 재작성", "학생의 생각 변화와 배운 점을 중심으로 서술 구조를 개편"),
        ],
        "relational_continuity": [
            ("followup_comparison", f"{project_title or '현재 기록'}을 확장하는 후속 비교 분석", "단발성 활동에서 벗어나 두 번째 단계의 질문을 던져 연속성 확보"),
            ("semester_thread", f"{major_label} 관련 학기별 탐구 로드맵", "첫 활동에서 다음 증거 확보로 이어지는 서사적 연결 고리 생성"),
        ],
        "cluster_depth": [
            ("major_depth_probe", f"{major_label} 심화 질문에 대한 실증적 탐구", "넓은 주제에서 벗어나 전공 핵심 질문 하나에 집중하는 탐구"),
            ("major_method_upgrade", f"{major_label} 경로를 위한 방법론 심화", "현재 주제를 유지하면서 전공 특화 키워드를 활용한 방법론적 고도화"),
        ],
        "cluster_suitability": [
            ("major_link_frame", f"현재 활동과 {major_label}의 접점 구체화", "전문적이고 억지스럽지 않은 방식으로 전공과의 연결 고리를 명징하게 제시"),
            ("major_question_shift", f"기존 근거를 활용한 {major_label} 중심 질문 전환", "확보된 증거는 유지하되 탐구 질문을 전공 방향으로 틀어서 정합성 강화"),
        ],
    }
    return [
        TopicCandidate(
            id=topic_id,
            title=title,
            summary=summary,
            why_it_fits=summary,
            evidence_hooks=[
                "학생부에 이미 기록된 구체적인 디테일 한 가지를 재사용하세요.",
                "학생이 실제로 방어 가능한 수준의 비교, 관찰 또는 성찰을 한 가지 추가하세요.",
            ],
        )
        for topic_id, title, summary in topics[axis_key]
    ]


def _direction_from_axis(*, axis: GapAxis, major_label: str, project_title: str) -> RecommendedDirection:
    complexity: DirectionComplexity = "deeper" if axis.severity == "weak" else "lighter" if axis.key == "cluster_suitability" else "balanced"
    copy: dict[GapAxisKey, tuple[str, str]] = {
        "universal_rigor": ("원리 중심 재구성", "단순 적용에서 벗어나 핵심 기저 원리와 메커니즘을 탐구하는 방향으로 전환합니다."),
        "universal_specificity": ("증거 구체화 스프린트", "주제를 좁히고 구체적인 데이터, 관찰 기록, 인용 근거를 보강하여 주장의 밀도를 높입니다."),
        "relational_narrative": ("방법 및 성찰 강화", "활동 결과보다 과정의 구체적 방법론과 그 과정에서의 성찰을 정밀하게 기술합니다."),
        "relational_continuity": ("후속 탐구 연결", "단절된 활동들을 하나의 흐름으로 묶고, 후속 질문을 통해 탐구의 연속성을 보여줍니다."),
        "cluster_depth": ("전공 심화 탐구", "목표 전공과 관련된 좁고 깊은 질문을 설정하고 전문적인 방법론을 적용해 깊이를 만듭니다."),
        "cluster_suitability": ("전공 정합성 최적화", "기존 활동들을 목표 전공의 인재상이나 핵심 역량과 더 자연스럽게 연결되도록 재정렬합니다."),
    }
    label, summary = copy[axis.key]
    format_recommendations = _format_recommendations_for_axis(axis.key, complexity)
    return RecommendedDirection(
        id=axis.key,
        label=label,
        summary=summary,
        why_now=axis.rationale,
        complexity=complexity,
        related_axes=[axis.key],
        topic_candidates=_topic_candidates_for_axis(axis_key=axis.key, major_label=major_label, project_title=project_title),
        page_count_options=_page_count_options_for_complexity(complexity),
        format_recommendations=format_recommendations,
        template_candidates=_template_candidates_for_axis(axis_key=axis.key, target_major=major_label, preferred_formats=[item.format for item in format_recommendations]),
    )


def _recommended_directions_from_axes(*, gap_axes: list[GapAxis], major_label: str, project_title: str) -> list[RecommendedDirection]:
    sorted_axes = sorted(gap_axes, key=lambda item: item.score)
    target_count = 2 if len([axis for axis in gap_axes if axis.severity == "strong"]) >= 3 else 3
    target_count = min(5, max(2, target_count + sum(1 for axis in gap_axes if axis.severity == "weak") - 1))
    selected_axes = [axis for axis in sorted_axes if axis.severity != "strong"][:target_count]
    if len(selected_axes) < 2:
        selected_axes = sorted_axes[:2]
    return [_direction_from_axis(axis=axis, major_label=major_label, project_title=project_title) for axis in selected_axes[:5]]


def _recommended_default_action_from_directions(
    directions: list[RecommendedDirection],
) -> RecommendedDefaultAction | None:
    if not directions:
        return None

    direction = directions[0]
    if not direction.topic_candidates or not direction.page_count_options or not direction.format_recommendations:
        return None

    topic = direction.topic_candidates[0]
    page_count = direction.page_count_options[0]
    format_choice = next(
        (item for item in direction.format_recommendations if item.recommended),
        direction.format_recommendations[0],
    )
    template_choice = next(
        (
            item
            for item in direction.template_candidates
            if format_choice.format in item.supported_formats and item.recommended
        ),
        None,
    ) or next(
        (item for item in direction.template_candidates if format_choice.format in item.supported_formats),
        None,
    ) or (direction.template_candidates[0] if direction.template_candidates else None)
    if template_choice is None:
        return None

    return RecommendedDefaultAction(
        direction_id=direction.id,
        topic_id=topic.id,
        page_count=page_count.page_count,
        export_format=format_choice.format,
        template_id=template_choice.id,
        rationale=(
            f"가장 시급한 보완이 필요한 '{direction.label}' 축을 해결하기 위해 이 방향을 추천합니다. "
            f"{page_count.page_count}페이지 분량의 {format_choice.format.upper()} 리포트로 바로 시작할 수 있습니다."
        ),
    )


def _diagnosis_summary(
    *,
    gap_axes: list[GapAxis],
    target_university: str | None,
    target_major: str | None,
    interest_universities: list[str] | None = None,
    career_direction: str | None,
) -> DiagnosisSummary:
    weak_axes = [axis.label for axis in gap_axes if axis.severity != "strong"]
    strong_axes = [axis.label for axis in gap_axes if axis.severity == "strong"]
    extra_targets = f" / 관심 대학교: {', '.join(interest_universities)}" if interest_universities else ""
    return DiagnosisSummary(
        overview=(
            "현재 학생부 기록은 "
            f"{', '.join(strong_axes[:2]) if strong_axes else '기초적인 활동 근거'} 면에서 가장 강점이 있으며, "
            "단순한 결과 나열보다는 구체적인 증거와 원리 중심의 서술로 전환이 필요한 단계입니다."
        ),
        target_context=(
            f"목표 대학교: {target_university or '설정 안 됨'} / "
            f"목표 전공: {target_major or '설정 안 됨'} / "
            f"진로 방향: {career_direction or '설정 안 됨'}"
            f"{extra_targets}"
        ),
        reasoning=(
            f"이후의 가이드는 주로 {', '.join(weak_axes[:3]) if weak_axes else '근거 기반의 심화 단계'}를 보강하는 방향으로 구성되었습니다."
        ),
        authenticity_note="학생부 원본의 사실만을 근간으로 하세요. 다음 리포트는 없는 성취를 꾸며내는 것이 아니라, 이미 있는 근거를 깊게 파고드는 작업이어야 합니다.",
    )


def _build_guided_diagnosis(
    *,
    project_title: str,
    target_major: str | None,
    target_university: str | None,
    interest_universities: list[str] | None = None,
    career_direction: str | None,
    full_text: str,
) -> DiagnosisResult:
    # Construct multi-target label for display
    targets = []
    if target_university:
        targets.append(f"{target_university} {target_major or ''}".strip())
    if interest_universities:
        targets.extend(interest_universities)
    
    target_context_label = " 및 ".join(targets[:2]) + (f" 외 {len(targets)-2}개" if len(targets) > 2 else "")
    if not target_context_label:
        target_context_label = target_major or "희망 전공"

    major_label = target_major or "희망 전공"
    gap_axes = _infer_gap_axes(
        full_text=full_text,
        target_major=target_major,
        target_university=target_university,
        interest_universities=interest_universities,
        career_direction=career_direction,
    )
    directions = _recommended_directions_from_axes(gap_axes=gap_axes, major_label=major_label, project_title=project_title)
    risk_level = _risk_level_from_axes(gap_axes)
    result = DiagnosisResult(
        headline=(
            f"{target_context_label} 입시 관점에서, 현재 기록은 {'조심스럽게 심화를 진행할 수 있는 기반이 마련되어 있습니다' if risk_level == 'safe' else '방어 가능한 근거가 일부 부족한 상태입니다'}; "
            "다음 활동은 양적인 확장보다 증거의 밀도와 방향성을 정교화하는 데 집중해야 합니다."
        ),
        strengths=_strengths_from_axes(gap_axes),
        gaps=_gaps_from_axes(gap_axes),
        detailed_gaps=_detailed_gaps_from_axes(gap_axes),
        recommended_focus=(
            f"{target_context_label} 합격을 목표로 할 때, 현재 가장 필요한 단계는 "
            f"{next((axis.label for axis in gap_axes if axis.severity != 'strong'), '기존 근거 기반의 심화')} 측면을 강화하는 것입니다. "
            "포장된 수식어보다 실제 수행 가능한 활동에 집중하세요."
        ),
        action_plan=[DiagnosisQuest(title=direction.label, description=direction.summary, priority="high" if index == 0 else "medium") for index, direction in enumerate(directions)],
        risk_level=risk_level,
        diagnosis_summary=_diagnosis_summary(
            gap_axes=gap_axes,
            target_university=target_university,
            target_major=target_major,
            interest_universities=interest_universities,
            career_direction=career_direction,
        ),
        gap_axes=gap_axes,
        recommended_directions=directions,
        recommended_default_action=_recommended_default_action_from_directions(directions),
    )
    _normalize_guided_choice_constraints(result)
    return result


def build_grounded_diagnosis_result(
    *,
    project_title: str,
    target_major: str | None,
    target_university: str | None = None,
    interest_universities: list[str] | None = None,
    career_direction: str | None = None,
    document_count: int,
    full_text: str,
) -> DiagnosisResult:
    _ = document_count
    return _build_guided_diagnosis(
        project_title=project_title,
        target_major=target_major,
        target_university=target_university,
        interest_universities=interest_universities,
        career_direction=career_direction,
        full_text=full_text,
    )


def _has_complete_guided_contract(result: DiagnosisResult) -> bool:
    expected_axes = set(AXIS_LABELS.keys())
    actual_axes = {axis.key for axis in result.gap_axes}
    return (
        result.diagnosis_summary is not None
        and len(result.gap_axes) == len(expected_axes)
        and actual_axes == expected_axes
        and bool(result.recommended_directions)
        and result.recommended_default_action is not None
    )


def _hydrate_guided_fields(
    *,
    result: DiagnosisResult,
    project_title: str,
    target_major: str | None,
    target_university: str | None,
    interest_universities: list[str] | None = None,
    career_direction: str | None,
    full_text: str,
) -> DiagnosisResult:
    _normalize_guided_choice_constraints(result)
    if _has_complete_guided_contract(result):
        return result

    fallback = build_grounded_diagnosis_result(
        project_title=project_title,
        target_major=target_major,
        target_university=target_university,
        interest_universities=interest_universities,
        career_direction=career_direction,
        document_count=1,
        full_text=full_text,
    )
    if not result.diagnosis_summary:
        result.diagnosis_summary = fallback.diagnosis_summary
    if len(result.gap_axes) != len(AXIS_LABELS) or {axis.key for axis in result.gap_axes} != set(AXIS_LABELS.keys()):
        result.gap_axes = fallback.gap_axes
    if not result.recommended_directions:
        result.recommended_directions = fallback.recommended_directions
    if result.recommended_default_action is None:
        result.recommended_default_action = fallback.recommended_default_action
    if not result.strengths:
        result.strengths = fallback.strengths
    if not result.gaps:
        result.gaps = fallback.gaps
    if not result.detailed_gaps:
        result.detailed_gaps = fallback.detailed_gaps
    if not result.action_plan:
        result.action_plan = fallback.action_plan
    if not result.recommended_focus:
        result.recommended_focus = fallback.recommended_focus
    _normalize_guided_choice_constraints(result)
    if result.recommended_default_action is None:
        result.recommended_default_action = fallback.recommended_default_action
    return result


async def evaluate_student_record(
    user_major: str,
    masked_text: str,
    target_university: str | None = None,
    target_major: str | None = None,
    interest_universities: list[str] | None = None,
    career_direction: str | None = None,
    project_title: str | None = None,
    scope_key: str = "global",
    evidence_keys: list[str] | None = None,
    bypass_cache: bool = False,
    raise_on_llm_failure: bool = False,
) -> DiagnosisResult:
    from unifoli_api.core.config import get_settings

    extra_targets = ""
    if interest_universities:
        targets_str = ", ".join(interest_universities)
        extra_targets = f"\nOther Interest Universities: {targets_str}"

    target_context = (
        f"Target University: {target_university or 'Not set'}\n"
        f"Target Major: {target_major or user_major}\n"
        f"Career Direction: {career_direction or 'Not set'}"
        f"{extra_targets}"
    )

    system_instruction = _build_diagnosis_system_instruction(
        target_context=target_context,
        user_major=user_major,
        masked_text=masked_text,
    )
    prompt = _build_diagnosis_prompt()

    settings = get_settings()
    llm = get_llm_client()
    model_name = _current_model_name()
    cache_request = CacheRequest(
        feature_name="diagnosis.evaluate_student_record",
        model_name=model_name,
        scope_key=scope_key,
        config_version=settings.llm_cache_version,
        ttl_seconds=settings.llm_cache_ttl_seconds if settings.llm_cache_enabled else 0,
        bypass=bypass_cache or not settings.llm_cache_enabled,
        response_format="json",
        evidence_keys=evidence_keys or [],
        payload={
            "target_context": target_context,
            "user_major": user_major,
            "masked_text": masked_text,
            "system_instruction": system_instruction,
            "prompt": prompt,
            "temperature": 0.2,
        },
    )

    # Retry logic for robustness
    max_retries = 2
    last_exc = None

    try:
        from unifoli_api.core.database import SessionLocal

        with SessionLocal() as cache_db:
            cached = fetch_cached_response(cache_db, cache_request)
        if cached:
            cached_result = DiagnosisResult.model_validate_json(cached)
            return _hydrate_guided_fields(
                result=cached_result,
                project_title=project_title or "학생 기록부",
                target_major=target_major or user_major,
                target_university=target_university,
                interest_universities=interest_universities,
                career_direction=career_direction,
                full_text=masked_text,
            )

        for attempt in range(max_retries + 1):
            try:
                result = await llm.generate_json(
                    prompt=prompt,
                    response_model=DiagnosisResult,
                    system_instruction=system_instruction,
                    temperature=0.2,
                )
                result = _hydrate_guided_fields(
                    result=result,
                    project_title=project_title or "학생 기록부",
                    target_major=target_major or user_major,
                    target_university=target_university,
                    interest_universities=interest_universities,
                    career_direction=career_direction,
                    full_text=masked_text,
                )
                with SessionLocal() as cache_db:
                    store_cached_response(cache_db, cache_request, response_payload=result.model_dump_json())
                return result
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < max_retries:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                break
        
        if last_exc: raise last_exc

    except Exception as exc:  # noqa: BLE001
        if raise_on_llm_failure:
            raise DiagnosisGenerationError(
                reason_code=_classify_diagnosis_generation_failure(exc),
                detail=str(exc),
            ) from exc
        fallback = build_grounded_diagnosis_result(
            project_title=project_title or "학생 기록부",
            target_major=target_major or user_major,
            target_university=target_university,
            interest_universities=interest_universities,
            career_direction=career_direction,
            document_count=1,
            full_text=masked_text,
        )
        fallback.headline = f"{fallback.headline} AI 진단 지연으로 인한 자동 분석 결과가 적용되었습니다."
        return fallback


def _classify_diagnosis_generation_failure(exc: Exception) -> str:
    if isinstance(exc, DiagnosisGenerationError):
        return exc.reason_code

    if isinstance(exc, LLMRequestError):
        reason = str(getattr(exc, "limited_reason", "") or "").strip().lower()
        if "timeout" in reason:
            return "provider_timeout"
        if "unreachable" in reason or "connection" in reason:
            return "connection_issue"
        if "model_not_found" in reason:
            return "model_not_found"
        if "invalid_json" in reason:
            return "invalid_json"
        if "invalid_request" in reason:
            return "invalid_request"
        if "provider_error" in reason:
            return "provider_error"
        return "provider_error"

    name = type(exc).__name__.strip().lower()
    if "timeout" in name:
        return "provider_timeout"
    if "connection" in name or "connect" in name or "network" in name:
        return "connection_issue"
    if "json" in name or "decode" in name or "validation" in name:
        return "invalid_json"
    return "provider_error"


def detect_policy_flags(text: str) -> list[PolicyFlagMatch]:
    findings: list[PolicyFlagMatch] = []
    for code, severity, detail, pattern in POLICY_FLAG_RULES:
        matches = list(pattern.finditer(text or ""))
        if not matches:
            continue
        findings.append(
            PolicyFlagMatch(
                code=code,
                severity=severity,
                detail=f"{detail} Match count: {len(matches)}.",
                matched_text=matches[0].group(0)[:180],
                match_count=len(matches),
            )
        )
    return findings


def attach_policy_flags_to_run(
    db: Session,
    *,
    run: DiagnosisRun,
    project: Project,
    user: User,
    findings: list[PolicyFlagMatch],
) -> list[PolicyFlag]:
    records: list[PolicyFlag] = []
    for finding in findings:
        record = PolicyFlag(
            diagnosis_run_id=run.id,
            project_id=project.id,
            user_id=user.id,
            code=finding.code,
            severity=finding.severity,
            detail=finding.detail,
            matched_text=finding.matched_text,
            match_count=finding.match_count,
            status="open",
        )
        db.add(record)
        records.append(record)
    if records:
        db.flush()
    return records


def ensure_review_task_for_flags(
    db: Session,
    *,
    run: DiagnosisRun,
    project: Project,
    user: User,
    findings: list[PolicyFlagMatch],
) -> ReviewTask | None:
    if not findings:
        return None

    existing = db.scalar(
        select(ReviewTask).where(
            ReviewTask.diagnosis_run_id == run.id,
            ReviewTask.status.in_(OPEN_REVIEW_STATUSES),
        )
    )
    if existing is not None:
        return existing

    task = ReviewTask(
        diagnosis_run_id=run.id,
        project_id=project.id,
        user_id=user.id,
        task_type="policy_review",
        status="open",
        assigned_role="admin",
        reason="Safety review required before trusting the analysis trace.",
        details={
            "policy_codes": [finding.code for finding in findings],
            "severities": [finding.severity for finding in findings],
            "match_count": sum(finding.match_count for finding in findings),
        },
    )
    db.add(task)
    db.flush()
    return task


def build_diagnosis_citations(
    *,
    chunks: list[DocumentChunk],
    result: DiagnosisResult,
    limit: int = 3,
) -> list[DiagnosisCitation]:
    if not chunks:
        return []

    query_terms = _tokenize_for_overlap(" ".join([result.headline, *result.strengths, *result.gaps, result.recommended_focus]))
    scored: list[tuple[float, DocumentChunk]] = []

    for chunk in chunks:
        chunk_terms = _tokenize_for_overlap(chunk.content_text)
        if not chunk_terms:
            continue
        overlap = len(query_terms & chunk_terms)
        density = overlap / max(len(query_terms), 1)
        score = overlap + density
        scored.append((score, chunk))

    if not scored:
        return []

    scored.sort(key=lambda item: (-item[0], item[1].chunk_index))
    selected = [item for item in scored if item[0] > 0][:limit]
    if not selected:
        selected = scored[: min(limit, len(scored))]

    citations: list[DiagnosisCitation] = []
    for score, chunk in selected:
        source_label = chunk.document.original_filename if chunk.document is not None else None
        citations.append(
            DiagnosisCitation(
                document_id=chunk.document_id,
                document_chunk_id=chunk.id,
                provenance_type=EvidenceProvenance.STUDENT_RECORD.value,
                source_label=source_label or f"문서 조각 {chunk.chunk_index + 1}",
                page_number=chunk.page_number,
                excerpt=_trim_excerpt(chunk.content_text),
                relevance_score=round(max(score, 0.1), 3),
            )
        )
    return citations


def create_response_trace(
    db: Session,
    *,
    run: DiagnosisRun,
    project: Project,
    user: User,
    input_text: str,
    result: DiagnosisResult,
    chunks: list[DocumentChunk],
    model_name: str,
) -> tuple[ResponseTrace, list[Citation]]:
    masked_excerpt = MASKING_PIPELINE.apply_masking(_trim_excerpt(input_text, limit=1600))
    response_excerpt = _trim_excerpt(" ".join([result.headline, *result.strengths, *result.gaps, result.recommended_focus]), limit=1600)

    trace = ResponseTrace(
        diagnosis_run_id=run.id,
        project_id=project.id,
        user_id=user.id,
        model_name=model_name,
        request_excerpt=masked_excerpt,
        response_excerpt=response_excerpt,
        trace_metadata={
            "risk_level": result.risk_level,
            "strength_count": len(result.strengths),
            "gap_count": len(result.gaps),
            "direction_count": len(result.recommended_directions),
        },
    )
    db.add(trace)
    db.flush()

    citation_records: list[Citation] = []
    for payload in build_diagnosis_citations(chunks=chunks, result=result):
        record = Citation(
            response_trace_id=trace.id,
            diagnosis_run_id=run.id,
            project_id=project.id,
            document_id=payload.document_id,
            document_chunk_id=payload.document_chunk_id,
            source_label=payload.source_label,
            page_number=payload.page_number,
            excerpt=payload.excerpt,
            relevance_score=payload.relevance_score,
        )
        db.add(record)
        citation_records.append(record)

    if citation_records:
        db.flush()
    return trace, citation_records


def _humanize_section_key(key: str) -> str:
    mapping = {
        "title": "주제명",
        "context": "인식 및 동기",
        "analysis": "탐구 분석",
        "reflection": "성찰 및 학습",
        "next_steps": "향후 보완 계획",
        "research_question": "탐구 질문",
        "evidence_review": "근거 분석",
        "method": "탐구 방법",
        "limitations": "한계점 인식",
        "comparison_frame": "비교 분석 프레임",
        "case_a": "사례 A 분석",
        "case_b": "사례 B 분석",
        "implications": "시사점",
        "problem": "문제 인식",
        "proposal": "대안 제시",
        "expected_impact": "기대 효과",
        "feasibility": "실현 가능성 점검",
        "starting_point": "탐구의 시작",
        "turning_points": "결정적 변화",
        "growth": "성장 포인트",
        "current_position": "현재의 위치",
        "next_move": "다음 스텝",
        "agenda": "리포트 개요",
        "evidence": "핵심 근거",
        "hook": "핵심 요약(Hook)",
        "visual_evidence": "시각적 근거(도표)",
        "interpretation": "결과 해석",
        "takeaway": "핵심 결론",
        "activity_scope": "활동 범위",
        "what_i_did": "수행 내용",
        "what_i_learned": "배운 점",
        "record_note": "기록 요약",
    }
    return mapping.get(key, key.replace("_", " ").title())


def _section_purpose(section_key: str, topic: TopicCandidate, direction: RecommendedDirection) -> str:
    purposes = {
        "title": f"선택된 주제 '{topic.title}'를 학생부의 실제 근거와 연결하여 한 문장으로 제시합니다.",
        "context": "추상적인 동기가 아닌, 학생부 내 구체적인 상황이나 의문점에서 탐구가 시작된 배경을 설명합니다.",
        "analysis": "기존 학생부 기록이 이미 증명하고 있는 역량과 탐구의 수준을 객관적으로 분석합니다.",
        "reflection": "활동을 통해 학생의 생각이나 관점이 어떻게 변화했는지, 새롭게 깨달은 점은 무엇인지 기술합니다.",
        "next_steps": "허황된 계획이 아닌, 학생의 현재 수준에서 실제로 수행 가능한 논리적인 다음 단계를 제시합니다.",
        "research_question": "답변 가능하고(Answerable), 구체적인(Specific) 하나의 탐구 질문을 설정합니다.",
        "evidence_review": "학생부 내에서 이 탐구를 뒷받침하는 가장 강력한 증거 키워드들을 나열합니다.",
        "method": "어떤 자료를 참고했는지, 실험이나 관찰을 어떻게 수행했는지 구체적인 방법론을 기술합니다.",
        "limitations": "탐구의 부족했던 점이나 데이터의 한계를 솔직하게 인정하여 진실성을 확보합니다.",
        "comparison_frame": "비교 분석을 위해 설정한 두 가지 대조군 또는 관점의 기준을 설명합니다.",
        "case_a": "첫 번째 사례나 관점에서 도출된 핵심 데이터를 요약합니다.",
        "case_b": "두 번째 사례나 관점에서 도출된 핵심 데이터를 요약합니다.",
        "implications": "위의 비교를 통해 목표 전공(Major)과 관련된 어떤 새로운 통찰을 얻었는지 설명합니다.",
        "problem": "기존 기록에서 보완이 필요한 지점이나 탐구가 필요한 논리적 공백을 명시합니다.",
        "proposal": "학생이 실제로 수행하여 기록을 보강할 수 있는 현실적인 보완책을 제안합니다.",
        "expected_impact": "이 보완책을 통해 학생부의 어떤 역량(전공 적합성 등)이 강화될지 기술합니다.",
        "feasibility": "제안된 활동이 학교 환경이나 학생의 현재 역량 내에서 가능한지 확인합니다.",
        "starting_point": "탐구의 시발점이 된 학생부 내의 특정 수업 활동이나 교사 코멘트를 인용합니다.",
        "turning_points": "탐구 과정 중 어려움을 극복하거나 질문의 방향이 바뀐 결정적 순간을 기술합니다.",
        "growth": "탐구 전후로 학생의 학술적 태도나 심화 지식이 어떻게 성장했는지 요약합니다.",
        "current_position": "기존 학생부에서 이 주제와 관련된 현재까지의 성취 수준을 진단합니다.",
        "next_move": "입시 관점에서 가장 높은 평가를 받을 수 있는 단 하나의 방어 가능한 후속 조치를 제시합니다.",
        "agenda": "발표 리포트의 전체적인 흐름을 슬라이드별 핵심 문구로 요약합니다.",
        "evidence": "학생이 직접 설명하거나 증명할 수 있는 가장 확실한 결과물 위주로 제시합니다.",
        "hook": "청중(입학사정관 등)의 관심을 끌 수 있는, 근거에 기반한 강렬한 요약 문구를 제시합니다.",
        "visual_evidence": "복잡한 데이터나 관계도를 한눈에 보여줄 수 있는 핵심 시각 자료 구성을 제안합니다.",
        "interpretation": "수치나 팩트가 전공 입장에서 어떤 가치를 지니는지 과도한 수식 없이 해석합니다.",
        "takeaway": "기록을 통해 최종적으로 증명하고자 하는 학생의 핵심 역량을 단문으로 결론짓습니다.",
        "activity_scope": "학생이 실제로 관여한 영역과 탐구의 경계를 명확히 하여 신뢰도를 확보합니다.",
        "what_i_did": "학생부에 기록되어 있거나 학생이 실제로 수행한 구체적 행위들을 리스트업합니다.",
        "what_i_learned": "활동을 통해 내재화된 전공 관련 학술적 원리나 태도를 정리합니다.",
        "record_note": "생활기록부의 '세부능력 및 특기사항' 등에 기재되기 가장 적합한 정제된 요약문을 작성합니다.",
    }
    return purposes.get(section_key, f"'{direction.label}' 방향성에 맞춰 학생부의 근거를 학술적으로 강화합니다.")


def build_guided_outline_plan(
    *,
    result: DiagnosisResult,
    direction_id: str,
    topic_id: str,
    page_count: int,
    export_format: Literal["pdf", "pptx", "hwpx"],
    template_id: str,
    include_provenance_appendix: bool = False,
    hide_internal_provenance_on_final_export: bool = True,
) -> tuple[RecommendedDirection, TopicCandidate, GuidedDraftOutline]:
    direction = next((item for item in result.recommended_directions if item.id == direction_id), None)
    if direction is None:
        raise ValueError("해당 진단에서 선택한 방향(Direction)을 찾을 수 없습니다.")
    topic = next((item for item in direction.topic_candidates if item.id == topic_id), None)
    if topic is None:
        raise ValueError("선택한 주제(Topic)가 해당 방향에 존재하지 않습니다.")
    if page_count not in {item.page_count for item in direction.page_count_options}:
        raise ValueError("선택한 페이지 수 옵션이 유효하지 않습니다.")
    if page_count < 5:
        raise ValueError("진단 리포트 생성에는 최소 5페이지가 필요합니다.")
    if export_format not in {item.format for item in direction.format_recommendations}:
        raise ValueError("선택한 내보내기 형식이 해당 방향에서 지원되지 않습니다.")

    template = get_template(template_id, render_format=RenderFormat(export_format))
    section_limit = min(len(template.section_schema), max(5, page_count + 1))
    section_keys = list(template.section_schema[:section_limit])
    citation_hooks = [citation.source_label for citation in result.citations[:2]]
    sections = [
        GuidedOutlineSection(
            id=section_key,
            title=_humanize_section_key(section_key),
            purpose=_section_purpose(section_key, topic, direction),
            evidence_plan=[*topic.evidence_hooks[:2], *citation_hooks][:3],
            authenticity_guardrail="학생 학생부 기록에 아직 없거나 향후 수행 계획이 아닌 허위 주장은 절대 포함하지 마세요.",
        )
        for section_key in section_keys
    ]
    outline_markdown = "\n\n".join(
        [
            f"# {topic.title}",
            f"## 요약\n{topic.summary}",
            *[
                "\n".join(
                    [
                        f"## {section.title}",
                        section.purpose,
                        "",
                        "근거 확보 계획:",
                        *[f"- {item}" for item in section.evidence_plan],
                        "",
                        f"진실성 가이드라인: {section.authenticity_guardrail}",
                    ]
                )
                for section in sections
            ],
        ]
    ).strip()
    outline = GuidedDraftOutline(
        title=topic.title,
        summary=direction.summary,
        outline_markdown=outline_markdown,
        sections=sections,
        export_format=export_format,
        template_id=template.id,
        template_label=template.label,
        page_count=page_count,
        include_provenance_appendix=include_provenance_appendix,
        hide_internal_provenance_on_final_export=hide_internal_provenance_on_final_export,
    )
    return direction, topic, outline


def serialize_policy_flag(flag: PolicyFlag) -> dict[str, object]:
    return {
        "id": flag.id,
        "code": flag.code,
        "severity": flag.severity,
        "detail": flag.detail,
        "matched_text": flag.matched_text,
        "match_count": flag.match_count,
        "status": flag.status,
        "created_at": flag.created_at.isoformat() if flag.created_at else None,
    }


def serialize_citation(citation: Citation) -> dict[str, object]:
    return {
        "id": citation.id,
        "document_id": citation.document_id,
        "document_chunk_id": citation.document_chunk_id,
        "provenance_type": EvidenceProvenance.STUDENT_RECORD.value,
        "source_label": citation.source_label,
        "page_number": citation.page_number,
        "excerpt": citation.excerpt,
        "relevance_score": citation.relevance_score,
    }


def latest_response_trace(run: DiagnosisRun) -> ResponseTrace | None:
    if not run.response_traces:
        return None
    return max(run.response_traces, key=lambda item: item.created_at)


def _current_model_name() -> str:
    from unifoli_api.core.config import get_settings

    settings = get_settings()
    if settings.llm_provider == "ollama":
        return settings.ollama_model
    return "gemini-1.5-pro"


def _template_catalog_prompt_block() -> str:
    lines = ["[Allowed Template Registry]"]
    for template in list_templates():
        formats = ", ".join(item.value for item in template.supported_formats)
        recommended_for = "; ".join(template.recommended_for[:3]) or "general grounded output"
        lines.append(
            f"- {template.id}: {template.label} | formats: {formats} | category: {template.category} | "
            f"density: {template.density} | visual_priority: {template.visual_priority} | "
            f"provenance_appendix: {'yes' if template.supports_provenance_appendix else 'no'} | "
            f"recommended_for: {recommended_for}"
        )
    return "\n".join(lines)


def _build_diagnosis_system_instruction(
    *,
    target_context: str,
    user_major: str,
    masked_text: str,
) -> str:
    template_catalog = _template_catalog_prompt_block()
    base_instruction = get_prompt_registry().compose_prompt("diagnosis.grounded-analysis")
    
    return (
        base_instruction.replace("{{target_context}}", target_context)
        .replace("{{user_major}}", user_major)
        .replace("{{template_catalog}}", template_catalog)
        .replace("{{masked_text}}", masked_text)
    )


def _build_diagnosis_prompt() -> str:
    return (
        "제시된 생활기록부 전문과 입시 목표를 바탕으로 종합 진단을 수행하십시오. "
        "반드시 부여된 Structured Response Contract를 엄격히 준수하여 JSON 형태로 출력하십시오."
    )
