from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.core.llm import get_llm_client
from polio_api.db.models.citation import Citation
from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.db.models.document_chunk import DocumentChunk
from polio_api.db.models.policy_flag import PolicyFlag
from polio_api.db.models.project import Project
from polio_api.db.models.response_trace import ResponseTrace
from polio_api.db.models.review_task import ReviewTask
from polio_api.db.models.user import User
from polio_api.services.diagnosis_scoring_service import (
    AdmissionAxisResult,
    DocumentQualitySummary,
    SectionAnalysisItem,
)
from polio_api.services.llm_cache_service import CacheRequest, fetch_cached_response, store_cached_response
from polio_api.services.prompt_registry import get_prompt_registry
from polio_ingest.masking import MaskingPipeline
from polio_domain.enums import EvidenceProvenance, RenderFormat
from polio_render.template_registry import RenderTemplate, get_template, list_templates, rank_templates_for_keywords


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


GapAxisKey = Literal[
    "conceptual_depth",
    "inquiry_continuity",
    "evidence_density",
    "process_explanation",
    "subject_major_alignment",
]
AxisSeverity = Literal["strong", "watch", "weak"]
DirectionComplexity = Literal["lighter", "balanced", "deeper"]


class GapAxis(BaseModel):
    key: GapAxisKey
    label: str
    score: int = Field(ge=0, le=100)
    severity: AxisSeverity
    rationale: str
    evidence_hint: str | None = None


class TopicCandidate(BaseModel):
    id: str
    title: str
    summary: str
    why_it_fits: str
    evidence_hooks: list[str] = Field(default_factory=list)


class PageCountOption(BaseModel):
    id: str
    label: str
    page_count: int = Field(ge=1, le=20)
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


class RecommendedDefaultAction(BaseModel):
    direction_id: str
    topic_id: str
    page_count: int = Field(ge=1, le=20)
    export_format: Literal["pdf", "pptx", "hwpx"]
    template_id: str
    rationale: str


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
    page_count: int
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
    citations: list[DiagnosisCitation] = Field(default_factory=list)
    policy_codes: list[str] = Field(default_factory=list)
    review_required: bool = False
    response_trace_id: str | None = None


@dataclass(frozen=True)
class PolicyFlagMatch:
    code: str
    severity: str
    detail: str
    matched_text: str
    match_count: int


