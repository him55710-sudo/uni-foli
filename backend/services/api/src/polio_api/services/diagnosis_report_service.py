from __future__ import annotations

import json
import logging
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.core.config import get_settings
from polio_api.core.llm import GeminiClient, LLMRequestError, OllamaClient, get_llm_client, get_llm_temperature
from polio_api.core.security import sanitize_public_error
from polio_api.db.models.diagnosis_report_artifact import DiagnosisReportArtifact
from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.db.models.project import Project
from polio_api.schemas.diagnosis import (
    ConsultantDiagnosisArtifactResponse,
    ConsultantDiagnosisEvidenceItem,
    ConsultantDiagnosisReport,
    ConsultantDiagnosisRoadmapItem,
    ConsultantDiagnosisScoreBlock,
    ConsultantDiagnosisSection,
    DiagnosisReportMode,
    DiagnosisResultPayload,
)
from polio_api.services.document_service import list_documents_for_project
from polio_api.services.prompt_registry import get_prompt_registry
from polio_domain.enums import RenderFormat
from polio_render.diagnosis_report_design_contract import get_diagnosis_report_design_contract
from polio_render.diagnosis_report_pdf_renderer import render_consultant_diagnosis_pdf
from polio_render.template_registry import get_template
from polio_shared.storage import get_storage_provider, get_storage_provider_name


logger = logging.getLogger("polio.api.diagnosis_report")

_DEFAULT_TEMPLATE_BY_MODE: dict[str, str] = {
    "compact": "consultant_diagnosis_compact",
    "premium_10p": "consultant_diagnosis_premium_10p",
}
_REPORT_FAILURE_FALLBACK = "Diagnosis report generation failed. Retry after checking the project evidence."


class _ConsultantNarrativePayload(BaseModel):
    executive_summary: str = Field(min_length=1, max_length=1600)
    current_record_status_brief: str | None = Field(default=None, max_length=900)
    strengths_brief: str | None = Field(default=None, max_length=900)
    weaknesses_risks_brief: str | None = Field(default=None, max_length=900)
    major_fit_brief: str | None = Field(default=None, max_length=900)
    section_diagnosis_brief: str | None = Field(default=None, max_length=900)
    topic_strategy_brief: str | None = Field(default=None, max_length=900)
    roadmap_bridge: str | None = Field(default=None, max_length=900)
    uncertainty_bridge: str | None = Field(default=None, max_length=900)
    final_consultant_memo: str = Field(min_length=1, max_length=1400)


class _NarrativeGenerationResult(BaseModel):
    narrative: _ConsultantNarrativePayload
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


_PREMIUM_SECTION_ORDER: tuple[str, ...] = (
    "cover_context",
    "executive_summary",
    "current_record_status",
    "evaluation_axis",
    "strength_analysis",
    "weakness_risk",
    "major_fit",
    "section_level_diagnosis",
    "roadmap",
    "topic_strategy",
    "final_memo",
    "appendix",
)

_COMPACT_SECTION_ORDER: tuple[str, ...] = (
    "cover_context",
    "executive_summary",
    "current_record_status",
    "strength_analysis",
    "weakness_risk",
    "roadmap",
    "final_memo",
)


def resolve_consultant_report_template_id(
    *,
    report_mode: DiagnosisReportMode,
    template_id: str | None,
) -> str:
    resolved = (template_id or _DEFAULT_TEMPLATE_BY_MODE[report_mode]).strip()
    # Validate against the registry so frontend always receives a supported template id.
    get_template(resolved, render_format=RenderFormat.PDF)
    return resolved


def get_latest_report_artifact_for_run(
    db: Session,
    *,
    diagnosis_run_id: str,
    report_mode: DiagnosisReportMode | None = None,
) -> DiagnosisReportArtifact | None:
    stmt = select(DiagnosisReportArtifact).where(DiagnosisReportArtifact.diagnosis_run_id == diagnosis_run_id)
    if report_mode is not None:
        stmt = stmt.where(DiagnosisReportArtifact.report_mode == report_mode)
    stmt = stmt.order_by(DiagnosisReportArtifact.version.desc(), DiagnosisReportArtifact.created_at.desc()).limit(1)
    return db.scalar(stmt)


def get_report_artifact_by_id(
    db: Session,
    *,
    diagnosis_run_id: str,
    artifact_id: str,
) -> DiagnosisReportArtifact | None:
    stmt = (
        select(DiagnosisReportArtifact)
        .where(
            DiagnosisReportArtifact.id == artifact_id,
            DiagnosisReportArtifact.diagnosis_run_id == diagnosis_run_id,
        )
        .limit(1)
    )
    return db.scalar(stmt)


def report_artifact_file_path(artifact: DiagnosisReportArtifact) -> Path | str | None:
    if not artifact.generated_file_path:
        return None
    return artifact.generated_file_path


def report_artifact_storage_key(artifact: DiagnosisReportArtifact) -> str | None:
    value = (artifact.storage_key or "").strip()
    if value:
        return value
    legacy = (artifact.generated_file_path or "").strip()
    if not legacy:
        return None
    legacy_path = Path(legacy)
    if legacy_path.is_absolute():
        return None
    return legacy


def report_artifact_execution_metadata(artifact: DiagnosisReportArtifact) -> dict[str, Any] | None:
    raw = (artifact.execution_metadata_json or "").strip()
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(decoded, dict):
        return decoded
    return None


def load_report_artifact_pdf_bytes(artifact: DiagnosisReportArtifact) -> bytes | None:
    key = report_artifact_storage_key(artifact)
    if not key:
        return None

    storage = get_storage_provider(get_settings())
    if not storage.exists(key):
        return None
    try:
        return storage.retrieve(key)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to retrieve diagnosis report artifact from storage key=%s", key)
        return None


