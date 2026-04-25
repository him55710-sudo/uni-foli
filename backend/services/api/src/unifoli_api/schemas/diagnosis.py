from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from unifoli_api.services.diagnosis_service import (
    DiagnosisCitation,
    DiagnosisResult,
    GuidedDraftOutline,
    RecommendedDirection,
    TopicCandidate,
)


class DiagnosisRunRequest(BaseModel):
    project_id: str
    interest_universities: list[str] | None = None


class DiagnosisResultPayload(DiagnosisResult):
    pass


class DiagnosisGuidedPlanRequest(BaseModel):
    direction_id: str = Field(min_length=1, max_length=80)
    topic_id: str = Field(min_length=1, max_length=80)
    page_count: int = Field(ge=5, le=20)
    export_format: Literal["pdf", "pptx", "hwpx"]
    template_id: str = Field(min_length=1, max_length=80)
    include_provenance_appendix: bool = False
    hide_internal_provenance_on_final_export: bool = True
    open_text_note: str | None = Field(default=None, max_length=1000)


class DiagnosisGuidedPlanResponse(BaseModel):
    diagnosis_run_id: str
    project_id: str
    direction: RecommendedDirection
    topic: TopicCandidate
    outline: GuidedDraftOutline


class DiagnosisPolicyFlagRead(BaseModel):
    id: str
    code: str
    severity: str
    detail: str
    matched_text: str
    match_count: int
    status: str
    created_at: datetime | None = None


class DiagnosisRunResponse(BaseModel):
    id: str
    project_id: str
    status: str
    status_message: str | None = None
    result_payload: DiagnosisResultPayload | None = None
    error_message: str | None = None
    review_required: bool = False
    policy_flags: list[DiagnosisPolicyFlagRead] = Field(default_factory=list)
    citations: list[DiagnosisCitation] = Field(default_factory=list)
    response_trace_id: str | None = None
    async_job_id: str | None = None
    async_job_status: str | None = None
    report_status: str | None = None
    report_async_job_id: str | None = None
    report_async_job_status: str | None = None
    report_artifact_id: str | None = None
    report_error_message: str | None = None


DiagnosisReportMode = Literal["basic", "premium", "consultant", "compact", "premium_10p"]
DiagnosisReportStatus = Literal["READY", "FAILED"]


class ConsultantDiagnosisEvidenceItem(BaseModel):
    source_label: str
    page_number: int | None = None
    excerpt: str
    relevance_score: float = Field(ge=0.0)
    support_status: Literal["verified", "probable", "needs_verification"] = "verified"


class ConsultantDiagnosisScoreBlock(BaseModel):
    key: str
    label: str
    score: int = Field(ge=0, le=100)
    band: str
    interpretation: str
    uncertainty_note: str | None = None
    evidence_summary: str | None = None
    missing_evidence: str | None = None
    next_best_action: str | None = None


class ConsultantDiagnosisScoreGroup(BaseModel):
    group: Literal["student_evaluation", "system_quality"]
    title: str
    blocks: list[ConsultantDiagnosisScoreBlock] = Field(default_factory=list)
    gating_status: Literal["ok", "reanalysis_required", "blocked"] | None = None
    note: str | None = None


class ConsultantDiagnosisRoadmapItem(BaseModel):
    horizon: Literal["1_month", "3_months", "6_months"]
    title: str
    actions: list[str] = Field(default_factory=list)
    success_signals: list[str] = Field(default_factory=list)
    caution_notes: list[str] = Field(default_factory=list)


class ConsultantSubjectMetricScores(BaseModel):
    academic_concept_density: int = Field(ge=0, le=100)
    inquiry_process: int = Field(ge=0, le=100)
    student_agency: int = Field(ge=0, le=100)
    major_connection: int = Field(ge=0, le=100)
    expansion_potential: int = Field(ge=0, le=100)
    differentiation: int = Field(ge=0, le=100)
    interview_defense: int = Field(ge=0, le=100)


class ConsultantSubjectSpecialtyAnalysis(BaseModel):
    subject: str
    core_record_summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    score: int = Field(ge=0, le=100)
    metric_scores: ConsultantSubjectMetricScores
    level: Literal["매우 강함", "강함", "보통", "약함", "위험"]
    admissions_meaning: str
    major_connection: str
    sentence_to_improve: str
    recommended_follow_up: str
    interview_question: str
    evidence_refs: list[str] = Field(default_factory=list)


class ConsultantRecordNetworkNode(BaseModel):
    id: str
    label: str
    category: str
    evidence_summary: str
    weight: int = Field(ge=1, le=5)


