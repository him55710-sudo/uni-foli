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


DiagnosisReportMode = Literal["compact", "premium_10p"]
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
    score_blocks: list[ConsultantDiagnosisScoreBlock] = Field(default_factory=list)
    score_groups: list[ConsultantDiagnosisScoreGroup] = Field(default_factory=list)
    sections: list[ConsultantDiagnosisSection] = Field(default_factory=list)
    roadmap: list[ConsultantDiagnosisRoadmapItem] = Field(default_factory=list)
    citations: list[ConsultantDiagnosisEvidenceItem] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    final_consultant_memo: str
    appendix_notes: list[str] = Field(default_factory=list)
    diagnosis_intelligence: dict[str, Any] = Field(default_factory=dict)
    render_hints: dict[str, Any] = Field(default_factory=dict)


class DiagnosisReportCreateRequest(BaseModel):
    report_mode: DiagnosisReportMode = "premium_10p"
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