MASKING_PIPELINE = MaskingPipeline()
TOKEN_PATTERN = re.compile(r"[A-Za-z가-힣0-9]{2,}")
OPEN_REVIEW_STATUSES = {"open", "pending"}
AXIS_LABELS: dict[GapAxisKey, str] = {
    "conceptual_depth": "Conceptual depth",
    "inquiry_continuity": "Inquiry continuity",
    "evidence_density": "Evidence density",
    "process_explanation": "Process explanation",
    "subject_major_alignment": "Subject-major alignment",
}
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
        re.compile(r"(?:학번|학생번호|student\s*id)\s*[:#]?\s*[A-Za-z0-9-]{4,20}", re.IGNORECASE),
    ),
    (
        "fabrication_request",
        "critical",
        "Input text appears to request fabricated or false admissions content.",
        re.compile(
            r"(허위|조작|없는\s+(?:활동|경험|실험)|사실이\s+아닌|꾸며|가짜|fabricat(?:e|ed|ion)|make\s+up)",
            re.IGNORECASE,
        ),
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


def _major_terms(target_major: str | None, career_direction: str | None) -> list[str]:
    raw = f"{target_major or ''} {career_direction or ''}"
    return [token.lower() for token in re.findall(r"[A-Za-z]{3,}", raw)]


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
    career_direction: str | None,
) -> list[GapAxis]:
    lowered = (full_text or "").lower()
    word_count = len((full_text or "").split())
    numeric_hits = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", full_text or ""))

    conceptual_terms = ["principle", "concept", "theory", "model", "reason", "why", "mechanism"]
    application_terms = ["application", "practical", "project", "using", "use", "solution", "service"]
    inquiry_terms = ["compare", "difference", "trend", "before", "after", "follow-up", "iterate", "again"]
    evidence_terms = ["data", "measure", "measured", "survey", "result", "observation", "evidence", "experiment"]
    process_terms = ["method", "process", "step", "procedure", "limit", "limitation", "reflection", "feedback"]

    concept_hits = sum(1 for term in conceptual_terms if term in lowered)
    application_hits = sum(1 for term in application_terms if term in lowered)
    inquiry_hits = sum(1 for term in inquiry_terms if term in lowered)
    evidence_hits = sum(1 for term in evidence_terms if term in lowered)
    process_hits = sum(1 for term in process_terms if term in lowered)
    overlap_hits = sum(1 for term in _major_terms(target_major, career_direction) if term in lowered)

    conceptual_score = 45 + (concept_hits * 12) - max(0, application_hits - concept_hits) * 7
    if "math" in lowered and application_hits > concept_hits:
        conceptual_score -= 10
    continuity_score = 40 + (inquiry_hits * 12) + (10 if word_count >= 220 else 0)
    evidence_score = 35 + min(word_count // 12, 25) + min(evidence_hits * 8, 20) + min(numeric_hits * 3, 12)
    process_score = 35 + (process_hits * 12) + (8 if "reflect" in lowered else 0)
    alignment_score = 40 + (overlap_hits * 15) + (8 if target_university else 0)

    return [
        _score_axis(
            key="conceptual_depth",
            score=conceptual_score,
            rationale=(
                "The record already explains principles or reasons behind the activity."
                if conceptual_score >= 75
                else "The record leans more on what was done than why the concept matters."
            ),
            evidence_hint="Look for places where the record explains principles, reasons, or mechanisms.",
        ),
        _score_axis(
            key="inquiry_continuity",
            score=continuity_score,
            rationale=(
                "The current record shows a visible follow-up path or comparison thread."
                if continuity_score >= 75
                else "The record still needs a clearer next-step chain instead of isolated activity fragments."
            ),
            evidence_hint="Comparison, follow-up questions, or iteration traces make this axis stronger.",
        ),
        _score_axis(
            key="evidence_density",
            score=evidence_score,
            rationale=(
                "The record already contains enough concrete evidence anchors for grounded drafting."
                if evidence_score >= 75
                else "The next step should add clearer observations, data points, or explicit evidence markers."
            ),
            evidence_hint="Measured results, observed differences, or concrete source notes help here.",
        ),
        _score_axis(
            key="process_explanation",
            score=process_score,
            rationale=(
                "The student record explains method, limits, or reflection with usable detail."
                if process_score >= 75
                else "Method steps and limitation notes are still too thin to defend the inquiry process."
            ),
            evidence_hint="Method steps, limit notes, and reflections are the key signals.",
        ),
        _score_axis(
            key="subject_major_alignment",
            score=alignment_score,
            rationale=(
                "The record already connects subject work to the target direction in a believable way."
                if alignment_score >= 75
                else "The next activity should make the major link clearer without pretending the student already did more."
            ),
            evidence_hint="Keep the major link explicit but grounded in what the student really did.",
        ),
    ]


def _strengths_from_axes(gap_axes: list[GapAxis]) -> list[str]:
    strengths = [axis.rationale for axis in gap_axes if axis.severity == "strong"]
    return strengths or ["The record has a workable starting point, but it still needs a clearer evidence trail."]


def _gaps_from_axes(gap_axes: list[GapAxis]) -> list[str]:
    gaps = [axis.rationale for axis in gap_axes if axis.severity != "strong"]
    return gaps or ["Turn the strongest topic into a deeper follow-up activity with clearer evidence and reflection."]


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
            PageCountOption(id="compact_2", label="2 pages", page_count=2, rationale="Best for one grounded claim and one short reflection."),
            PageCountOption(id="focused_3", label="3 pages", page_count=3, rationale="Adds space for one evidence section without overexpanding."),
        ]
    if complexity == "deeper":
        return [
            PageCountOption(id="full_5", label="5 pages", page_count=5, rationale="Fits a full method-analysis-reflection arc."),
            PageCountOption(id="extended_6", label="6 pages", page_count=6, rationale="Useful when comparison or timeline detail matters."),
        ]
    return [
        PageCountOption(id="balanced_3", label="3 pages", page_count=3, rationale="Enough room for question, evidence, and reflection."),
        PageCountOption(id="balanced_4", label="4 pages", page_count=4, rationale="Adds one more section for method or comparison."),
        PageCountOption(id="balanced_5", label="5 pages", page_count=5, rationale="Best when the inquiry needs a fuller arc."),
    ]


def _format_recommendations_for_axis(axis_key: GapAxisKey, complexity: DirectionComplexity) -> list[FormatRecommendation]:
    recommendations: dict[GapAxisKey, list[FormatRecommendation]] = {
        "conceptual_depth": [
            FormatRecommendation(format="pdf", label="PDF report", rationale="Best for concept-first explanation and clean section flow.", recommended=True),
            FormatRecommendation(format="hwpx", label="HWPX submission", rationale="Works well when the output needs to stay school-friendly."),
            FormatRecommendation(format="pptx", label="Presentation deck", rationale="Use only if the concept can be shown with very short slides.", caution="Slides can oversimplify nuanced explanations."),
        ],
        "inquiry_continuity": [
            FormatRecommendation(format="pptx", label="Presentation deck", rationale="Good for showing progression, comparison, or a step-by-step story.", recommended=True),
            FormatRecommendation(format="pdf", label="PDF report", rationale="Good when the continuity needs more paragraph-based explanation."),
            FormatRecommendation(format="hwpx", label="HWPX submission", rationale="Safe for school submission, but keep the timeline concise."),
        ],
        "evidence_density": [
            FormatRecommendation(format="pdf", label="PDF report", rationale="Best for fitting evidence, method, and reflection in one place.", recommended=True),
            FormatRecommendation(format="hwpx", label="HWPX submission", rationale="Useful when the teacher-facing export must stay conservative."),
            FormatRecommendation(format="pptx", label="Presentation deck", rationale="Use if the evidence can be shown in a few focused visuals.", caution="Dense evidence can feel too thin on slides."),
        ],
        "process_explanation": [
            FormatRecommendation(format="pdf", label="PDF report", rationale="Best for method steps, limits, and reflection paragraphs.", recommended=True),
            FormatRecommendation(format="hwpx", label="HWPX submission", rationale="Safe when the final format should resemble a school document."),
            FormatRecommendation(format="pptx", label="Presentation deck", rationale="Works only if the process can be broken into very clear steps."),
        ],
        "subject_major_alignment": [
            FormatRecommendation(format="hwpx", label="HWPX submission", rationale="Best for a conservative, record-friendly articulation of major fit.", recommended=True),
            FormatRecommendation(format="pdf", label="PDF report", rationale="Good when the alignment needs slightly more explanation."),
            FormatRecommendation(format="pptx", label="Presentation deck", rationale="Use when the major link is easier to show than to narrate."),
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
            why_it_fits=f"Recommended because it fits the {AXIS_LABELS[axis_key].lower()} repair focus.",
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
        "conceptual_depth": [
            ("core_principle_reset", f"{major_label} core principle behind the current activity", "Reframe the activity around one principle, not just the applied result."),
            ("why_this_works", f"Why the observed result happens in {project_title or major_label}", "Turn a practical activity into a principle-driven explanation."),
        ],
        "inquiry_continuity": [
            ("followup_comparison", f"One follow-up comparison extending {project_title or 'the current record'}", "Build a visible second step so the inquiry no longer feels isolated."),
            ("semester_thread", f"Semester progression question for {major_label}", "Create a narrative link from the first activity to the next evidence move."),
        ],
        "evidence_density": [
            ("measure_more_clearly", f"Add one clearer evidence set to {project_title or 'the current topic'}", "Keep the topic but strengthen it with a more explicit dataset or observation."),
            ("evidence_matrix", f"Evidence matrix for {major_label} inquiry", "Organize what is already observed and what still needs to be collected."),
        ],
        "process_explanation": [
            ("method_limit_map", f"Method and limitation map for {project_title or 'the inquiry'}", "Explain exactly how the activity was done and what its limits were."),
            ("reflection_upgrade", f"Reflection-first rewrite for {major_label}", "Center the draft on what changed in the student's thinking and why."),
        ],
        "subject_major_alignment": [
            ("major_link_frame", f"Grounded connection between current subject work and {major_label}", "Make the major link clearer without pretending the record is already specialized."),
            ("major_question_shift", f"{major_label} question shift based on the current record", "Keep the current evidence but change the inquiry question so it aligns better."),
        ],
    }
    return [
        TopicCandidate(
            id=topic_id,
            title=title,
            summary=summary,
            why_it_fits=summary,
            evidence_hooks=[
                "Reuse one grounded detail from the uploaded record.",
                "Add one comparison, observation, or reflection the student can actually defend.",
            ],
        )
        for topic_id, title, summary in topics[axis_key]
    ]


def _direction_from_axis(*, axis: GapAxis, major_label: str, project_title: str) -> RecommendedDirection:
    complexity: DirectionComplexity = "deeper" if axis.severity == "weak" else "lighter" if axis.key == "subject_major_alignment" else "balanced"
    copy: dict[GapAxisKey, tuple[str, str]] = {
        "conceptual_depth": ("Concept-driven reset", "Move the next output away from pure application and toward core principles or mechanisms."),
        "inquiry_continuity": ("Follow-up continuity path", "Build a second-step question so the record shows progression instead of one isolated activity."),
        "evidence_density": ("Evidence densification sprint", "Keep the topic narrow and add clearer observations, data, or citations before polishing claims."),
        "process_explanation": ("Method-and-reflection clarification", "Use the next output to explain how the work happened and what its limits were."),
        "subject_major_alignment": ("Major-alignment reframing", "Retune the topic so it sounds more like a believable bridge to the target direction."),
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
            f"Start with {direction.label.lower()} because it addresses the most immediate weak axis "
            f"and stays finishable with a {page_count.label.lower()} {format_choice.format.upper()} output."
        ),
    )