class ConsultantRecordNetworkEdge(BaseModel):
    source: str
    target: str
    label: str
    strength: Literal["Strong", "Moderate", "Weak", "Artificial"]
    rationale: str


class ConsultantRecordNetwork(BaseModel):
    central_theme: str
    evaluation: dict[str, str] = Field(default_factory=dict)
    nodes: list[ConsultantRecordNetworkNode] = Field(default_factory=list)
    edges: list[ConsultantRecordNetworkEdge] = Field(default_factory=list)
    matrix: list[dict[str, Any]] = Field(default_factory=list)


class ConsultantResearchTopicRecommendation(BaseModel):
    title: str
    classification: Literal["강력 추천", "확장 가능 주제"]
    connected_evidence: str
    inquiry_question: str
    subject_concepts: list[str] = Field(default_factory=list)
    method: str
    expected_output: str
    record_sentence: str
    interview_use: str
    difficulty: Literal["상", "중", "하"]
    priority: int = Field(ge=1, le=12)


class ConsultantInterviewQuestionFrame(BaseModel):
    category: Literal["전공 적합성", "탐구 과정 검증", "약점 방어"]
    question: str
    intent: str
    answer_frame: str
    connected_evidence: str
    good_direction: str
    avoid: str


class ConsultantBeforeAfterRewrite(BaseModel):
    original_summary: str
    problem: str
    improved_sentence: str
    why_better: str
    exaggeration_risk: str


class ConsultantGradeStoryAnalysis(BaseModel):
    grade_label: str
    stage_role: str
    core_activities: list[str] = Field(default_factory=list)
    visible_competencies: list[str] = Field(default_factory=list)
    weak_connections: list[str] = Field(default_factory=list)
    next_flow: str
    section_linkage: str
    guidance_tone: str


class ConsultantReportQualityGate(BaseModel):
    key: str
    label: str
    passed: bool
    message: str


class ConsultantDiagnosisSection(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    body_markdown: str
    evidence_items: list[ConsultantDiagnosisEvidenceItem] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    additional_verification_needed: list[str] = Field(default_factory=list)


class ConsultantDiagnosisReport(BaseModel):
    diagnosis_run_id: str
    project_id: str
    report_mode: DiagnosisReportMode
    template_id: str
    title: str
    subtitle: str
    student_target_context: str
    generated_at: datetime
    report_mode_label: str | None = None
    expected_page_range: str | None = None
    actual_page_count: int | None = None
    score_blocks: list[ConsultantDiagnosisScoreBlock] = Field(default_factory=list)
    score_groups: list[ConsultantDiagnosisScoreGroup] = Field(default_factory=list)
    sections: list[ConsultantDiagnosisSection] = Field(default_factory=list)
    roadmap: list[ConsultantDiagnosisRoadmapItem] = Field(default_factory=list)
    subject_specialty_analyses: list[ConsultantSubjectSpecialtyAnalysis] = Field(default_factory=list)
    record_network: ConsultantRecordNetwork | None = None
    research_topics: list[ConsultantResearchTopicRecommendation] = Field(default_factory=list)
    interview_questions: list[ConsultantInterviewQuestionFrame] = Field(default_factory=list)
    before_after_examples: list[ConsultantBeforeAfterRewrite] = Field(default_factory=list)
    grade_story_analyses: list[ConsultantGradeStoryAnalysis] = Field(default_factory=list)
    quality_gates: list[ConsultantReportQualityGate] = Field(default_factory=list)
    citations: list[ConsultantDiagnosisEvidenceItem] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    final_consultant_memo: str
    appendix_notes: list[str] = Field(default_factory=list)
    diagnosis_intelligence: dict[str, Any] = Field(default_factory=dict)
    render_hints: dict[str, Any] = Field(default_factory=dict)


class DiagnosisReportCreateRequest(BaseModel):
    report_mode: DiagnosisReportMode = "premium"
    template_id: str | None = Field(default=None, min_length=1, max_length=80)
    include_appendix: bool = True
    include_citations: bool = True
    force_regenerate: bool = False


class ConsultantDiagnosisArtifactResponse(BaseModel):
    id: str
    diagnosis_run_id: str
    project_id: str
    report_mode: DiagnosisReportMode
    template_id: str
    export_format: Literal["pdf"]
    include_appendix: bool
    include_citations: bool
    status: DiagnosisReportStatus
    version: int
    storage_provider: str | None = None
    storage_key: str | None = None
    generated_file_path: str | None = None
    download_url: str | None = None
    execution_metadata: dict[str, Any] | None = None
    error_message: str | None = None
    payload: ConsultantDiagnosisReport | None = None
    created_at: datetime
    updated_at: datetime