def build_report_artifact_response(
    *,
    artifact: DiagnosisReportArtifact,
    include_payload: bool = True,
) -> ConsultantDiagnosisArtifactResponse:
    settings = get_settings()
    payload = None
    if include_payload and artifact.report_payload_json:
        try:
            payload = ConsultantDiagnosisReport.model_validate_json(artifact.report_payload_json)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to decode diagnosis report payload artifact=%s: %s", artifact.id, exc)

    download_url = None
    if report_artifact_storage_key(artifact):
        download_url = (
            f"{settings.api_prefix}/diagnosis/{artifact.diagnosis_run_id}/report.pdf"
            f"?artifact_id={artifact.id}"
        )
    report_mode = artifact.report_mode if artifact.report_mode in {"compact", "premium_10p"} else "premium_10p"
    report_status = artifact.status if artifact.status in {"READY", "FAILED"} else "FAILED"

    return ConsultantDiagnosisArtifactResponse(
        id=artifact.id,
        diagnosis_run_id=artifact.diagnosis_run_id,
        project_id=artifact.project_id,
        report_mode=report_mode,  # type: ignore[arg-type]
        template_id=artifact.template_id
        or _DEFAULT_TEMPLATE_BY_MODE.get(report_mode, "consultant_diagnosis_premium_10p"),
        export_format="pdf",
        include_appendix=bool(artifact.include_appendix),
        include_citations=bool(artifact.include_citations),
        status=report_status,  # type: ignore[arg-type]
        version=artifact.version,
        storage_provider=artifact.storage_provider,
        storage_key=report_artifact_storage_key(artifact),
        generated_file_path=artifact.generated_file_path,
        download_url=download_url,
        execution_metadata=report_artifact_execution_metadata(artifact),
        error_message=artifact.error_message,
        payload=payload,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


async def generate_consultant_report_artifact(
    db: Session,
    *,
    run: DiagnosisRun,
    project: Project,
    report_mode: DiagnosisReportMode,
    template_id: str | None,
    include_appendix: bool,
    include_citations: bool,
    force_regenerate: bool,
) -> DiagnosisReportArtifact:
    settings = get_settings()
    storage = get_storage_provider(settings)
    resolved_template_id = resolve_consultant_report_template_id(
        report_mode=report_mode,
        template_id=template_id,
    )
    latest_for_mode = get_latest_report_artifact_for_run(
        db,
        diagnosis_run_id=run.id,
        report_mode=report_mode,
    )

    if not force_regenerate and latest_for_mode is not None:
        existing_key = report_artifact_storage_key(latest_for_mode)
        if (
            latest_for_mode.status == "READY"
            and latest_for_mode.template_id == resolved_template_id
            and bool(latest_for_mode.include_appendix) == include_appendix
            and bool(latest_for_mode.include_citations) == include_citations
            and existing_key
            and storage.exists(existing_key)
        ):
            return latest_for_mode

    if not run.result_payload:
        raise ValueError("Diagnosis is not complete yet.")

    result = DiagnosisResultPayload.model_validate_json(run.result_payload)
    documents = list_documents_for_project(db, project.id)
    latest_version = latest_for_mode.version if latest_for_mode is not None else 0
    next_version = latest_version + 1
    started_at = time.perf_counter()

    try:
        report = await build_consultant_report_payload(
            run=run,
            project=project,
            result=result,
            report_mode=report_mode,
            template_id=resolved_template_id,
            include_appendix=include_appendix,
            include_citations=include_citations,
            documents=documents,
        )
        report_json = report.model_dump(mode="json")
        report_json_str = report.model_dump_json()
        execution_metadata_raw = report_json.get("render_hints", {}).get("execution_metadata")
        execution_metadata = execution_metadata_raw if isinstance(execution_metadata_raw, dict) else {}

        stored_path = (
            f"exports/diagnosis_reports/{project.id}/{run.id}/"
            f"consultant-diagnosis-{report_mode}-v{next_version}.pdf"
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            render_consultant_diagnosis_pdf(
                report_payload=report_json,
                output_path=tmp_path,
                report_mode=report_mode,
                template_id=resolved_template_id,
                include_appendix=include_appendix,
                include_citations=include_citations,
            )
            with open(tmp_path, "rb") as f:
                storage.store(f.read(), stored_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        duration_ms = int(max(0.0, (time.perf_counter() - started_at) * 1000.0))
        execution_metadata = {
            **execution_metadata,
            "storage_provider": get_storage_provider_name(storage),
            "storage_key": stored_path,
            "processing_duration_ms": duration_ms,
        }

        artifact = DiagnosisReportArtifact(
            diagnosis_run_id=run.id,
            project_id=project.id,
            report_mode=report_mode,
            template_id=resolved_template_id,
            export_format="pdf",
            include_appendix=include_appendix,
            include_citations=include_citations,
            status="READY",
            version=next_version,
            report_payload_json=report_json_str,
            storage_provider=get_storage_provider_name(storage),
            storage_key=stored_path,
            generated_file_path=stored_path,
            execution_metadata_json=json.dumps(execution_metadata, ensure_ascii=False),
            error_message=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Consultant diagnosis report generation failed for run=%s", run.id)
        duration_ms = int(max(0.0, (time.perf_counter() - started_at) * 1000.0))
        execution_metadata = {
            "requested_llm_provider": (settings.llm_provider or "gemini").strip().lower(),
            "requested_llm_model": (
                settings.ollama_render_model
                or settings.ollama_model
                or "gemma4"
            ) if (settings.llm_provider or "").strip().lower() == "ollama" else "gemini-1.5-pro",
            "actual_llm_provider": "deterministic_fallback",
            "actual_llm_model": "deterministic_fallback",
            "llm_profile_used": "render",
            "fallback_used": True,
            "fallback_reason": sanitize_public_error(str(exc), fallback=_REPORT_FAILURE_FALLBACK),
            "processing_duration_ms": duration_ms,
        }
        artifact = DiagnosisReportArtifact(
            diagnosis_run_id=run.id,
            project_id=project.id,
            report_mode=report_mode,
            template_id=resolved_template_id,
            export_format="pdf",
            include_appendix=include_appendix,
            include_citations=include_citations,
            status="FAILED",
            version=next_version,
            report_payload_json=_build_failed_report_payload(
                run=run,
                project=project,
                report_mode=report_mode,
                template_id=resolved_template_id,
            ),
            storage_provider=get_storage_provider_name(storage),
            storage_key=None,
            generated_file_path=None,
            execution_metadata_json=json.dumps(execution_metadata, ensure_ascii=False),
            error_message=sanitize_public_error(str(exc), fallback=_REPORT_FAILURE_FALLBACK),
        )

    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


async def build_consultant_report_payload(
    *,
    run: DiagnosisRun,
    project: Project,
    result: DiagnosisResultPayload,
    report_mode: DiagnosisReportMode,
    template_id: str,
    include_appendix: bool,
    include_citations: bool,
    documents: list[Any],
) -> ConsultantDiagnosisReport:
    target_context = _build_target_context(project=project, result=result, documents=documents)
    evidence_items = _build_evidence_items(result)
    score_blocks = _build_score_blocks(result=result)
    document_structure = _collect_student_record_structure(documents)
    uncertainty_notes = _build_uncertainty_notes(
        result=result,
        document_structure=document_structure,
        evidence_items=evidence_items,
    )
    roadmap = _build_roadmap(result=result, uncertainty_notes=uncertainty_notes)
    narratives_result_raw = await _generate_narratives(
        project=project,
        result=result,
        document_structure=document_structure,
        uncertainty_notes=uncertainty_notes,
    )
    if isinstance(narratives_result_raw, _NarrativeGenerationResult):
        narratives_result = narratives_result_raw
    else:
        narratives_result = _NarrativeGenerationResult(
            narrative=_ConsultantNarrativePayload.model_validate(narratives_result_raw),
            execution_metadata={
                "requested_llm_provider": None,
                "requested_llm_model": None,
                "actual_llm_provider": None,
                "actual_llm_model": None,
                "llm_profile_used": "render",
                "fallback_used": None,
                "fallback_reason": None,
            },
        )
    narratives = _enforce_narrative_contract(
        narratives_result.narrative,
        result=result,
        document_structure=document_structure,
        uncertainty_notes=uncertainty_notes,
    )
    template = get_template(template_id, render_format=RenderFormat.PDF)
    design_contract = get_diagnosis_report_design_contract(
        report_mode=report_mode,
        template_id=template_id,
        template_section_schema=template.section_schema,
    )

    sections = _build_sections(
        result=result,
        report_mode=report_mode,
        target_context=target_context,
        evidence_items=evidence_items,
        score_blocks=score_blocks,
        document_structure=document_structure,
        roadmap=roadmap,
        narratives=narratives,
        uncertainty_notes=uncertainty_notes,
    )
    sections = _enforce_section_architecture(sections, report_mode=report_mode)

    appendix_notes: list[str] = []
    if include_appendix:
        appendix_notes.extend(_build_appendix_notes(documents, document_structure))
    if include_citations:
        appendix_notes.append("인용 부록에는 주장-근거 연결 검증을 위한 출처 라인이 포함됩니다.")

    report_payload = ConsultantDiagnosisReport(
        diagnosis_run_id=run.id,
        project_id=project.id,
        report_mode=report_mode,
        template_id=template_id,
        title=f"{project.title} 전문 컨설턴트 진단서",
        subtitle="학생부 근거 기반 진단 · 리스크 명시 · 실행 로드맵",
        student_target_context=target_context,
        generated_at=datetime.now(timezone.utc),
        score_blocks=score_blocks,
        sections=sections,
        roadmap=roadmap,
        citations=evidence_items if include_citations else [],
        uncertainty_notes=uncertainty_notes,
        final_consultant_memo=narratives.final_consultant_memo,
        appendix_notes=appendix_notes,
        render_hints={
            "a4": True,
            "minimum_pages": 10 if report_mode == "premium_10p" else 5,
            "visual_tone": "consultant_premium",
            "include_appendix": include_appendix,
            "include_citations": include_citations,
            "section_order": list(_PREMIUM_SECTION_ORDER if report_mode == "premium_10p" else _COMPACT_SECTION_ORDER),
            "design_contract": design_contract,
            "execution_metadata": {
                **narratives_result.execution_metadata,
                "diagnosis_backbone_requested_llm_provider": result.requested_llm_provider,
                "diagnosis_backbone_requested_llm_model": result.requested_llm_model,
                "diagnosis_backbone_actual_llm_provider": result.actual_llm_provider,
                "diagnosis_backbone_actual_llm_model": result.actual_llm_model,
                "diagnosis_backbone_fallback_used": result.fallback_used,
                "diagnosis_backbone_fallback_reason": result.fallback_reason,
            },
        },
    )
    return report_payload


def _build_target_context(*, project: Project, result: DiagnosisResultPayload, documents: list[Any]) -> str:
    target_university = project.target_university or "미설정"
    target_major = project.target_major or "미설정"
    diagnosis_target = result.diagnosis_summary.target_context if result.diagnosis_summary else None
    context_bits = [
        f"프로젝트: {project.title}",
        f"목표 대학: {target_university}",
        f"목표 전공: {target_major}",
        f"분석 문서 수: {len(documents)}",
    ]
    if diagnosis_target:
        context_bits.append(f"진단 타깃 메모: {diagnosis_target}")
    return " | ".join(context_bits)


def _build_score_blocks(*, result: DiagnosisResultPayload) -> list[ConsultantDiagnosisScoreBlock]:
    blocks: list[ConsultantDiagnosisScoreBlock] = []
    for axis in result.admission_axes or []:
        blocks.append(
            ConsultantDiagnosisScoreBlock(
                key=axis.key,
                label=axis.label,
                score=int(axis.score),
                band=axis.band,
                interpretation=axis.rationale,
                uncertainty_note="해당 점수는 입력 문서 기반 상대평가이며 절대 합격예측이 아님.",
            )
        )

    if result.document_quality:
        reliability_score = int(round(max(0.0, min(1.0, result.document_quality.parse_reliability_score)) * 100))
        blocks.append(
            ConsultantDiagnosisScoreBlock(
                key="parse_reliability",
                label="파싱 신뢰도",
                score=reliability_score,
                band=result.document_quality.parse_reliability_band,
                interpretation=result.document_quality.summary,
                uncertainty_note="문서 추출 품질이 낮으면 진단 정확도도 함께 낮아질 수 있음.",
            )
        )
        evidence_density_score = int(round(max(0.0, min(1.0, result.document_quality.evidence_density)) * 100))
        blocks.append(
            ConsultantDiagnosisScoreBlock(
                key="evidence_density",
                label="근거 밀도",
                score=evidence_density_score,
                band="high" if evidence_density_score >= 70 else "mid" if evidence_density_score >= 45 else "low",
                interpretation="근거 밀도는 주장 대비 근거 앵커의 충실도를 의미합니다.",
                uncertainty_note="밀도가 낮은 문장은 반드시 '추가 확인 필요'로 표기해야 함.",
            )
        )

    if not blocks:
        blocks.append(
            ConsultantDiagnosisScoreBlock(
                key="fallback",
                label="진단 요약 점수",
                score=52,
                band="watch",
                interpretation="구조화 점수 축이 부족하여 보수적 기본 점수를 사용했습니다.",
                uncertainty_note="추가 문서 근거 확보 후 재생성 권장.",
            )
        )
    return blocks


def _build_evidence_items(result: DiagnosisResultPayload) -> list[ConsultantDiagnosisEvidenceItem]:
    evidence_items: list[ConsultantDiagnosisEvidenceItem] = []
    for citation in result.citations or []:
        score = float(citation.relevance_score)
        if score >= 1.6:
            support_status = "verified"
        elif score >= 0.8:
            support_status = "probable"
        else:
            support_status = "needs_verification"
        evidence_items.append(
            ConsultantDiagnosisEvidenceItem(
                source_label=citation.source_label,
                page_number=citation.page_number,
                excerpt=citation.excerpt,
                relevance_score=round(score, 3),
                support_status=support_status,
            )
        )
    return evidence_items[:40]


def _collect_student_record_structure(documents: list[Any]) -> dict[str, Any]:
    section_density: dict[str, float] = {}
    weak_sections: list[str] = []
    timeline_signals: list[str] = []
    activity_clusters: list[str] = []
    alignment_signals: list[str] = []
    continuity_signals: list[str] = []
    process_signals: list[str] = []
    uncertain_items: list[str] = []

    for document in documents:
        metadata = getattr(document, "parse_metadata", None)
        if not isinstance(metadata, dict):
            continue
        canonical = metadata.get("student_record_canonical")
        if isinstance(canonical, dict):
            timeline_signals.extend(_extract_canonical_values(canonical.get("timeline_signals"), "signal"))
            alignment_signals.extend(_extract_canonical_values(canonical.get("major_alignment_hints"), "hint"))
            weak_sections.extend(_extract_canonical_values(canonical.get("weak_or_missing_sections"), "section"))
            uncertain_items.extend(_extract_canonical_values(canonical.get("uncertainties"), "message"))
            activity_clusters.extend(_extract_canonical_values(canonical.get("extracurricular"), "label"))
            process_signals.extend(_extract_canonical_values(canonical.get("subject_special_notes"), "label"))
            career_signals = _extract_canonical_values(canonical.get("career_signals"), "label")
            continuity_signals.extend(career_signals)

            section_classification = canonical.get("section_classification")
            if isinstance(section_classification, dict):
                for legacy_key, canonical_key in (
                    ("교과학습발달상황", "grades_subjects"),
                    ("세특", "subject_special_notes"),
                    ("창체", "extracurricular"),
                    ("진로", "career_signals"),
                    ("독서", "reading_activity"),
                    ("행동특성", "behavior_opinion"),
                ):
                    payload = section_classification.get(canonical_key)
                    if not isinstance(payload, dict):
                        continue
                    try:
                        normalized = max(0.0, min(1.0, float(payload.get("density") or 0.0)))
                    except (TypeError, ValueError):
                        continue
                    section_density[legacy_key] = max(section_density.get(legacy_key, 0.0), normalized)
        structure_candidates = _extract_structure_candidates(metadata)

        for structure in structure_candidates:
            for key, value in (structure.get("section_density") or {}).items():
                try:
                    normalized = max(0.0, min(1.0, float(value)))
                except (TypeError, ValueError):
                    continue
                section_density[str(key)] = max(section_density.get(str(key), 0.0), normalized)

            weak_sections.extend([str(item).strip() for item in structure.get("weak_sections", []) if str(item).strip()])
            timeline_signals.extend([str(item).strip() for item in structure.get("timeline_signals", []) if str(item).strip()])
            activity_clusters.extend([str(item).strip() for item in structure.get("activity_clusters", []) if str(item).strip()])
            alignment_signals.extend([str(item).strip() for item in structure.get("subject_major_alignment_signals", []) if str(item).strip()])
            continuity_signals.extend([str(item).strip() for item in structure.get("continuity_signals", []) if str(item).strip()])
            process_signals.extend([str(item).strip() for item in structure.get("process_reflection_signals", []) if str(item).strip()])
            uncertain_items.extend([str(item).strip() for item in structure.get("uncertain_items", []) if str(item).strip()])

        pdf_analysis = metadata.get("pdf_analysis")
        if isinstance(pdf_analysis, dict):
            uncertain_items.extend([str(item).strip() for item in pdf_analysis.get("evidence_gaps", []) if str(item).strip()])

    return {
        "section_density": section_density,
        "weak_sections": _dedupe(weak_sections, limit=12),
        "timeline_signals": _dedupe(timeline_signals, limit=12),
        "activity_clusters": _dedupe(activity_clusters, limit=12),
        "subject_major_alignment_signals": _dedupe(alignment_signals, limit=12),
        "continuity_signals": _dedupe(continuity_signals, limit=10),
        "process_reflection_signals": _dedupe(process_signals, limit=10),
        "uncertain_items": _dedupe(uncertain_items, limit=12),
    }


def _extract_structure_candidates(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    canonical = metadata.get("student_record_canonical")
    if isinstance(canonical, dict):
        converted = _canonical_to_structure_candidate(canonical)
        if converted:
            candidates.append(converted)

    direct = metadata.get("student_record_structure")
    if isinstance(direct, dict):
        candidates.append(direct)

    analysis_artifact = metadata.get("analysis_artifact")
    if isinstance(analysis_artifact, dict):
        nested = analysis_artifact.get("student_record_structure")
        if isinstance(nested, dict):
            candidates.append(nested)
        fallback = analysis_artifact.get("structure")
        if isinstance(fallback, dict):
            candidates.append(fallback)

    return candidates


def _canonical_to_structure_candidate(canonical: dict[str, Any]) -> dict[str, Any]:
    section_classification = canonical.get("section_classification")
    section_density: dict[str, float] = {}
    if isinstance(section_classification, dict):
        for legacy_key, canonical_key in (
            ("교과학습발달상황", "grades_subjects"),
            ("세특", "subject_special_notes"),
            ("창체", "extracurricular"),
            ("진로", "career_signals"),
            ("독서", "reading_activity"),
            ("행동특성", "behavior_opinion"),
        ):
            payload = section_classification.get(canonical_key)
            if not isinstance(payload, dict):
                continue
            try:
                density = max(0.0, min(1.0, float(payload.get("density") or 0.0)))
            except (TypeError, ValueError):
                continue
            section_density[legacy_key] = density

    return {
        "section_density": section_density,
        "weak_sections": _extract_canonical_values(canonical.get("weak_or_missing_sections"), "section"),
        "timeline_signals": _extract_canonical_values(canonical.get("timeline_signals"), "signal"),
        "activity_clusters": _extract_canonical_values(canonical.get("extracurricular"), "label"),
        "subject_major_alignment_signals": _extract_canonical_values(canonical.get("major_alignment_hints"), "hint"),
        "continuity_signals": _extract_canonical_values(canonical.get("career_signals"), "label"),
        "process_reflection_signals": _extract_canonical_values(canonical.get("subject_special_notes"), "label"),
        "uncertain_items": _extract_canonical_values(canonical.get("uncertainties"), "message"),
    }


def _extract_canonical_values(values: Any, key: str) -> list[str]:
    if not isinstance(values, list):
        return []
    output: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        value = str(item.get(key) or "").strip()
        if value:
            output.append(value)
    return output


def _build_uncertainty_notes(
    *,
    result: DiagnosisResultPayload,
    document_structure: dict[str, Any],
    evidence_items: list[ConsultantDiagnosisEvidenceItem],
) -> list[str]:
    notes: list[str] = []
    if result.document_quality and result.document_quality.needs_review:
        notes.append("문서 파싱 품질 점검 필요: 일부 페이지/구역은 수동 검토 후 확정해야 합니다.")
    if not evidence_items:
        notes.append("직접 인용 가능한 근거가 부족합니다. 주요 주장마다 원문 출처를 보강하세요.")
    if result.review_required:
        notes.append("정책/안전 플래그가 감지되어 검토 태스크가 열린 상태입니다.")
    for item in document_structure.get("uncertain_items", [])[:4]:
        notes.append(f"구조 추정 불확실: {item}")
    if not notes:
        notes.append("현재 근거 범위 내에서 보수적으로 해석했습니다. 새로운 성취 서술은 추가 검증 후 반영하세요.")
    return _dedupe(notes, limit=8)


def _build_roadmap(
    *,
    result: DiagnosisResultPayload,
    uncertainty_notes: list[str],
) -> list[ConsultantDiagnosisRoadmapItem]:
    immediate_actions = _dedupe(
        [*result.next_actions, *[item.description for item in result.action_plan or []]],
        limit=4,
    )
    if not immediate_actions:
        immediate_actions = ["현재 개요에서 근거가 약한 문장 3개를 선택해 출처 라인을 명시합니다."]

    mid_actions = _dedupe(
        [f"보완 과제: {gap.title} - {gap.description}" for gap in result.detailed_gaps or []],
        limit=4,
    )
    if not mid_actions:
        mid_actions = _dedupe(result.gaps, limit=3)
    if not mid_actions:
        mid_actions = ["탐구 연속성을 보여줄 후속 활동 계획을 작성하고 기록합니다."]

    long_actions = _dedupe(
        [f"주제 확장: {topic}" for topic in result.recommended_topics or []],
        limit=4,
    )
    if not long_actions:
        long_actions = ["목표 전공 연계성이 높은 1개 주제를 선정해 심화 보고서 초안을 완성합니다."]

    return [
        ConsultantDiagnosisRoadmapItem(
            horizon="1_month",
            title="1개월: 근거 정합성 정리",
            actions=immediate_actions,
            success_signals=[
                "핵심 주장-근거 매핑표 완성",
                "근거 미확인 문장에 '추가 확인 필요' 명시",
            ],
            caution_notes=uncertainty_notes[:2],
        ),
        ConsultantDiagnosisRoadmapItem(
            horizon="3_months",
            title="3개월: 보완 축 집중 개선",
            actions=mid_actions,
            success_signals=[
                "약점 축(연속성/근거밀도/과정설명) 최소 1개 이상 개선 확인",
                "정량 또는 관찰 근거가 포함된 사례 추가",
            ],
            caution_notes=["활동 사실을 과장하지 말고 실제 수행 범위만 기록"],
        ),
        ConsultantDiagnosisRoadmapItem(
            horizon="6_months",
            title="6개월: 전공 적합성 스토리 완성",
            actions=long_actions,
            success_signals=[
                "전공-교과-활동 연결 문장이 자연스럽게 이어짐",
                "최종 보고서 초안에서 unsupported claim 비율 감소",
            ],
            caution_notes=["합격 가능성 단정 문구 금지", "검증 불가 성취는 보류"],
        ),
    ]


async def _generate_narratives(
    *,
    project: Project,
    result: DiagnosisResultPayload,
    document_structure: dict[str, Any],
    uncertainty_notes: list[str],
) -> _NarrativeGenerationResult:
    fallback_summary = _build_fallback_executive_summary(result=result)
    fallback_memo = _build_fallback_final_memo(result=result)
    settings = get_settings()
    requested_provider = (settings.llm_provider or "gemini").strip().lower()
    requested_model = (
        (settings.ollama_render_model or settings.ollama_model or "gemma4").strip()
        if requested_provider == "ollama"
        else "gemini-1.5-pro"
    )
    fallback_execution = {
        "requested_llm_provider": requested_provider,
        "requested_llm_model": requested_model,
        "actual_llm_provider": "deterministic_fallback",
        "actual_llm_model": "deterministic_fallback",
        "llm_profile_used": "render",
        "fallback_used": True,
        "fallback_reason": "llm_unavailable",
    }

    context_payload = {
        "project_title": project.title,
        "target_university": project.target_university,
        "target_major": project.target_major,
        "headline": result.headline,
        "recommended_focus": result.recommended_focus,
        "strengths": result.strengths[:5],
        "gaps": result.gaps[:5],
        "next_actions": result.next_actions[:5],
        "recommended_topics": result.recommended_topics[:4],
        "weak_sections": document_structure.get("weak_sections", [])[:6],
        "uncertainty_notes": uncertainty_notes[:4],
        "required_section_order": list(_PREMIUM_SECTION_ORDER),
        "narrative_contract": {
            "executive_summary": "4-6문장, 근거와 불확실성 경계 포함",
            "current_record_status_brief": "현재 상태를 1-2문장으로 요약",
            "strengths_brief": "검증된 강점 축 요약 1-2문장",
            "weaknesses_risks_brief": "보완/리스크 축 요약 1-2문장",
            "major_fit_brief": "전공 적합성 축 요약 1-2문장",
            "section_diagnosis_brief": "섹션별 진단 해석 요약 1-2문장",
            "topic_strategy_brief": "주제·전략 요약 1-2문장",
            "roadmap_bridge": "1m/3m/6m 연결 문장 1개",
            "uncertainty_bridge": "불확실성 경계 문장 1개",
            "final_consultant_memo": "최종 실행 코멘트 3-4문장",
        },
    }

    registry = get_prompt_registry()
    system_instruction = registry.compose_prompt("diagnosis.consultant-report-orchestration")
    prompt = (
        f"{registry.compose_prompt('diagnosis.executive-summary-writer')}\n\n"
        f"{registry.compose_prompt('diagnosis.roadmap-generator')}\n\n"
        "[진단 컨텍스트 JSON]\n"
        f"{json.dumps(context_payload, ensure_ascii=False, indent=2)}"
    )

    try:
        llm = get_llm_client(profile="render")
        response = await llm.generate_json(
            prompt=prompt,
            response_model=_ConsultantNarrativePayload,
            system_instruction=system_instruction,
            temperature=get_llm_temperature(profile="render"),
        )
        actual_provider = "ollama" if isinstance(llm, OllamaClient) else "gemini" if isinstance(llm, GeminiClient) else requested_provider
        actual_model = (
            llm.model
            if isinstance(llm, OllamaClient)
            else llm.model_name
            if isinstance(llm, GeminiClient)
            else requested_model
        )
        provider_fallback_used = actual_provider != requested_provider or actual_model != requested_model
        fallback_reason = "provider_auto_fallback" if provider_fallback_used else None
        return _NarrativeGenerationResult(
            narrative=_ConsultantNarrativePayload(
                executive_summary=response.executive_summary.strip() or fallback_summary,
                current_record_status_brief=(response.current_record_status_brief or "").strip() or None,
                strengths_brief=(response.strengths_brief or "").strip() or None,
                weaknesses_risks_brief=(response.weaknesses_risks_brief or "").strip() or None,
                major_fit_brief=(response.major_fit_brief or "").strip() or None,
                section_diagnosis_brief=(response.section_diagnosis_brief or "").strip() or None,
                topic_strategy_brief=(response.topic_strategy_brief or "").strip() or None,
                roadmap_bridge=(response.roadmap_bridge or "").strip() or None,
                uncertainty_bridge=(response.uncertainty_bridge or "").strip() or None,
                final_consultant_memo=response.final_consultant_memo.strip() or fallback_memo,
            ),
            execution_metadata={
                "requested_llm_provider": requested_provider,
                "requested_llm_model": requested_model,
                "actual_llm_provider": actual_provider,
                "actual_llm_model": actual_model,
                "llm_profile_used": "render",
                "fallback_used": provider_fallback_used,
                "fallback_reason": fallback_reason,
            },
        )
    except (LLMRequestError, RuntimeError, ValueError) as exc:
        logger.warning("Consultant narrative fallback applied: %s", exc)
        fallback_execution["fallback_reason"] = getattr(exc, "limited_reason", None) or sanitize_public_error(
            str(exc),
            fallback="llm_unavailable",
            max_length=120,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected consultant narrative error. Fallback applied: %s", exc)
        fallback_execution["fallback_reason"] = sanitize_public_error(
            str(exc),
            fallback="llm_unavailable",
            max_length=120,
        )

    return _NarrativeGenerationResult(
        narrative=_ConsultantNarrativePayload(
            executive_summary=fallback_summary,
            current_record_status_brief=None,
            strengths_brief=None,
            weaknesses_risks_brief=None,
            major_fit_brief=None,
            section_diagnosis_brief=None,
            topic_strategy_brief=None,
            roadmap_bridge=None,
            uncertainty_bridge=None,
            final_consultant_memo=fallback_memo,
        ),
        execution_metadata=fallback_execution,
    )


def _enforce_narrative_contract(
    narrative: _ConsultantNarrativePayload,
    *,
    result: DiagnosisResultPayload,
    document_structure: dict[str, Any],
    uncertainty_notes: list[str],
) -> _ConsultantNarrativePayload:
    weak_sections = [str(item).strip() for item in document_structure.get("weak_sections", []) if str(item).strip()]
    verified_strength = (result.strengths or ["검증 가능한 강점 신호가 제한적입니다."])[0]
    primary_gap = (result.gaps or ["근거 밀도와 과정 설명 보강이 필요합니다."])[0]
    major_fit_seed = (document_structure.get("subject_major_alignment_signals") or ["전공 연계 근거 문장이 제한적입니다."])[0]
    section_density = document_structure.get("section_density") if isinstance(document_structure.get("section_density"), dict) else {}
    density_focus = ", ".join(f"{k}:{int(float(v) * 100)}%" for k, v in list(section_density.items())[:3]) if section_density else "섹션 밀도 정보가 제한적입니다."

    executive_summary = _guardrail_text(
        narrative.executive_summary,
        fallback=(
            f"현재 진단 기준에서 확인된 핵심 강점은 '{verified_strength}'입니다. "
            f"우선 보완축은 '{primary_gap}'이며, 문장-근거 정합성 개선이 필요합니다. "
            "검증이 약한 항목은 '추가 확인 필요'로 분리해 과장 위험을 차단했습니다."
        ),
        max_len=1200,
    )
    if "추가 확인 필요" not in executive_summary:
        executive_summary = f"{executive_summary} 근거가 약한 항목은 추가 확인 필요로 표기합니다."

    final_memo = _guardrail_text(
        narrative.final_consultant_memo,
        fallback=_build_fallback_final_memo(result=result),
        max_len=1100,
    )

    return _ConsultantNarrativePayload(
        executive_summary=executive_summary,
        current_record_status_brief=_guardrail_text(
            narrative.current_record_status_brief,
            fallback=f"현재 기록 상태는 '{result.recommended_focus or '근거 중심 보강'}' 축을 우선 정렬해야 합니다.",
            max_len=360,
        ),
        strengths_brief=_guardrail_text(
            narrative.strengths_brief,
            fallback=f"확인된 강점은 '{verified_strength}'이며 근거 연결성을 유지해야 합니다.",
            max_len=360,
        ),
        weaknesses_risks_brief=_guardrail_text(
            narrative.weaknesses_risks_brief,
            fallback=f"핵심 리스크는 '{primary_gap}'이고 약한 섹션은 {', '.join(weak_sections[:3]) or '추가 확인 필요 항목'}입니다.",
            max_len=360,
        ),
        major_fit_brief=_guardrail_text(
            narrative.major_fit_brief,
            fallback=f"전공 적합성 해석은 '{major_fit_seed}' 근거를 기준으로 보수적으로 제시합니다.",
            max_len=360,
        ),
        section_diagnosis_brief=_guardrail_text(
            narrative.section_diagnosis_brief,
            fallback=f"섹션 밀도 기준 핵심 점검 축은 {density_focus} 입니다.",
            max_len=360,
        ),
        topic_strategy_brief=_guardrail_text(
            narrative.topic_strategy_brief,
            fallback=f"주제 전략은 '{(result.recommended_topics or ['전공 연계 심화 주제'])[0]}' 중심으로 단계적 확장을 권장합니다.",
            max_len=360,
        ),
        roadmap_bridge=_guardrail_text(
            narrative.roadmap_bridge,
            fallback="로드맵은 1개월 정합성 정리, 3개월 보완축 개선, 6개월 전공 스토리 완성 순으로 운영합니다.",
            max_len=360,
        ),
        uncertainty_bridge=_guardrail_text(
            narrative.uncertainty_bridge,
            fallback=f"불확실성 경계: {(uncertainty_notes or ['검증 부족 항목은 추가 확인 필요로 유지']) [0]}",
            max_len=360,
        ),
        final_consultant_memo=final_memo,
    )


def _guardrail_text(value: str | None, *, fallback: str, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    text = re.sub(r"\s+", " ", text).strip()
    for forbidden in ("합격 보장", "무조건 합격", "확정 합격", "반드시 합격", "대신 수행"):
        text = text.replace(forbidden, "검증 필요")
    if len(text) > max_len:
        text = f"{text[: max_len - 1].rstrip()}…"
    return text


def _enforce_section_architecture(
    sections: list[ConsultantDiagnosisSection],
    *,
    report_mode: DiagnosisReportMode,
) -> list[ConsultantDiagnosisSection]:
    expected = _PREMIUM_SECTION_ORDER if report_mode == "premium_10p" else _COMPACT_SECTION_ORDER
    section_map = {section.id: section for section in sections}
    ordered: list[ConsultantDiagnosisSection] = []
    for section_id in expected:
        existing = section_map.get(section_id)
        if existing is not None:
            ordered.append(existing)
            continue
        ordered.append(
            ConsultantDiagnosisSection(
                id=section_id,
                title=_humanize_section_title(section_id),
                subtitle="자동 보완 섹션",
                body_markdown="- 구조 일관성을 위해 기본 섹션 틀을 유지했습니다.\n- 근거가 부족한 항목은 추가 확인 필요로 관리합니다.",
            )
        )
    return ordered


def _humanize_section_title(section_id: str) -> str:
    title_map = {
        "cover_context": "Cover / 학생 목표 컨텍스트",
        "executive_summary": "Executive Summary",
        "current_record_status": "Current Record Status Diagnosis",
        "evaluation_axis": "Evaluation-Axis Analysis",
        "strength_analysis": "Strength Analysis",
        "weakness_risk": "Weakness / Risk Analysis",
        "major_fit": "Major / University Fit Analysis",
        "section_level_diagnosis": "Evidence-Backed Section-Level Diagnosis",
        "roadmap": "Action Roadmap (1m / 3m / 6m)",
        "topic_strategy": "Topic / Report Strategy Recommendations",
        "final_memo": "Final Consultant Memo",
        "appendix": "Appendix / Evidence Note",
    }
    return title_map.get(section_id, section_id)


def _build_fallback_executive_summary(*, result: DiagnosisResultPayload) -> str:
    strength = result.strengths[0] if result.strengths else "현재 기록에는 활용 가능한 기본 강점이 확인됩니다."
    gap = result.gaps[0] if result.gaps else "다음 단계에서는 근거 밀도와 과정 설명을 우선 보완해야 합니다."
    return (
        f"본 진단은 '{result.headline}'를 중심으로 학생부 근거를 재검토했습니다. "
        f"확인된 강점은 '{strength}'이며, 핵심 보완축은 '{gap}'입니다. "
        "현재 상태에서 가장 중요한 전략은 검증 가능한 사례를 중심으로 개요를 재정렬하고, "
        "근거가 약한 문장을 '추가 확인 필요'로 명시해 과장 가능성을 차단하는 것입니다."
    )


def _build_fallback_final_memo(*, result: DiagnosisResultPayload) -> str:
    focus = result.recommended_focus or "근거 연결 강화"
    next_step = result.next_actions[0] if result.next_actions else "개요의 다음 소단락 1개를 근거 중심으로 재작성"
    return (
        "최종 코멘트: 현재 자료만으로도 방향성은 충분히 도출됩니다. "
        f"다만 '{focus}'를 우선 과제로 두고, '{next_step}'를 실행해 문장-근거 정합성을 먼저 끌어올리는 것이 안전합니다. "
        "합격 예측성 문구나 검증되지 않은 성취 서술은 배제하고, 근거가 확보된 문장부터 완성도를 높이십시오."
    )


def _build_sections(
    *,
    result: DiagnosisResultPayload,
    report_mode: DiagnosisReportMode,
    target_context: str,
    evidence_items: list[ConsultantDiagnosisEvidenceItem],
    score_blocks: list[ConsultantDiagnosisScoreBlock],
    document_structure: dict[str, Any],
    roadmap: list[ConsultantDiagnosisRoadmapItem],
    narratives: _ConsultantNarrativePayload,
    uncertainty_notes: list[str],
) -> list[ConsultantDiagnosisSection]:
    top_evidence = evidence_items[:8]
    weak_sections = document_structure.get("weak_sections", [])
    timeline_signals = document_structure.get("timeline_signals", [])
    alignment_signals = document_structure.get("subject_major_alignment_signals", [])
    continuity_signals = document_structure.get("continuity_signals", [])
    process_signals = document_structure.get("process_reflection_signals", [])

    section_density = document_structure.get("section_density", {})
    density_lines = [f"{key}: {round(float(value) * 100)}%" for key, value in section_density.items()]
    if not density_lines:
        density_lines = ["섹션 밀도 추정값이 부족하여 텍스트 기반 보수 추정을 사용했습니다."]

    roadmap_lines: list[str] = []
    for item in roadmap:
        roadmap_lines.append(f"{item.title}")
        roadmap_lines.extend([f"- {action}" for action in item.actions[:3]])

    current_status_intro = _clean_line(narratives.current_record_status_brief, max_len=220)
    strength_intro = _clean_line(narratives.strengths_brief, max_len=220)
    weakness_intro = _clean_line(narratives.weaknesses_risks_brief, max_len=220)
    major_fit_intro = _clean_line(narratives.major_fit_brief, max_len=220)
    section_diag_intro = _clean_line(narratives.section_diagnosis_brief, max_len=220)
    topic_strategy_intro = _clean_line(narratives.topic_strategy_brief, max_len=220)
    roadmap_bridge = _clean_line(narratives.roadmap_bridge, max_len=220)
    uncertainty_bridge = _clean_line(narratives.uncertainty_bridge, max_len=220)

    sections = [
        ConsultantDiagnosisSection(
            id="cover_context",
            title="Cover / 학생 목표 컨텍스트",
            subtitle="프로젝트 목표와 진단 범위",
            body_markdown=_bulleted(
                [
                    target_context,
                    "본 리포트는 학생부 기반 근거만 사용하며 합격 보장/예측 문구를 포함하지 않습니다.",
                    "검증 불충분 항목은 '추가 확인 필요'로 분리했습니다.",
                ]
            ),
            evidence_items=top_evidence[:2],
        ),
        ConsultantDiagnosisSection(
            id="executive_summary",
            title="Executive Summary",
            subtitle="핵심 진단 요약",
            body_markdown=narratives.executive_summary,
            evidence_items=top_evidence[:3],
        ),
        ConsultantDiagnosisSection(
            id="current_record_status",
            title="Current Record Status Diagnosis",
            subtitle="현재 기록 상태 점검",
            body_markdown=_bulleted(
                [
                    *( [current_status_intro] if current_status_intro else [] ),
                    result.overview or "구조화 진단 개요가 요약되지 않아 기본 점검 프레임으로 작성했습니다.",
                    f"권장 집중축: {result.recommended_focus}",
                    *[f"리스크: {risk}" for risk in (result.risks or [])[:3]],
                ]
            ),
            evidence_items=top_evidence[:3],
            additional_verification_needed=weak_sections[:2],
        ),
        ConsultantDiagnosisSection(
            id="evaluation_axis",
            title="Evaluation-Axis Analysis",
            subtitle="평가축별 해석",
            body_markdown=_bulleted(
                [f"{block.label} ({block.score}): {block.interpretation}" for block in score_blocks]
            ),
            evidence_items=top_evidence[:2],
        ),
        ConsultantDiagnosisSection(
            id="strength_analysis",
            title="Strength Analysis",
            subtitle="검증된 강점",
            body_markdown=_bulleted(
                [
                    *( [strength_intro] if strength_intro else [] ),
                    *(result.strengths or ["강점 문장이 부족하여 보수적 해석을 사용했습니다."]),
                ]
            ),
            evidence_items=[item for item in top_evidence if item.support_status == "verified"][:3],
        ),
        ConsultantDiagnosisSection(
            id="weakness_risk",
            title="Weakness / Risk Analysis",
            subtitle="보완 필요 영역",
            body_markdown=_bulleted(
                [
                    *( [weakness_intro] if weakness_intro else [] ),
                    *(result.gaps or ["보완 포인트가 명시되지 않아 기본 리스크 프레임을 적용했습니다."]),
                    *[f"약한 섹션 추정: {item}" for item in weak_sections[:3]],
                ]
            ),
            evidence_items=top_evidence[:3],
            additional_verification_needed=weak_sections[:4],
            unsupported_claims=["검증되지 않은 성취/수상/실험 결과 추가 금지"],
        ),
        ConsultantDiagnosisSection(
            id="major_fit",
            title="Major / University Fit Analysis",
            subtitle="목표 진로 적합성",
            body_markdown=_bulleted(
                [
                    *( [major_fit_intro] if major_fit_intro else [] ),
                    *(alignment_signals[:4] or ["전공 적합성 직접 신호가 제한적입니다."]),
                    *(continuity_signals[:3] or ["연속성 신호가 부족해 후속활동 설계가 필요합니다."]),
                ]
            ),
            evidence_items=top_evidence[:2],
            additional_verification_needed=["목표 전공 직접 연계 문장 보강 필요"],
        ),
        ConsultantDiagnosisSection(
            id="section_level_diagnosis",
            title="Evidence-Backed Section-Level Diagnosis",
            subtitle="섹션별 근거 밀도 진단",
            body_markdown=_bulleted(
                [
                    *( [section_diag_intro] if section_diag_intro else [] ),
                    *density_lines[:8],
                    *(timeline_signals[:3] or ["학기/학년 흐름 신호가 제한적으로 추출되었습니다."]),
                    *(process_signals[:3] or ["과정·성찰 신호를 명시적으로 보강할 필요가 있습니다."]),
                ]
            ),
            evidence_items=top_evidence[:4],
        ),
        ConsultantDiagnosisSection(
            id="roadmap",
            title="Action Roadmap (1m / 3m / 6m)",
            subtitle="실행 가능한 단계별 계획",
            body_markdown=_bulleted(
                [
                    *( [roadmap_bridge] if roadmap_bridge else [] ),
                    *roadmap_lines,
                ]
            ),
            evidence_items=top_evidence[:2],
        ),
        ConsultantDiagnosisSection(
            id="topic_strategy",
            title="Topic / Report Strategy Recommendations",
            subtitle="탐구 주제 및 보고서 전략",
            body_markdown=_bulleted(
                [
                    *( [topic_strategy_intro] if topic_strategy_intro else [] ),
                    *(result.recommended_topics or ["추천 주제 신호가 부족하여 기본 전공연계 전략을 사용했습니다."]),
                    *[f"후속 행동: {item}" for item in (result.next_actions or [])[:3]],
                ]
            ),
            evidence_items=top_evidence[:3],
            additional_verification_needed=["주제별 실제 수행 가능 범위를 문장으로 명시"],
        ),
        ConsultantDiagnosisSection(
            id="final_memo",
            title="Final Consultant Memo",
            subtitle="최종 점검 코멘트",
            body_markdown=narratives.final_consultant_memo,
            evidence_items=top_evidence[:2],
        ),
    ]

    if report_mode == "premium_10p":
        appendix_lines = [
            "인용 부록에서 주장-근거 라인을 교차 점검하십시오.",
            "추가 확인 필요 문장은 최종본에서도 표기를 유지하십시오.",
            "내부 검토 로그는 제출본에서 과도하게 노출하지 않도록 관리하십시오.",
        ]
        if uncertainty_bridge:
            appendix_lines.insert(0, uncertainty_bridge)
        for note in uncertainty_notes[:4]:
            appendix_lines.append(f"불확실성 노트: {note}")
        for citation in top_evidence[:4]:
            label = citation.source_label
            if citation.page_number:
                label = f"{label} p.{citation.page_number}"
            appendix_lines.append(f"인용 근거: {label} ({citation.support_status})")
        sections.append(
            ConsultantDiagnosisSection(
                id="appendix",
                title="Appendix / Evidence Note",
                subtitle="근거·불확실성 부록",
                body_markdown=_bulleted(appendix_lines),
                evidence_items=top_evidence[:4],
            )
        )
    return sections


def _build_appendix_notes(documents: list[Any], document_structure: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for document in documents:
        metadata = getattr(document, "parse_metadata", None)
        if not isinstance(metadata, dict):
            continue
        warnings = metadata.get("warnings")
        if isinstance(warnings, list):
            for warning in warnings:
                text = str(warning).strip()
                if text:
                    notes.append(f"파싱 경고: {text}")
        confidence = metadata.get("parse_confidence")
        if isinstance(confidence, (int, float)):
            notes.append(f"파싱 confidence={round(float(confidence), 3)}")
    for item in document_structure.get("uncertain_items", [])[:5]:
        notes.append(f"구조 추정 불확실 항목: {item}")
    return _dedupe(notes, limit=20)


def _build_failed_report_payload(
    *,
    run: DiagnosisRun,
    project: Project,
    report_mode: DiagnosisReportMode,
    template_id: str,
) -> str:
    payload = ConsultantDiagnosisReport(
        diagnosis_run_id=run.id,
        project_id=project.id,
        report_mode=report_mode,
        template_id=template_id,
        title=f"{project.title} 전문 컨설턴트 진단서",
        subtitle="생성 실패 - 제한 정보",
        student_target_context=f"프로젝트: {project.title}",
        generated_at=datetime.now(timezone.utc),
        score_blocks=[],
        sections=[
            ConsultantDiagnosisSection(
                id="generation_failed",
                title="진단서 생성 실패",
                subtitle=None,
                body_markdown="요청한 진단서를 생성하지 못했습니다. 프로젝트 근거 문서를 확인한 뒤 재시도해 주세요.",
            )
        ],
        roadmap=[],
        citations=[],
        uncertainty_notes=["리포트 생성 실패로 인해 상세 분석이 포함되지 않았습니다."],
        final_consultant_memo="근거 문서 상태 확인 후 재생성해 주세요.",
        appendix_notes=[],
        render_hints={"a4": True, "minimum_pages": 1},
    )
    return payload.model_dump_json()


def _clean_line(value: str | None, *, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}…"


def _bulleted(lines: list[str]) -> str:
    cleaned = [str(item).strip() for item in lines if str(item).strip()]
    return "\n".join(f"- {line}" for line in cleaned)


def _dedupe(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw in items:
        normalized = str(raw or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped
