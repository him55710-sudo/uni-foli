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
from polio_api.services.llm_cache_service import CacheRequest, fetch_cached_response, store_cached_response
from polio_ingest.masking import MaskingPipeline
from polio_domain.enums import EvidenceProvenance


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

class DiagnosisResult(BaseModel):
    headline: str = Field(description="Short diagnosis summary headline")
    strengths: list[str] = Field(description="Current grounded strengths in the record")
    gaps: list[str] = Field(description="Visible evidence or inquiry gaps to close next")
    detailed_gaps: list[DiagnosisGap] = Field(default_factory=list, description="Structured gap analysis")
    recommended_focus: str = Field(description="Most important next focus")
    action_plan: list[DiagnosisQuest] = Field(default_factory=list, description="Concrete next quests")
    risk_level: Literal["safe", "warning", "danger"] = Field(description="Risk tier")
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
        re.compile(r"(?:학번|수험번호|student\s*id)\s*[:#]?\s*[A-Za-z0-9-]{4,20}", re.IGNORECASE),
    ),
    (
        "fabrication_request",
        "critical",
        "Input text appears to request fabricated or false admissions content.",
        re.compile(
            r"(허위|조작|없는\s+(?:활동|경험|실험)|사실이\s+아닌|꾸며|대필|fabricat(?:e|ed|ion)|make\s+up)",
            re.IGNORECASE,
        ),
    ),
)


def build_grounded_diagnosis_result(
    *,
    project_title: str,
    target_major: str | None,
    document_count: int,
    full_text: str,
) -> DiagnosisResult:
    major_label = target_major or "the selected major"
    lowered = full_text.lower()

    has_measurement = any(token in lowered for token in ["measure", "experiment", "data", "analysis", "survey"])
    has_comparison = any(token in lowered for token in ["compare", "difference", "before", "after", "trend"])
    has_reflection = any(token in lowered for token in ["reflect", "limit", "improve", "lesson", "feedback"])

    strengths: list[str] = []
    gaps: list[str] = []

    if document_count >= 1 and len(full_text.split()) >= 120:
        strengths.append("The uploaded record already contains enough grounded text to build the next activity.")
    else:
        gaps.append("The current record is still thin, so the next quest should create clearer evidence before expanding claims.")

    if has_measurement or has_comparison:
        strengths.append("The record shows an inquiry trace through measuring, comparing, or analyzing.")
    else:
        gaps.append("The record does not yet show a visible inquiry process such as comparison, measurement, or analysis.")

    if has_reflection:
        strengths.append("The student already reflects on limits or improvements, which helps later drafting.")
    else:
        gaps.append("Method limits and next-step reflection are still weak in the current record.")

    if not strengths:
        strengths.append("The record has a usable starting point, but it needs a more explicit evidence trail.")
    if not gaps:
        gaps.append("Turn the strongest topic into a deeper follow-up activity with clearer evidence and reflection.")

    risk_level: Literal["safe", "warning", "danger"]
    if len(gaps) >= 3:
        risk_level = "danger"
    elif len(gaps) == 2:
        risk_level = "warning"
    else:
        risk_level = "safe"

    recommended_focus = (
        f"{major_label} inquiry for {project_title} that adds one comparison, one explicit method limit, "
        "and one concrete reflection tied to the current record."
    )
    headline = (
        f"For {major_label}, the record is {'grounded enough' if risk_level == 'safe' else 'not finished yet'}; "
        "the next step should produce clearer evidence, not broader claims."
    )

    return DiagnosisResult(
        headline=headline,
        strengths=strengths[:3],
        gaps=gaps[:4],
        risk_level=risk_level,
        recommended_focus=recommended_focus,
    )


async def evaluate_student_record(
    user_major: str,
    masked_text: str,
    target_university: str | None = None,
    target_major: str | None = None,
    scope_key: str = "global",
    evidence_keys: list[str] | None = None,
    bypass_cache: bool = False,
) -> DiagnosisResult:
    from polio_api.core.config import get_settings

    system_instruction = (
        "You are 'Uni Folia', a rigorous admissions-oriented school record analyst and mentor. "
        "Your expertise is strictly limited to high school student records (생기부), university admissions, "
        "and academic portfolio development. If a user asks about topics unrelated to these areas, "
        "you MUST politely decline saying exactly: '죄송합니다. 저는 학업에 관련된 대화만 진행할 수 있습니다.' "
        "Read the student's grounded record and explain the real gaps between the current evidence "
        "and the stated target major. Do not predict admission. Focus on what is missing and what "
        "the next action should be. Output all text fields in Korean (한국어)."
    )
    target_context = (
        f"Target University: {target_university or 'Not set'}\n"
        f"Target Major: {target_major or user_major}"
    )

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
            "temperature": 0.2,
        },
    )

    try:
        prompt = f"{target_context}\nPrimary Major Context: {user_major}\n\n[Masked Record]\n{masked_text}"
        from polio_api.core.database import SessionLocal

        with SessionLocal() as cache_db:
            cached = fetch_cached_response(cache_db, cache_request)
        if cached:
            return DiagnosisResult.model_validate_json(cached)

        result = await llm.generate_json(
            prompt=prompt,
            response_model=DiagnosisResult,
            system_instruction=system_instruction,
            temperature=0.2,
        )
        with SessionLocal() as cache_db:
            store_cached_response(
                cache_db,
                cache_request,
                response_payload=result.model_dump_json(),
            )
        return result
    except Exception as exc:  # noqa: BLE001
        return DiagnosisResult(
            headline=f"Diagnosis request failed: {exc}",
            strengths=[],
            gaps=["The AI diagnosis call failed, so use the grounded fallback diagnosis instead."],
            risk_level="warning",
            recommended_focus="Retry the diagnosis or continue with the grounded fallback blueprint.",
        )


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


def _tokenize_for_overlap(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text or "")}


def _trim_excerpt(text: str, *, limit: int = 240) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def build_diagnosis_citations(
    *,
    chunks: list[DocumentChunk],
    result: DiagnosisResult,
    limit: int = 3,
) -> list[DiagnosisCitation]:
    if not chunks:
        return []

    query_terms = _tokenize_for_overlap(
        " ".join([result.headline, *result.strengths, *result.gaps, result.recommended_focus])
    )
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
        source_label = None
        if chunk.document is not None:
            source_label = chunk.document.original_filename
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
    response_excerpt = _trim_excerpt(
        " ".join([result.headline, *result.strengths, *result.gaps, result.recommended_focus]),
        limit=1600,
    )

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