def _diagnosis_summary(*, gap_axes: list[GapAxis], target_university: str | None, target_major: str | None, career_direction: str | None) -> DiagnosisSummary:
    weak_axes = [axis.label for axis in gap_axes if axis.severity != "strong"]
    strong_axes = [axis.label for axis in gap_axes if axis.severity == "strong"]
    return DiagnosisSummary(
        overview=(
            "The current record is strongest where "
            f"{', '.join(strong_axes[:2]).lower() if strong_axes else 'there is at least one grounded starting point'}, "
            "and it needs the next move to stay focused on evidence rather than polish."
        ),
        target_context=(
            f"Target university: {target_university or 'Not set'} / "
            f"Target major: {target_major or 'Not set'} / "
            f"Career direction: {career_direction or 'Not set'}"
        ),
        reasoning=(
            "The guided directions below were ranked around "
            f"{', '.join(weak_axes[:3]).lower() if weak_axes else 'the next grounded improvement step'}."
        ),
        authenticity_note="Use the student record as the base truth. The next draft should deepen evidence, not invent accomplishments.",
    )


def _build_guided_diagnosis(*, project_title: str, target_major: str | None, target_university: str | None, career_direction: str | None, full_text: str) -> DiagnosisResult:
    major_label = target_major or "the selected major"
    gap_axes = _infer_gap_axes(full_text=full_text, target_major=target_major, target_university=target_university, career_direction=career_direction)
    directions = _recommended_directions_from_axes(gap_axes=gap_axes, major_label=major_label, project_title=project_title)
    risk_level = _risk_level_from_axes(gap_axes)
    return DiagnosisResult(
        headline=(
            f"For {major_label}, the record is {'grounded enough to move carefully' if risk_level == 'safe' else 'still missing a few defendable pieces'}; "
            "the next action should tighten evidence and direction rather than increase polish."
        ),
        strengths=_strengths_from_axes(gap_axes),
        gaps=_gaps_from_axes(gap_axes),
        detailed_gaps=_detailed_gaps_from_axes(gap_axes),
        recommended_focus=(
            f"For {major_label}, the safest next step is to choose one direction that strengthens "
            f"{next((axis.label for axis in gap_axes if axis.severity != 'strong'), 'the current evidence base').lower()} "
            "without making broader claims than the record can support."
        ),
        action_plan=[DiagnosisQuest(title=direction.label, description=direction.summary, priority="high" if index == 0 else "medium") for index, direction in enumerate(directions)],
        risk_level=risk_level,
        diagnosis_summary=_diagnosis_summary(gap_axes=gap_axes, target_university=target_university, target_major=target_major, career_direction=career_direction),
        gap_axes=gap_axes,
        recommended_directions=directions,
        recommended_default_action=_recommended_default_action_from_directions(directions),
    )


def build_grounded_diagnosis_result(
    *,
    project_title: str,
    target_major: str | None,
    target_university: str | None = None,
    career_direction: str | None = None,
    document_count: int,
    full_text: str,
) -> DiagnosisResult:
    _ = document_count
    return _build_guided_diagnosis(project_title=project_title, target_major=target_major, target_university=target_university, career_direction=career_direction, full_text=full_text)


def _hydrate_guided_fields(
    *,
    result: DiagnosisResult,
    project_title: str,
    target_major: str | None,
    target_university: str | None,
    career_direction: str | None,
    full_text: str,
) -> DiagnosisResult:
    if result.gap_axes and result.recommended_directions and result.diagnosis_summary is not None:
        return result
    fallback = build_grounded_diagnosis_result(project_title=project_title, target_major=target_major, target_university=target_university, career_direction=career_direction, document_count=1, full_text=full_text)
    if not result.diagnosis_summary:
        result.diagnosis_summary = fallback.diagnosis_summary
    if not result.gap_axes:
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
    return result


async def evaluate_student_record(
    user_major: str,
    masked_text: str,
    target_university: str | None = None,
    target_major: str | None = None,
    career_direction: str | None = None,
    project_title: str | None = None,
    scope_key: str = "global",
    evidence_keys: list[str] | None = None,
    bypass_cache: bool = False,
) -> DiagnosisResult:
    from polio_api.core.config import get_settings

    system_instruction = _build_diagnosis_system_instruction()
    target_context = (
        f"Target University: {target_university or 'Not set'}\n"
        f"Target Major: {target_major or user_major}\n"
        f"Career Direction: {career_direction or 'Not set'}"
    )
    prompt = _build_diagnosis_prompt(target_context=target_context, user_major=user_major, masked_text=masked_text)

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

    try:
        from polio_api.core.database import SessionLocal

        with SessionLocal() as cache_db:
            cached = fetch_cached_response(cache_db, cache_request)
        if cached:
            cached_result = DiagnosisResult.model_validate_json(cached)
            return _hydrate_guided_fields(result=cached_result, project_title=project_title or "Student record", target_major=target_major or user_major, target_university=target_university, career_direction=career_direction, full_text=masked_text)

        result = await llm.generate_json(
            prompt=prompt,
            response_model=DiagnosisResult,
            system_instruction=system_instruction,
            temperature=0.2,
        )
        result = _hydrate_guided_fields(result=result, project_title=project_title or "Student record", target_major=target_major or user_major, target_university=target_university, career_direction=career_direction, full_text=masked_text)
        with SessionLocal() as cache_db:
            store_cached_response(cache_db, cache_request, response_payload=result.model_dump_json())
        return result
    except Exception as exc:  # noqa: BLE001
        fallback = build_grounded_diagnosis_result(project_title=project_title or "Student record", target_major=target_major or user_major, target_university=target_university, career_direction=career_direction, document_count=1, full_text=masked_text)
        fallback.headline = f"{fallback.headline} AI diagnosis fallback applied after: {exc}"
        return fallback


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
                source_label=source_label or f"Document chunk {chunk.chunk_index + 1}",
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
    return key.replace("_", " ").title()


def _section_purpose(section_key: str, topic: TopicCandidate, direction: RecommendedDirection) -> str:
    purposes = {
        "title": f"Frame the selected topic '{topic.title}' in one grounded line.",
        "context": "Explain the context and why the topic matters now.",
        "analysis": "Interpret what the existing record already supports.",
        "reflection": "Show what the student learned, noticed, or would improve next.",
        "next_steps": "Keep the next move truthful and finishable.",
        "research_question": "State one narrow, answerable inquiry question.",
        "evidence_review": "List the strongest evidence already present in the record.",
        "method": "Describe how the student gathered or interpreted evidence.",
        "limitations": "Name the limit of the current evidence without overstating.",
        "comparison_frame": "Set up the two things that will be compared.",
        "case_a": "Summarize the first side of the comparison.",
        "case_b": "Summarize the second side of the comparison.",
        "implications": "Explain what the comparison changes in the student's understanding.",
        "problem": "State the problem or tension that the proposal addresses.",
        "proposal": "State the realistic proposal or next action.",
        "expected_impact": "Explain what improvement the proposal would create.",
        "feasibility": "Keep the proposal tied to what the student could actually do.",
        "starting_point": "Anchor the story in where the activity started.",
        "turning_points": "Mark the key changes or discoveries along the way.",
        "growth": "Explain what grew in the student's inquiry or understanding.",
        "current_position": "Summarize where the current record stands today.",
        "next_move": "Turn the story into one defensible next move.",
        "agenda": "State the presentation flow in one sentence per slide cluster.",
        "evidence": "Show only the strongest evidence the student can defend.",
        "hook": "Start with one concise, evidence-backed hook.",
        "visual_evidence": "Choose the one visual or table that matters most.",
        "interpretation": "Explain what the evidence means without overselling it.",
        "takeaway": "End with the one conclusion the record can support.",
        "activity_scope": "Clarify what the student actually did and within what boundary.",
        "what_i_did": "List the concrete actions already grounded in the record.",
        "what_i_learned": "Turn the activity into a credible learning takeaway.",
        "record_note": "Write the most submission-friendly summary note.",
    }
    return purposes.get(section_key, f"Advance the {direction.label.lower()} path in a grounded way.")


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
        raise ValueError("Selected direction is not available for this diagnosis.")
    topic = next((item for item in direction.topic_candidates if item.id == topic_id), None)
    if topic is None:
        raise ValueError("Selected topic is not available for this direction.")
    if page_count not in {item.page_count for item in direction.page_count_options}:
        raise ValueError("Selected page count is not available for this direction.")
    if export_format not in {item.format for item in direction.format_recommendations}:
        raise ValueError("Selected export format is not available for this direction.")

    template = get_template(template_id, render_format=RenderFormat(export_format))
    section_limit = min(len(template.section_schema), max(3, page_count + 1))
    section_keys = list(template.section_schema[:section_limit])
    citation_hooks = [citation.source_label for citation in result.citations[:2]]
    sections = [
        GuidedOutlineSection(
            id=section_key,
            title=_humanize_section_key(section_key),
            purpose=_section_purpose(section_key, topic, direction),
            evidence_plan=[*topic.evidence_hooks[:2], *citation_hooks][:3],
            authenticity_guardrail="Do not add claims that are not already grounded in the student record or planned as future work.",
        )
        for section_key in section_keys
    ]
    outline_markdown = "\n\n".join(
        [
            f"# {topic.title}",
            f"## Summary\n{topic.summary}",
            *[
                "\n".join(
                    [
                        f"## {section.title}",
                        section.purpose,
                        "",
                        "Evidence plan:",
                        *[f"- {item}" for item in section.evidence_plan],
                        "",
                        f"Authenticity guardrail: {section.authenticity_guardrail}",
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
    from polio_api.core.config import get_settings

    settings = get_settings()
    if settings.llm_provider == "ollama":
        return settings.ollama_model
    return "gemini-1.5-pro"


def _guided_choice_contract_block() -> str:
    return "\n".join(
        [
            "[Structured Response Contract]",
            "- diagnosis_summary: overview, target_context, reasoning, authenticity_note",
            "- gap_axes: use only conceptual_depth, inquiry_continuity, evidence_density, process_explanation, subject_major_alignment",
            "- recommended_directions: adaptive count from 2 to 5 based on actual diagnosis complexity",
            "- topic_candidates: 2 to 4 realistic, evidence-aware options per direction",
            "- page_count_options: short, finishable options matched to evidence density and direction complexity",
            "- format_recommendations: use only pdf, pptx, hwpx",
            "- template_candidates: use only runtime-provided template ids",
            "- recommended_default_action: pick one coherent default that references ids already present inside recommended_directions",
            "- open-ended user input is optional and should not be treated as the primary interaction path",
        ]
    )


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


def _build_diagnosis_system_instruction() -> str:
    return get_prompt_registry().compose_prompt("diagnosis.grounded-analysis")


def _build_diagnosis_prompt(
    *,
    target_context: str,
    user_major: str,
    masked_text: str,
) -> str:
    return (
        f"[Target Context]\n{target_context}\n\n"
        f"[Primary Major Context]\n{user_major}\n\n"
        f"{_guided_choice_contract_block()}\n\n"
        f"{_template_catalog_prompt_block()}\n\n"
        f"[Masked Student Record]\n{masked_text}"
    )
