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

from unifoli_api.core.config import get_settings
from unifoli_api.core.llm import GeminiClient, LLMRequestError, OllamaClient, get_llm_client, get_llm_temperature
from unifoli_api.core.security import sanitize_public_error
from unifoli_api.db.models.diagnosis_report_artifact import DiagnosisReportArtifact
from unifoli_api.db.models.diagnosis_run import DiagnosisRun
from unifoli_api.db.models.project import Project
from unifoli_api.schemas.diagnosis import (
    ConsultantDiagnosisArtifactResponse,
    ConsultantDiagnosisEvidenceItem,
    ConsultantDiagnosisReport,
    ConsultantDiagnosisRoadmapItem,
    ConsultantDiagnosisScoreBlock,
    ConsultantDiagnosisScoreGroup,
    ConsultantDiagnosisSection,
    DiagnosisReportMode,
    DiagnosisResultPayload,
)
from unifoli_api.services.document_service import list_documents_for_project
from unifoli_api.services.prompt_registry import (
    PromptAssetNotFoundError,
    PromptRegistryError,
    get_prompt_registry,
)
from unifoli_domain.enums import RenderFormat
from unifoli_render.diagnosis_report_design_contract import get_diagnosis_report_design_contract
from unifoli_render.diagnosis_report_pdf_renderer import render_consultant_diagnosis_pdf
from unifoli_render.template_registry import get_template
from unifoli_shared.storage import get_storage_provider, get_storage_provider_name


logger = logging.getLogger("unifoli.api.diagnosis_report")

_DEFAULT_TEMPLATE_BY_MODE: dict[str, str] = {
    "compact": "consultant_diagnosis_compact",
    "premium_10p": "consultant_diagnosis_premium_10p",
}
_REPORT_FAILURE_FALLBACK = "진단 보고서 생성에 실패했습니다. 프로젝트 근거를 확인한 뒤 다시 시도해 주세요."


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
    "cover_title_summary",
    "executive_verdict",
    "record_baseline_dashboard",
    "student_evaluation_matrix",
    "system_quality_reliability",
    "strength_analysis",
    "weakness_risk_analysis",
    "section_by_section_diagnosis",
    "major_fit_interpretation",
    "recommended_report_directions",
    "avoid_repetition_topics",
    "evidence_cards",
    "interview_readiness",
    "roadmap",
    "uncertainty_verification_note",
    "citation_appendix",
)

_COMPACT_SECTION_ORDER: tuple[str, ...] = (
    "executive_verdict",
    "record_baseline_dashboard",
    "strength_analysis",
    "risk_analysis",
    "recommended_report_direction",
    "roadmap",
    "uncertainty_verification_note",
    "citation_appendix",
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
    document_structure = _collect_student_record_structure(documents)
    evidence_bank = _collect_evidence_bank(documents)
    evidence_items = _build_evidence_items(result)
    score_groups = _build_score_groups(
        result=result,
        document_structure=document_structure,
        evidence_items=evidence_items,
        evidence_bank=evidence_bank,
    )
    student_score_group = next((group for group in score_groups if group.group == "student_evaluation"), None)
    system_score_group = next((group for group in score_groups if group.group == "system_quality"), None)
    score_blocks = list(student_score_group.blocks) if student_score_group else []
    contradiction_blocked = bool(system_score_group and system_score_group.gating_status == "blocked")
    unique_anchor_ids = {
        str(item.get("anchor_id") or "").strip()
        for item in evidence_bank
        if str(item.get("anchor_id") or "").strip()
    }
    unique_anchor_pages = {
        int(item.get("page") or 0)
        for item in evidence_bank
        if int(item.get("page") or 0) > 0
    }
    evidence_anchor_gate_failed = len(unique_anchor_ids) < 10 or len(unique_anchor_pages) < 6
    reanalysis_required = bool(
        (student_score_group and student_score_group.gating_status == "reanalysis_required")
        or (system_score_group and system_score_group.gating_status == "reanalysis_required")
        or evidence_anchor_gate_failed
    )
    if evidence_anchor_gate_failed:
        for group in score_groups:
            if group.gating_status != "blocked":
                group.gating_status = "reanalysis_required"
                message = f"고유 앵커 {len(unique_anchor_ids)}개 / 페이지 {len(unique_anchor_pages)}개로 품질 게이트를 충족하지 못했습니다."
                group.note = _clean_line(f"{group.note or ''} {message}".strip(), max_len=220)
    if contradiction_blocked:
        raise ValueError("contradiction_check_failed")
    uncertainty_notes = _build_uncertainty_notes(
        result=result,
        document_structure=document_structure,
        evidence_items=evidence_items,
        evidence_bank=evidence_bank,
    )
    if reanalysis_required:
        uncertainty_notes = _dedupe(
            [
                "보완이 필요합니다: 필수 섹션 커버리지가 부족하거나 근거 앵커 분산이 낮습니다.",
                (
                    f"앵커 품질 게이트 미충족: 고유 앵커 {len(unique_anchor_ids)}개 / 고유 페이지 {len(unique_anchor_pages)}개"
                    if evidence_anchor_gate_failed
                    else ""
                ),
                *uncertainty_notes,
            ],
            limit=10,
        )
    roadmap = _build_roadmap(result=result, uncertainty_notes=uncertainty_notes)
    diagnosis_intelligence = _build_diagnosis_intelligence(
        result=result,
        document_structure=document_structure,
        evidence_bank=evidence_bank,
        evidence_items=evidence_items,
    )
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
        score_groups=score_groups,
        document_structure=document_structure,
        evidence_bank=evidence_bank,
        roadmap=roadmap,
        narratives=narratives,
        uncertainty_notes=uncertainty_notes,
        reanalysis_required=reanalysis_required,
        diagnosis_intelligence=diagnosis_intelligence,
    )
    sections = _enforce_section_architecture(sections, report_mode=report_mode)

    appendix_notes: list[str] = []
    internal_qa_artifact = _build_appendix_notes(documents, document_structure)
    if include_appendix and report_mode == "compact":
        appendix_notes.extend(internal_qa_artifact)
    if include_citations and report_mode == "compact":
        appendix_notes.append("인용 부록에는 주장-근거 연결 검증을 위한 출처 라인이 포함됩니다.")
    diagnosis_confidence_block = next(
        (
            block
            for block in (system_score_group.blocks if system_score_group else [])
            if block.key == "diagnosis_confidence_gate"
        ),
        None,
    )
    analysis_confidence_score = (
        (float(diagnosis_confidence_block.score) / 100.0)
        if diagnosis_confidence_block is not None
        else float(
            ((document_structure.get("coverage_check") or {}).get("coverage_score", 0.0))
            if isinstance(document_structure.get("coverage_check"), dict)
            else 0.0
        )
    )

    report_payload = ConsultantDiagnosisReport(
        diagnosis_run_id=run.id,
        project_id=project.id,
        report_mode=report_mode,
        template_id=template_id,
        title=f"{project.title} 전문 컨설턴트 진단",
        subtitle="학생부 근거 기반 진단 · 리스크 명시 · 실행 로드맵",
        student_target_context=target_context,
        generated_at=datetime.now(timezone.utc),
        score_blocks=score_blocks,
        score_groups=score_groups,
        sections=sections,
        roadmap=roadmap,
        citations=evidence_items if include_citations and report_mode == "compact" else [],
        uncertainty_notes=uncertainty_notes,
        final_consultant_memo=narratives.final_consultant_memo,
        appendix_notes=appendix_notes,
        diagnosis_intelligence=diagnosis_intelligence,
        render_hints={
            "a4": True,
            "minimum_pages": 10 if report_mode == "premium_10p" else 5,
            "visual_tone": "consultant_premium",
            "include_appendix": include_appendix,
            "include_citations": include_citations,
            "analysis_confidence_score": analysis_confidence_score,
            "one_line_verdict": _clean_line(narratives.executive_summary, max_len=150),
            "public_appendix_enabled": bool(include_appendix and report_mode == "compact"),
            "public_citations_enabled": bool(include_citations and report_mode == "compact"),
            "section_order": list(_PREMIUM_SECTION_ORDER if report_mode == "premium_10p" else _COMPACT_SECTION_ORDER),
            "provisional_label": "reference_only" if reanalysis_required else "verified_ready",
            "verified_vs_inferred_policy": {
                "verified": "근거 앵커로 확인된 문장만 단정적으로 표현",
                "inferred": "추론 문장은 가능성/해석 표현으로 제한",
                "uncertainty": "근거 부족 항목은 추가 확인 필요로 명시",
            },
            "section_semantics": _build_section_semantics(report_mode=report_mode),
            "design_contract": design_contract,
            "diagnosis_intelligence": diagnosis_intelligence,
            "internal_qa_artifact": {
                "appendix_notes": internal_qa_artifact,
                "evidence_bank_size": len(evidence_bank),
                "unique_evidence_pages": len({int(item.get("page") or 0) for item in evidence_bank if int(item.get("page") or 0) > 0}),
                "reanalysis_required": reanalysis_required,
            },
            "execution_metadata": {
                **narratives_result.execution_metadata,
                "diagnosis_backbone_requested_llm_provider": result.requested_llm_provider,
                "diagnosis_backbone_requested_llm_model": result.requested_llm_model,
                "diagnosis_backbone_actual_llm_provider": result.actual_llm_provider,
                "diagnosis_backbone_actual_llm_model": result.actual_llm_model,
                "diagnosis_backbone_fallback_used": result.fallback_used,
                "diagnosis_backbone_fallback_reason": result.fallback_reason,
                "reanalysis_required": reanalysis_required,
            },
        },
    )
    return report_payload


def _build_target_context(*, project: Project, result: DiagnosisResultPayload, documents: list[Any]) -> str:
    target_university = project.target_university or "미설정"
    target_major = project.target_major or "미설정"
    diagnosis_target = result.diagnosis_summary.target_context if result.diagnosis_summary else None
    student_name = "미확인"
    for document in documents:
        metadata = getattr(document, "parse_metadata", None)
        if not isinstance(metadata, dict):
            continue
        canonical = metadata.get("student_record_canonical")
        if isinstance(canonical, dict):
            analysis_artifact = metadata.get("analysis_artifact")
            canonical_data = (
                analysis_artifact.get("canonical_data")
                if isinstance(analysis_artifact, dict) and isinstance(analysis_artifact.get("canonical_data"), dict)
                else {}
            )
            candidate = str(canonical_data.get("student_name") or "").strip()
            if candidate:
                student_name = candidate
                break
    context_bits = [
        f"학생: {student_name}",
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
                uncertainty_note="해당 점수는 입력 문서 기반 상대평가이며 합격 예측이 아닙니다.",
            )
        )

    if not blocks:
        blocks.append(
            ConsultantDiagnosisScoreBlock(
                key="fallback",
                label="진단 요약 점수",
                score=52,
                band="watch",
                interpretation="구조화 점수 축이 부족하여 보수적 기본 점수를 사용합니다.",
                uncertainty_note="추가 문서 근거 정보 확보를 권장합니다.",
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


def _collect_evidence_bank(documents: list[Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for document in documents:
        metadata = getattr(document, "parse_metadata", None)
        if not isinstance(metadata, dict):
            continue
        canonical = metadata.get("student_record_canonical")
        if not isinstance(canonical, dict):
            continue
        raw_bank = canonical.get("evidence_bank")
        if not isinstance(raw_bank, list):
            continue
        for item in raw_bank:
            if not isinstance(item, dict):
                continue
            try:
                page = int(item.get("page") or 0)
            except (TypeError, ValueError):
                continue
            quote = str(item.get("quote") or "").strip()
            if page <= 0 or not quote:
                continue
            dedupe_key = (page, quote)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            collected.append(item)
    return collected


def _bounded_score(value: float) -> int:
    return int(max(0, min(100, round(float(value)))))


def _student_band(score: int) -> str:
    if score >= 80:
        return "strong"
    if score >= 60:
        return "watch"
    return "weak"


def _system_band(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "mid"
    return "low"


def _axis_score_lookup(result: DiagnosisResultPayload) -> dict[str, int]:
    scores: dict[str, int] = {}
    for axis in result.admission_axes or []:
        key = str(axis.key or "").strip()
        if not key:
            continue
        scores[key] = _bounded_score(axis.score)
    return scores


def _build_student_score_block(
    *,
    key: str,
    label: str,
    interpretation: str,
    next_best_action: str,
    base_score: int,
    evidence_key: str,
    evidence_bank: list[dict[str, Any]],
    required_anchor_count: int,
    required_page_diversity: int,
    page_diversity: int,
    coverage_score: float,
    missing_required_count: int,
    contradiction_passed: bool,
    support_signal_count: int,
) -> ConsultantDiagnosisScoreBlock:
    anchor_ids = _select_anchor_ids_for_score(key=evidence_key, evidence_bank=evidence_bank)
    anchor_count = len(anchor_ids)
    adjusted_score = _bounded_score(base_score)
    missing_evidence: list[str] = []

    if anchor_count < required_anchor_count:
        adjusted_score = min(adjusted_score, 55)
        missing_evidence.append(f"축별 최소 앵커 기준({required_anchor_count}) 미달")
    if page_diversity < required_page_diversity:
        adjusted_score = min(adjusted_score, 60)
        missing_evidence.append(f"페이지 다양성 기준({required_page_diversity}) 미달")
    if coverage_score < 0.65:
        adjusted_score = min(adjusted_score, 65)
        missing_evidence.append("파싱 커버리지 65% 미만")
    if missing_required_count > 0:
        adjusted_score = min(adjusted_score, 62)
        missing_evidence.append(f"필수 섹션 누락 {missing_required_count}건")
    if not contradiction_passed:
        adjusted_score = min(adjusted_score, 40)
        missing_evidence.append("모순 검증 실패")

    evidence_summary = (
        f"고유 앵커 {anchor_count}개 · 페이지 다양성 {page_diversity}개 · 관련 신호 {support_signal_count}개"
    )
    if missing_evidence:
        uncertainty_note = "reference-only: 근거 조건 일부 미충족으로 보수적 클램프를 적용했습니다."
    else:
        uncertainty_note = "근거 조건 충족: 앵커/페이지 분산을 확인했습니다."

    return ConsultantDiagnosisScoreBlock(
        key=key,
        label=label,
        score=adjusted_score,
        band=_student_band(adjusted_score),
        interpretation=interpretation,
        uncertainty_note=uncertainty_note,
        evidence_summary=evidence_summary,
        missing_evidence="; ".join(missing_evidence) if missing_evidence else None,
        next_best_action=next_best_action,
    )


def _build_score_groups(
    *,
    result: DiagnosisResultPayload,
    document_structure: dict[str, Any],
    evidence_items: list[ConsultantDiagnosisEvidenceItem],
    evidence_bank: list[dict[str, Any]],
) -> list[ConsultantDiagnosisScoreGroup]:
    coverage_check = (
        document_structure.get("coverage_check")
        if isinstance(document_structure.get("coverage_check"), dict)
        else {}
    )
    contradiction_check = (
        document_structure.get("contradiction_check")
        if isinstance(document_structure.get("contradiction_check"), dict)
        else {"passed": True, "items": []}
    )
    parse_coverage_score = _bounded_score(float(coverage_check.get("coverage_score", 0.0)) * 100.0)
    missing_required_sections = [
        str(item).strip()
        for item in coverage_check.get("missing_required_sections", [])
        if str(item).strip()
    ] if isinstance(coverage_check.get("missing_required_sections"), list) else []

    continuity_signals = [
        str(item).strip()
        for item in document_structure.get("continuity_signals", [])
        if str(item).strip()
    ]
    alignment_signals = [
        str(item).strip()
        for item in document_structure.get("subject_major_alignment_signals", [])
        if str(item).strip()
    ]
    process_signals = [
        str(item).strip()
        for item in document_structure.get("process_reflection_signals", [])
        if str(item).strip()
    ]
    weak_sections = [str(item).strip() for item in document_structure.get("weak_sections", []) if str(item).strip()]

    unique_anchor_ids = {
        str(item.get("anchor_id") or "").strip()
        for item in evidence_bank
        if str(item.get("anchor_id") or "").strip()
    }
    unique_anchor_pages = {
        int(item.get("page") or 0)
        for item in evidence_bank
        if int(item.get("page") or 0) > 0
    }
    unique_citation_pages = {int(item.page_number or 0) for item in evidence_items if int(item.page_number or 0) > 0}
    unique_quotes = {
        str(item.get("quote") or "").strip()
        for item in evidence_bank
        if str(item.get("quote") or "").strip()
    }
    anchor_diversity_score = _bounded_score((len(unique_anchor_ids) / 12.0) * 100.0)
    page_diversity_score = _bounded_score((len(unique_anchor_pages) / 8.0) * 100.0)
    citation_coverage_score = _bounded_score((len(unique_citation_pages) / max(len(unique_anchor_pages), 1)) * 100.0)
    evidence_uniqueness_score = _bounded_score((len(unique_quotes) / max(len(evidence_bank), 1)) * 100.0)
    redaction_safety_score = 100 if _redaction_safety_ok(evidence_bank) else 55
    contradiction_passed = bool(contradiction_check.get("passed", True))
    contradiction_score = 100 if contradiction_passed else 0
    section_coverage_reliability_score = _bounded_score(
        parse_coverage_score - (len(missing_required_sections) * 10.0)
    )
    evidence_anchor_gate_failed = len(unique_anchor_ids) < 10 or len(unique_anchor_pages) < 6
    required_section_gate_failed = bool(missing_required_sections)
    reanalysis_required = (
        bool(coverage_check.get("reanalysis_required"))
        or parse_coverage_score < 72
        or evidence_anchor_gate_failed
        or required_section_gate_failed
    )
    reanalysis_requirement_score = 35 if reanalysis_required else 100
    diagnosis_confidence_score = _bounded_score(
        (parse_coverage_score * 0.26)
        + (citation_coverage_score * 0.18)
        + (evidence_uniqueness_score * 0.16)
        + (anchor_diversity_score * 0.16)
        + (section_coverage_reliability_score * 0.12)
        + (redaction_safety_score * 0.12)
    )
    if reanalysis_required:
        diagnosis_confidence_score = min(diagnosis_confidence_score, 64)
    if evidence_anchor_gate_failed:
        diagnosis_confidence_score = min(diagnosis_confidence_score, 58)
    if not contradiction_passed:
        diagnosis_confidence_score = 0

    axis_scores = _axis_score_lookup(result)
    u_rigor = axis_scores.get("universal_rigor", 52)
    u_spec = axis_scores.get("universal_specificity", 50)
    r_narr = axis_scores.get("relational_narrative", 50)
    r_cont = axis_scores.get("relational_continuity", 50)
    c_depth = axis_scores.get("cluster_depth", 50)
    c_suit = axis_scores.get("cluster_suitability", 50)
    authenticity_risk = axis_scores.get("authenticity_risk", 50)
    authenticity_safety = _bounded_score(100.0 - authenticity_risk)

    evidence_density_signal = _bounded_score(
        len(unique_anchor_ids) * 7.0
        + len(unique_anchor_pages) * 6.0
        + len(unique_citation_pages) * 4.0
    )
    process_signal_strength = _bounded_score(len(process_signals) * 22.0)
    continuity_signal_strength = _bounded_score(len(continuity_signals) * 18.0)
    alignment_signal_strength = _bounded_score(len(alignment_signals) * 18.0)

    inquiry_depth = _bounded_score((c_depth * 0.78) + (u_rigor * 0.22))
    evidence_density = _bounded_score((u_spec * 0.4) + (evidence_density_signal * 0.6))
    process_reflection_quality = _bounded_score((r_narr * 0.55) + (process_signal_strength * 0.45))
    continuity_across_grades = _bounded_score((r_cont * 0.7) + (continuity_signal_strength * 0.3))
    major_fit_alignment = _bounded_score((c_suit * 0.75) + (alignment_signal_strength * 0.25))
    originality_without_overclaim = _bounded_score(
        (c_depth * 0.45)
        + (evidence_uniqueness_score * 0.35)
        + (authenticity_safety * 0.2)
    )
    if len(unique_anchor_ids) < 8:
        originality_without_overclaim = min(originality_without_overclaim, 62)
    authenticity_safety_score = _bounded_score((authenticity_safety * 0.75) + (redaction_safety_score * 0.25))
    narrative_cohesion = _bounded_score((r_narr * 0.52) + (r_cont * 0.48))
    actionability_for_next_report = _bounded_score(
        (narrative_cohesion * 0.35)
        + (major_fit_alignment * 0.25)
        + (_bounded_score((len(result.next_actions) * 18.0) + (len(result.recommended_topics) * 14.0)) * 0.4)
    )
    interview_explainability = _bounded_score(
        (narrative_cohesion * 0.4)
        + (process_reflection_quality * 0.35)
        + (evidence_density * 0.25)
    )

    student_blocks = [
        _build_student_score_block(
            key="academic_rigor",
            label="학업 엄밀성",
            interpretation="교과 성취와 탐구 정확도에서 학업 기반의 신뢰도를 평가합니다.",
            next_best_action="핵심 과목 2개에서 관찰값 또는 근거 문장을 각 1개 이상 추가하세요.",
            base_score=u_rigor,
            evidence_key="universal_rigor",
            evidence_bank=evidence_bank,
            required_anchor_count=3,
            required_page_diversity=2,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(process_signals),
        ),
        _build_student_score_block(
            key="specificity_and_concreteness",
            label="구체성·정량성",
            interpretation="주장에 대응하는 수치·관찰·방법 설명의 구체성을 평가합니다.",
            next_best_action="핵심 주장 3개를 선택해 각각 페이지 앵커와 측정/관찰 단서를 붙이세요.",
            base_score=u_spec,
            evidence_key="universal_specificity",
            evidence_bank=evidence_bank,
            required_anchor_count=3,
            required_page_diversity=3,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(unique_citation_pages),
        ),
        _build_student_score_block(
            key="inquiry_depth",
            label="탐구 심화도",
            interpretation="단발 활동이 아닌 비교·확장·심화 흔적의 밀도를 평가합니다.",
            next_best_action="동일 주제에서 '문제-시도-한계-보완' 흐름을 1개 사례로 정리하세요.",
            base_score=inquiry_depth,
            evidence_key="cluster_depth",
            evidence_bank=evidence_bank,
            required_anchor_count=3,
            required_page_diversity=2,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(continuity_signals),
        ),
        _build_student_score_block(
            key="evidence_density",
            label="근거 밀도",
            interpretation="주요 주장 대비 인용·앵커·페이지 분산의 충분성을 평가합니다.",
            next_best_action="한 문단당 최소 1개 근거 앵커를 연결하고 근거 없는 문장은 분리하세요.",
            base_score=evidence_density,
            evidence_key="universal_specificity",
            evidence_bank=evidence_bank,
            required_anchor_count=4,
            required_page_diversity=3,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(unique_anchor_ids),
        ),
        _build_student_score_block(
            key="process_reflection_quality",
            label="과정 성찰력",
            interpretation="활동 과정의 의사결정·한계 인식·개선 연결성을 평가합니다.",
            next_best_action="활동 1개를 선택해 의사결정 이유와 한계 인식을 2문장으로 명시하세요.",
            base_score=process_reflection_quality,
            evidence_key="relational_narrative",
            evidence_bank=evidence_bank,
            required_anchor_count=2,
            required_page_diversity=2,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(process_signals),
        ),
        _build_student_score_block(
            key="continuity_across_grades",
            label="학년 간 연속성",
            interpretation="학년이 올라갈수록 관심 주제가 연결·심화되는 흐름을 평가합니다.",
            next_best_action="학년별 활동 3개를 연결한 연속성 문장을 먼저 작성하세요.",
            base_score=continuity_across_grades,
            evidence_key="relational_continuity",
            evidence_bank=evidence_bank,
            required_anchor_count=2,
            required_page_diversity=2,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(continuity_signals),
        ),
        _build_student_score_block(
            key="major_fit_alignment",
            label="전공 적합성 정합",
            interpretation="교과·활동·진로 신호가 목표 전공 해석으로 일관되게 묶이는지 평가합니다.",
            next_best_action="전공 키워드 2개를 기준으로 기존 활동을 재분류해 연결 문장을 만드세요.",
            base_score=major_fit_alignment,
            evidence_key="cluster_suitability",
            evidence_bank=evidence_bank,
            required_anchor_count=3,
            required_page_diversity=2,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(alignment_signals),
        ),
        _build_student_score_block(
            key="originality_without_overclaim",
            label="차별성(과장 배제)",
            interpretation="차별성은 유지하되 근거가 약한 성과 과장을 억제하는 안전성을 평가합니다.",
            next_best_action="새 활동을 지어내지 말고 기존 활동의 문제정의·해결과정을 더 구체화하세요.",
            base_score=originality_without_overclaim,
            evidence_key="cluster_depth",
            evidence_bank=evidence_bank,
            required_anchor_count=3,
            required_page_diversity=3,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=max(len(unique_quotes), 1),
        ),
        _build_student_score_block(
            key="authenticity_safety",
            label="진정성 안전성",
            interpretation="검증 가능한 사실 범위를 벗어나지 않는지, 과장 위험이 통제되는지 평가합니다.",
            next_best_action="근거가 약한 주장에는 '추가 확인 필요' 라벨을 명시하세요.",
            base_score=authenticity_safety_score,
            evidence_key="relational_narrative",
            evidence_bank=evidence_bank,
            required_anchor_count=3,
            required_page_diversity=3,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=max(1, len(unique_citation_pages)),
        ),
        _build_student_score_block(
            key="narrative_cohesion",
            label="서사 응집도",
            interpretation="활동·교과·전공 연결 문장이 하나의 축으로 읽히는지를 평가합니다.",
            next_best_action="핵심 서사 문장을 1개 정하고 모든 사례를 그 문장에 연결해 재배열하세요.",
            base_score=narrative_cohesion,
            evidence_key="relational_narrative",
            evidence_bank=evidence_bank,
            required_anchor_count=2,
            required_page_diversity=2,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(continuity_signals),
        ),
        _build_student_score_block(
            key="actionability_for_next_report",
            label="다음 보고서 실행 가능성",
            interpretation="진단 결과를 실제 탐구보고서 과제로 전환할 준비도를 평가합니다.",
            next_best_action="추천 축 중 1개를 선택해 1페이지 분량 실행 체크리스트를 작성하세요.",
            base_score=actionability_for_next_report,
            evidence_key="cluster_suitability",
            evidence_bank=evidence_bank,
            required_anchor_count=2,
            required_page_diversity=2,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(result.next_actions),
        ),
        _build_student_score_block(
            key="interview_explainability",
            label="면접 설명 가능성",
            interpretation="질문 상황에서 근거·과정·전공 연결을 명료하게 설명할 수 있는지를 평가합니다.",
            next_best_action="예상 질문 3개에 대해 근거 페이지를 포함한 2문장 답변 초안을 작성하세요.",
            base_score=interview_explainability,
            evidence_key="relational_narrative",
            evidence_bank=evidence_bank,
            required_anchor_count=2,
            required_page_diversity=2,
            page_diversity=len(unique_anchor_pages),
            coverage_score=float(coverage_check.get("coverage_score", 0.0) or 0.0),
            missing_required_count=len(missing_required_sections),
            contradiction_passed=contradiction_passed,
            support_signal_count=len(process_signals),
        ),
    ]

    system_blocks = [
        ConsultantDiagnosisScoreBlock(
            key="parse_coverage",
            label="파싱 커버리지",
            score=parse_coverage_score,
            band=_system_band(parse_coverage_score),
            interpretation="필수 항목 및 섹션 추출의 전반적 커버리지입니다.",
            uncertainty_note="필수 섹션 추출 결과를 기준으로 계산했습니다.",
            evidence_summary=f"필수 섹션 누락 {len(missing_required_sections)}건",
            missing_evidence=", ".join(missing_required_sections[:4]) if missing_required_sections else None,
            next_best_action="누락 섹션 원문을 재업로드하거나 OCR 품질을 점검하세요." if missing_required_sections else None,
        ),
        ConsultantDiagnosisScoreBlock(
            key="citation_coverage",
            label="인용 커버리지",
            score=citation_coverage_score,
            band=_system_band(citation_coverage_score),
            interpretation="문장-근거 연결에서 페이지 분산이 확보됐는지 평가합니다.",
            uncertainty_note="인용 페이지가 적으면 보수적으로 해석됩니다.",
            evidence_summary=f"인용 페이지 {len(unique_citation_pages)}개 / 앵커 페이지 {len(unique_anchor_pages)}개",
            missing_evidence=None if citation_coverage_score >= 60 else "핵심 주장 대비 인용 페이지가 부족합니다.",
            next_best_action="주장별 인용 페이지를 최소 1개 이상 연결하세요.",
        ),
        ConsultantDiagnosisScoreBlock(
            key="evidence_uniqueness",
            label="근거 고유성",
            score=evidence_uniqueness_score,
            band=_system_band(evidence_uniqueness_score),
            interpretation="동일 인용 반복 여부를 점검해 근거 다양성을 평가합니다.",
            uncertainty_note="고유성이 낮으면 반복형 주제 추천을 제한합니다.",
            evidence_summary=f"고유 인용 {len(unique_quotes)}개 / 전체 앵커 {len(evidence_bank)}개",
            missing_evidence=None if evidence_uniqueness_score >= 60 else "반복 인용 비율이 높습니다.",
            next_best_action="같은 문장 재활용 대신 다른 페이지 근거를 추가 확보하세요.",
        ),
        ConsultantDiagnosisScoreBlock(
            key="anchor_diversity",
            label="앵커 다양성",
            score=anchor_diversity_score,
            band=_system_band(anchor_diversity_score),
            interpretation="고유 앵커 수가 진단 신뢰도 기준을 충족하는지 평가합니다.",
            uncertainty_note="중요 축은 최소 10개 이상의 고유 앵커를 권장합니다.",
            evidence_summary=f"고유 앵커 {len(unique_anchor_ids)}개",
            missing_evidence=None if len(unique_anchor_ids) >= 10 else "고유 앵커가 10개 미만입니다.",
            next_best_action="핵심 축(엄밀성·구체성·전공연계) 기준 앵커를 우선 보강하세요.",
        ),
        ConsultantDiagnosisScoreBlock(
            key="page_diversity",
            label="페이지 다양성",
            score=page_diversity_score,
            band=_system_band(page_diversity_score),
            interpretation="특정 페이지만 과도하게 의존하지 않는지 평가합니다.",
            uncertainty_note="페이지 다양성 미달 시 점수는 reference-only로 간주합니다.",
            evidence_summary=f"고유 페이지 {len(unique_anchor_pages)}개",
            missing_evidence=None if len(unique_anchor_pages) >= 6 else "고유 페이지가 6개 미만입니다.",
            next_best_action="다른 학년/섹션 페이지로 근거 분산을 확대하세요.",
        ),
        ConsultantDiagnosisScoreBlock(
            key="section_coverage_reliability",
            label="섹션 커버리지 신뢰도",
            score=section_coverage_reliability_score,
            band=_system_band(section_coverage_reliability_score),
            interpretation="필수 섹션 누락 여부를 반영한 커버리지 신뢰도입니다.",
            uncertainty_note="누락 섹션이 존재하면 자동으로 보수 모드가 적용됩니다.",
            evidence_summary=f"누락 섹션 {len(missing_required_sections)}건",
            missing_evidence=", ".join(missing_required_sections[:5]) if missing_required_sections else None,
            next_best_action="누락 섹션의 원문 추출을 먼저 완료한 뒤 재진단하세요." if missing_required_sections else None,
        ),
        ConsultantDiagnosisScoreBlock(
            key="contradiction_check",
            label="모순 검증",
            score=contradiction_score,
            band=_system_band(contradiction_score),
            interpretation="누락/충분 판정 간 충돌 여부를 검사합니다.",
            uncertainty_note=None if contradiction_passed else "모순 감지로 premium 렌더를 차단합니다.",
            evidence_summary=f"모순 항목 {len(contradiction_check.get('items', []) if isinstance(contradiction_check.get('items'), list) else [])}건",
            missing_evidence=None if contradiction_passed else "구조 판정이 충돌합니다.",
            next_best_action="모순 섹션을 우선 정정한 뒤 다시 파싱하세요." if not contradiction_passed else None,
        ),
        ConsultantDiagnosisScoreBlock(
            key="redaction_safety",
            label="비식별 안전성",
            score=redaction_safety_score,
            band=_system_band(redaction_safety_score),
            interpretation="민감정보 노출 패턴 여부를 점검합니다.",
            uncertainty_note=None if redaction_safety_score >= 80 else "민감정보 패턴 감지로 검토가 필요합니다.",
            evidence_summary="전화번호/주민번호/이메일 패턴 검사 기준",
            missing_evidence=None if redaction_safety_score >= 80 else "민감정보가 포함된 원문이 있습니다.",
            next_best_action="민감정보를 비식별 처리한 뒤 재업로드하세요." if redaction_safety_score < 80 else None,
        ),
        ConsultantDiagnosisScoreBlock(
            key="reanalysis_requirement",
            label="재분석 필요도 게이트",
            score=reanalysis_requirement_score,
            band=_system_band(reanalysis_requirement_score),
            interpretation="현재 데이터 품질에서 즉시 활용 가능한지 여부를 나타냅니다.",
            uncertainty_note="reanalysis_required가 true이면 결과는 provisional로 표시됩니다." if reanalysis_required else None,
            evidence_summary=(
                "근거 게이트 통과"
                if not reanalysis_required
                else f"게이트 미통과(앵커:{len(unique_anchor_ids)}·페이지:{len(unique_anchor_pages)}·누락:{len(missing_required_sections)})"
            ),
            missing_evidence=None if not reanalysis_required else "게이트 조건을 충족하지 못했습니다.",
            next_best_action="게이트 조건을 충족한 뒤 최신 진단을 다시 생성하세요." if reanalysis_required else None,
        ),
        ConsultantDiagnosisScoreBlock(
            key="diagnosis_confidence_gate",
            label="진단 신뢰도 게이트",
            score=diagnosis_confidence_score,
            band=_system_band(diagnosis_confidence_score),
            interpretation="파싱/근거/안전성 지표를 종합한 진단 신뢰도입니다.",
            uncertainty_note="합격 예측 지표가 아닌 분석 신뢰도 지표입니다.",
            evidence_summary=(
                f"parse {parse_coverage_score} · citation {citation_coverage_score} · anchor {anchor_diversity_score}"
            ),
            missing_evidence=None if diagnosis_confidence_score >= 65 else "신뢰도 게이트가 낮아 결과 해석을 제한합니다.",
            next_best_action="신뢰도 65점 이상이 되도록 누락 섹션과 근거 밀도를 먼저 보완하세요.",
        ),
    ]

    student_group = ConsultantDiagnosisScoreGroup(
        group="student_evaluation",
        title="학생 평가 점수",
        blocks=student_blocks,
        gating_status="reanalysis_required" if reanalysis_required else "ok",
        note=(
            "reference-only: 근거 앵커/페이지 다양성 또는 필수 섹션 커버리지가 부족해 보수적으로 산출했습니다."
            if reanalysis_required
            else "학생 평가는 근거 앵커·페이지 분산·섹션 커버리지 게이트 통과 조건에서 산출했습니다."
        ),
    )
    system_group = ConsultantDiagnosisScoreGroup(
        group="system_quality",
        title="시스템 품질 점수",
        blocks=system_blocks,
        gating_status="blocked" if not contradiction_passed else ("reanalysis_required" if reanalysis_required else "ok"),
        note=(
            "모순 검증 실패로 premium PDF 렌더를 차단합니다."
            if not contradiction_passed
            else "시스템 품질 점수는 학생 평가 점수와 분리해 진단 신뢰도만 평가합니다."
        ),
    )
    return [student_group, system_group]



def _select_anchor_ids_for_score(*, key: str, evidence_bank: list[dict[str, Any]]) -> list[str]:
    keyword_map: dict[str, tuple[str, ...]] = {
        "universal_rigor": ("학업", "성취", "교과", "세특", "과목", "성적"),
        "universal_specificity": ("구체성", "수치", "현상", "방법", "결과", "근거"),
        "relational_narrative": ("서사", "동기", "발전", "성장", "계기", "스토리"),
        "relational_continuity": ("심화", "확장", "연속", "연계", "지속", "흐름"),
        "cluster_depth": ("심층", "전문", "고급", "이론", "실험", "연구"),
        "cluster_suitability": ("적합", "전공", "진로", "관심", "지망", "목표"),
    }
    keywords = keyword_map.get(key, ())
    selected: list[str] = []
    for item in evidence_bank:
        quote = str(item.get("quote") or "")
        if keywords and not any(keyword in quote for keyword in keywords):
            continue
        anchor_id = str(item.get("anchor_id") or "").strip()
        if anchor_id and anchor_id not in selected:
            selected.append(anchor_id)
        if len(selected) >= 4:
            break
    if len(selected) >= 2:
        return selected

    for item in evidence_bank:
        anchor_id = str(item.get("anchor_id") or "").strip()
        if anchor_id and anchor_id not in selected:
            selected.append(anchor_id)
        if len(selected) >= 2:
            break
    return selected


def _redaction_safety_ok(evidence_bank: list[dict[str, Any]]) -> bool:
    pii_patterns = (
        re.compile(r"\b01[0-9][- ]?\d{3,4}[- ]?\d{4}\b"),
        re.compile(r"\b\d{6}[- ]?\d{7}\b"),
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    )
    for item in evidence_bank:
        quote = str(item.get("quote") or "")
        if any(pattern.search(quote) for pattern in pii_patterns):
            return False
    return True


def _collect_student_record_structure(documents: list[Any]) -> dict[str, Any]:
    section_density: dict[str, float] = {}
    weak_sections: list[str] = []
    timeline_signals: list[str] = []
    activity_clusters: list[str] = []
    alignment_signals: list[str] = []
    continuity_signals: list[str] = []
    process_signals: list[str] = []
    uncertain_items: list[str] = []
    coverage_check: dict[str, Any] = {
        "required_sections": [],
        "missing_required_sections": [],
        "coverage_score": 0.0,
        "reanalysis_required": False,
    }
    contradiction_check: dict[str, Any] = {"passed": True, "items": []}

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
            canonical_coverage = canonical.get("section_coverage")
            if isinstance(canonical_coverage, dict):
                coverage_check = {
                    "required_sections": list(canonical_coverage.get("section_counts", {}).keys())
                    if isinstance(canonical_coverage.get("section_counts"), dict)
                    else coverage_check.get("required_sections", []),
                    "missing_required_sections": list(canonical_coverage.get("missing_sections", []))
                    if isinstance(canonical_coverage.get("missing_sections"), list)
                    else coverage_check.get("missing_required_sections", []),
                    "coverage_score": max(
                        float(coverage_check.get("coverage_score", 0.0)),
                        float(canonical_coverage.get("coverage_score", 0.0) or 0.0),
                    ),
                    "reanalysis_required": bool(canonical_coverage.get("reanalysis_required"))
                    or bool(coverage_check.get("reanalysis_required")),
                }
            quality_gates = canonical.get("quality_gates")
            if isinstance(quality_gates, dict):
                if quality_gates.get("reanalysis_required"):
                    coverage_check["reanalysis_required"] = True
                missing_required = quality_gates.get("missing_required_sections")
                if isinstance(missing_required, list):
                    merged_missing = _dedupe(
                        [
                            *[str(item) for item in coverage_check.get("missing_required_sections", [])],
                            *[str(item) for item in missing_required],
                        ],
                        limit=20,
                    )
                    coverage_check["missing_required_sections"] = merged_missing

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
            coverage_candidate = structure.get("coverage_check")
            if isinstance(coverage_candidate, dict):
                coverage_check["coverage_score"] = max(
                    float(coverage_check.get("coverage_score", 0.0)),
                    float(coverage_candidate.get("coverage_score", 0.0) or 0.0),
                )
                if bool(coverage_candidate.get("reanalysis_required")):
                    coverage_check["reanalysis_required"] = True
                if isinstance(coverage_candidate.get("required_sections"), list):
                    coverage_check["required_sections"] = _dedupe(
                        [*coverage_check.get("required_sections", []), *coverage_candidate.get("required_sections", [])],
                        limit=30,
                    )
                if isinstance(coverage_candidate.get("missing_required_sections"), list):
                    coverage_check["missing_required_sections"] = _dedupe(
                        [*coverage_check.get("missing_required_sections", []), *coverage_candidate.get("missing_required_sections", [])],
                        limit=30,
                    )
            contradiction_candidate = structure.get("contradiction_check")
            if isinstance(contradiction_candidate, dict):
                contradiction_check["passed"] = bool(contradiction_candidate.get("passed", True)) and bool(
                    contradiction_check.get("passed", True)
                )
                candidate_items = contradiction_candidate.get("items")
                if isinstance(candidate_items, list):
                    contradiction_check["items"] = [*contradiction_check.get("items", []), *candidate_items]

        pdf_analysis = metadata.get("pdf_analysis")
        if isinstance(pdf_analysis, dict):
            uncertain_items.extend([str(item).strip() for item in pdf_analysis.get("evidence_gaps", []) if str(item).strip()])

    normalized_weak_sections = _dedupe([_normalize_section_name(str(item)) for item in weak_sections], limit=20)
    filtered_weak_sections: list[str] = []
    contradiction_items: list[dict[str, Any]] = list(contradiction_check.get("items", []))
    for section in normalized_weak_sections:
        density = float(section_density.get(section, 0.0))
        if density >= 0.95:
            contradiction_items.append(
                {
                    "section": section,
                    "density": round(density, 3),
                    "reason": "weak_or_missing_conflicts_with_density",
                }
            )
            continue
        filtered_weak_sections.append(section)
    contradiction_check["items"] = contradiction_items
    contradiction_check["passed"] = bool(contradiction_check.get("passed", True)) and len(contradiction_items) == 0

    return {
        "section_density": section_density,
        "weak_sections": _dedupe(filtered_weak_sections, limit=12),
        "timeline_signals": _dedupe(timeline_signals, limit=12),
        "activity_clusters": _dedupe(activity_clusters, limit=12),
        "subject_major_alignment_signals": _dedupe(alignment_signals, limit=12),
        "continuity_signals": _dedupe(continuity_signals, limit=10),
        "process_reflection_signals": _dedupe(process_signals, limit=10),
        "uncertain_items": _dedupe(uncertain_items, limit=12),
        "coverage_check": coverage_check,
        "contradiction_check": contradiction_check,
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
        "coverage_check": {
            "required_sections": list((canonical.get("section_coverage") or {}).get("section_counts", {}).keys())
            if isinstance((canonical.get("section_coverage") or {}).get("section_counts"), dict)
            else [],
            "missing_required_sections": list((canonical.get("quality_gates") or {}).get("missing_required_sections", []))
            if isinstance((canonical.get("quality_gates") or {}).get("missing_required_sections"), list)
            else list((canonical.get("section_coverage") or {}).get("missing_sections", []))
            if isinstance((canonical.get("section_coverage") or {}).get("missing_sections"), list)
            else [],
            "coverage_score": float((canonical.get("section_coverage") or {}).get("coverage_score", 0.0) or 0.0),
            "reanalysis_required": bool((canonical.get("quality_gates") or {}).get("reanalysis_required"))
            or bool((canonical.get("section_coverage") or {}).get("reanalysis_required")),
        },
        "contradiction_check": {
            "passed": True,
            "items": [],
        },
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
    evidence_bank: list[dict[str, Any]] | None = None,
) -> list[str]:
    notes: list[str] = []
    coverage_check = (
        document_structure.get("coverage_check")
        if isinstance(document_structure.get("coverage_check"), dict)
        else {}
    )
    contradiction_check = (
        document_structure.get("contradiction_check")
        if isinstance(document_structure.get("contradiction_check"), dict)
        else {"passed": True, "items": []}
    )
    effective_evidence_bank = evidence_bank or []
    unique_anchor_ids = {
        str(item.get("anchor_id") or "").strip()
        for item in effective_evidence_bank
        if str(item.get("anchor_id") or "").strip()
    }
    unique_pages = {
        int(item.get("page") or 0)
        for item in effective_evidence_bank
        if int(item.get("page") or 0) > 0
    }
    citation_pages = {int(item.page_number or 0) for item in evidence_items if int(item.page_number or 0) > 0}

    notes.append("검증 원칙: 공식 학생부 근거가 약한 내용은 추론으로만 표기합니다.")
    if result.document_quality and result.document_quality.needs_review:
        notes.append("문서 품질 검토가 필요합니다. 누락 페이지와 섹션 구조를 다시 확인해 주세요.")
    if not evidence_items:
        notes.append("직접 인용 가능한 근거가 부족합니다. 주요 주장마다 원문 출처를 보강해 주세요.")
    if unique_anchor_ids and len(unique_anchor_ids) < 10:
        notes.append(f"고유 앵커가 {len(unique_anchor_ids)}개로 기준(10개) 미달입니다. 점수는 reference-only로 해석하세요.")
    if unique_pages and len(unique_pages) < 6:
        notes.append(f"고유 페이지가 {len(unique_pages)}개로 기준(6개) 미달입니다. 페이지 분산을 확대해 주세요.")
    if citation_pages and len(citation_pages) < 5:
        notes.append("인용 페이지 분산이 낮아 핵심 주장 일부는 추론으로 분류됩니다.")
    if result.review_required:
        notes.append("정합성/안전성 플래그가 감지되어 보수적 해석 상태로 전환되었습니다.")
    if bool(coverage_check.get("reanalysis_required")):
        missing = coverage_check.get("missing_required_sections")
        if isinstance(missing, list) and missing:
            notes.append(f"필수 섹션 누락: {', '.join(str(item) for item in missing[:6])}")
        else:
            notes.append("필수 섹션 커버리지가 낮아 보완이 필요합니다.")
    if not bool(contradiction_check.get("passed", True)):
        notes.append("모순 검증 실패: 누락 상태와 과다 상태가 충돌하여 보수 모드로 전환되었습니다.")
    if not bool(contradiction_check.get("passed", True)) or bool(coverage_check.get("reanalysis_required")):
        notes.append("현재 결과는 provisional 진단이며, 재파싱/재검증 후 최종본으로 확정해야 합니다.")
    for item in document_structure.get("uncertain_items", [])[:4]:
        notes.append(f"구조 추정 불확실: {item}")
    if not notes:
        notes.append("현재 근거 범위 안에서 보수적으로 해석했습니다. 신규 사실은 추가 검증 후 반영해 주세요.")
    return _dedupe(notes, limit=10)


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
        immediate_actions = ["현재 개요에서 근거가 약한 문장 3개를 선택해 출처 라인을 명시해 주세요."]

    mid_actions = _dedupe(
        [f"보완 과제: {gap.title} - {gap.description}" for gap in result.detailed_gaps or []],
        limit=4,
    )
    if not mid_actions:
        mid_actions = _dedupe(result.gaps, limit=3)
    if not mid_actions:
        mid_actions = ["탐구 연속성을 보여주는 후속 활동 계획을 작성하고 기록해 주세요."]

    long_actions = _dedupe(
        [f"주제 확장: {topic}" for topic in result.recommended_topics or []],
        limit=4,
    )
    if not long_actions:
        long_actions = ["목표 전공 연계성이 높은 1개 주제를 선정해 심화 보고서 초안을 완성해 주세요."]

    return [
        ConsultantDiagnosisRoadmapItem(
            horizon="1_month",
            title="1개월: 근거 정합성 정리",
            actions=immediate_actions,
            success_signals=[
                "핵심 주장-근거 매핑표 완성",
                "근거 미확인 문장은 '추가 확인 필요'로 명시",
            ],
            caution_notes=uncertainty_notes[:2],
        ),
        ConsultantDiagnosisRoadmapItem(
            horizon="3_months",
            title="3개월: 보완 축 집중 개선",
            actions=mid_actions,
            success_signals=[
                "약점 축(연속성·근거 밀도·과정 설명력) 최소 1개 이상 개선 확인",
                "정량 혹은 관찰 근거가 포함된 사례 추가",
            ],
            caution_notes=["활동 사실을 과장하지 말고 실제 수행 범위만 기록"],
        ),
        ConsultantDiagnosisRoadmapItem(
            horizon="6_months",
            title="6개월: 전공 적합성 스토리 완성",
            actions=long_actions,
            success_signals=[
                "전공-교과-활동 연결 문장이 자연스럽게 이어짐",
                "최종 보고서 초안에서 미검증 주장 비율 감소",
            ],
            caution_notes=["합격 가능성 단정 문구 금지", "검증 불가 사실은 보류"],
        ),
    ]


def _build_diagnosis_intelligence(
    *,
    result: DiagnosisResultPayload,
    document_structure: dict[str, Any],
    evidence_bank: list[dict[str, Any]],
    evidence_items: list[ConsultantDiagnosisEvidenceItem],
) -> dict[str, Any]:
    section_density = (
        document_structure.get("section_density")
        if isinstance(document_structure.get("section_density"), dict)
        else {}
    )
    strong_sections = sorted(
        [
            (str(section).strip(), float(density))
            for section, density in section_density.items()
            if str(section).strip() and float(density or 0.0) >= 0.66
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    weak_sections = [str(item).strip() for item in document_structure.get("weak_sections", []) if str(item).strip()]
    continuity_signals = [str(item).strip() for item in document_structure.get("continuity_signals", []) if str(item).strip()]
    alignment_signals = [
        str(item).strip()
        for item in document_structure.get("subject_major_alignment_signals", [])
        if str(item).strip()
    ]
    process_signals = [
        str(item).strip()
        for item in document_structure.get("process_reflection_signals", [])
        if str(item).strip()
    ]

    unique_anchor_ids = {
        str(item.get("anchor_id") or "").strip()
        for item in evidence_bank
        if str(item.get("anchor_id") or "").strip()
    }
    unique_pages = {
        int(item.get("page") or 0)
        for item in evidence_bank
        if int(item.get("page") or 0) > 0
    }
    citation_pages = {int(item.page_number or 0) for item in evidence_items if int(item.page_number or 0) > 0}
    unique_quotes = {
        str(item.get("quote") or "").strip()
        for item in evidence_bank
        if str(item.get("quote") or "").strip()
    }
    coverage_check = (
        document_structure.get("coverage_check")
        if isinstance(document_structure.get("coverage_check"), dict)
        else {}
    )
    missing_required_sections = [
        str(item).strip()
        for item in coverage_check.get("missing_required_sections", [])
        if str(item).strip()
    ] if isinstance(coverage_check.get("missing_required_sections"), list) else []

    missing_dimensions: list[str] = []
    if len(unique_anchor_ids) < 10 or len(unique_pages) < 6 or len(citation_pages) < 5:
        missing_dimensions.append("측정 가능한 근거 밀도")
    if len(process_signals) < 2:
        missing_dimensions.append("과정 설명력")
    if len(continuity_signals) < 2:
        missing_dimensions.append("학년 간 연속성")
    if len(alignment_signals) < 2:
        missing_dimensions.append("전공 연계 해석")
    if len(unique_quotes) < max(8, len(evidence_bank) // 2):
        missing_dimensions.append("차별성(반복 최소화)")
    if missing_required_sections:
        missing_dimensions.append("필수 섹션 커버리지")
    missing_dimensions = _dedupe(missing_dimensions, limit=6)

    recommended_reinforcement_axes = _dedupe(
        [
            "근거 밀도 보강",
            "과정 설명 정밀화",
            "전공 연결 문장 강화",
            "학년 간 연속성 명확화",
            *[f"{item} 보완" for item in missing_dimensions[:3]],
        ],
        limit=5,
    )
    safe_reinforcement_points = _dedupe(
        [
            *(f"{section}는 이미 밀도가 높아 확장 근거로 활용하기 좋습니다." for section, _ in strong_sections[:3]),
            "새 활동을 지어내기보다 기존 활동의 맥락·한계·개선을 구체화하는 방식이 안전합니다.",
            *(f"{signal} 축은 기존 기록 흐름과 무리 없이 이어질 수 있습니다." for signal in alignment_signals[:2]),
        ],
        limit=5,
    )
    best_report_styles_now = _dedupe(
        [
            "verification_comparison_type",
            "extension_deepening_type" if len(continuity_signals) < 3 else "application_design_type",
            "problem_solving_type" if len(process_signals) < 3 else "interdisciplinary_connection_type",
        ],
        limit=3,
    )
    style_labels = {
        "verification_comparison_type": "검증/비교형",
        "extension_deepening_type": "확장/심화형",
        "application_design_type": "적용/설계형",
        "problem_solving_type": "문제해결형",
        "interdisciplinary_connection_type": "융합 연결형",
    }

    recommended_report_directions: list[dict[str, Any]] = []
    for direction in result.recommended_directions:
        topics = list(direction.topic_candidates or [])
        if not topics:
            topics = [
                type("TopicLike", (), {"title": direction.label, "summary": direction.summary, "why_it_fits": direction.why_now, "evidence_hooks": []})()
            ]
        for topic in topics:
            if len(recommended_report_directions) >= 5:
                break
            existing_evidence = [str(item).strip() for item in getattr(topic, "evidence_hooks", []) if str(item).strip()]
            if not existing_evidence:
                existing_evidence = [section for section, _ in strong_sections[:2]] or ["기존 학생부 핵심 활동"]
            compensate_for = (
                missing_dimensions[0]
                if missing_dimensions
                else "기록 연결성 강화"
            )
            new_evidence_to_collect = (
                "비교 근거(수치·관찰·변화)를 최소 2개 확보"
                if "근거" in compensate_for or "밀도" in compensate_for
                else "과정 선택 이유와 한계/개선 메모를 1개 이상 확보"
            )
            recommended_report_directions.append(
                {
                    "title": _clean_line(str(getattr(topic, "title", direction.label)), max_len=90),
                    "why_it_fits_current_record": _clean_line(
                        str(getattr(topic, "why_it_fits", direction.why_now or direction.summary)),
                        max_len=180,
                    ),
                    "compensates_weak_point": compensate_for,
                    "existing_evidence": existing_evidence[:3],
                    "new_evidence_to_collect": new_evidence_to_collect,
                    "overclaim_guardrail": "합격·수상 확정 표현은 금지하고, 확인 가능한 사실만 기술합니다.",
                }
            )
        if len(recommended_report_directions) >= 5:
            break

    if len(recommended_report_directions) < 3:
        for topic in result.recommended_topics[:5]:
            if len(recommended_report_directions) >= 5:
                break
            recommended_report_directions.append(
                {
                    "title": _clean_line(str(topic), max_len=90),
                    "why_it_fits_current_record": "현재 기록의 관심축과 자연스럽게 연결되며 과장 위험을 통제하기 쉽습니다.",
                    "compensates_weak_point": missing_dimensions[0] if missing_dimensions else "연결성 보완",
                    "existing_evidence": [section for section, _ in strong_sections[:2]] or ["기존 교과·활동 기록"],
                    "new_evidence_to_collect": "근거 페이지와 관찰/과정 메모를 함께 확보",
                    "overclaim_guardrail": "새로운 성과를 단정하지 말고 기존 기록 근거로만 서술합니다.",
                }
            )

    avoid_report_directions = _dedupe(
        [
            "기존 문장을 거의 반복하는 요약형 주제",
            "근거 없이 결과를 크게 확장하는 성과 단정형 주제",
            "전공 연결이 약한 단발 체험 나열형 주제",
        ],
        limit=3,
    )
    high_overclaim_risk_claims = _dedupe(
        [
            "검증 근거 없이 전국/최상위 수준 성취를 단정하는 표현",
            "실제 수행 범위를 넘어서는 설계 완성도·성과를 서술하는 표현",
            "근거 없는 합격 가능성 또는 결과 예측 표현",
        ],
        limit=3,
    )

    return {
        "추천 보완 축": recommended_reinforcement_axes,
        "피해야 할 반복형 주제": avoid_report_directions,
        "지금 쓰면 좋은 탐구보고서 유형": [style_labels.get(item, item) for item in best_report_styles_now],
        "현재 기록에서 가장 안전하게 강화할 수 있는 포인트": safe_reinforcement_points,
        "추가 근거 없이는 과장 위험이 큰 주장": high_overclaim_risk_claims,
        "recommended_reinforcement_axes": recommended_reinforcement_axes,
        "avoid_repetitive_topics": avoid_report_directions,
        "best_report_styles_now": best_report_styles_now,
        "safe_reinforcement_points": safe_reinforcement_points,
        "high_overclaim_risk_claims": high_overclaim_risk_claims,
        "strong_sections_to_avoid_repeating": [section for section, _ in strong_sections[:4]],
        "weak_sections_to_complement": weak_sections[:6],
        "missing_dimensions": missing_dimensions,
        "recommended_report_directions": recommended_report_directions[:5],
        "avoid_report_directions": [
            {
                "title": title,
                "why_risky": "기록 차별성이 약하거나 근거 과장 위험이 높습니다.",
                "safer_alternative": "기존 근거를 재해석하는 보완형 탐구로 조정하세요.",
            }
            for title in avoid_report_directions[:3]
        ],
        "evidence_metrics": {
            "unique_anchor_count": len(unique_anchor_ids),
            "unique_page_count": len(unique_pages),
            "citation_page_count": len(citation_pages),
            "missing_required_sections": missing_required_sections[:8],
        },
    }


def _build_section_semantics(*, report_mode: DiagnosisReportMode) -> dict[str, str]:
    premium = {
        "cover_title_summary": "meta",
        "executive_verdict": "action",
        "record_baseline_dashboard": "verified",
        "student_evaluation_matrix": "verified",
        "system_quality_reliability": "verified",
        "strength_analysis": "verified",
        "weakness_risk_analysis": "uncertainty",
        "section_by_section_diagnosis": "verified",
        "major_fit_interpretation": "inferred",
        "recommended_report_directions": "action",
        "avoid_repetition_topics": "uncertainty",
        "evidence_cards": "verified",
        "interview_readiness": "inferred",
        "roadmap": "action",
        "uncertainty_verification_note": "uncertainty",
        "citation_appendix": "verified",
    }
    compact = {
        "executive_verdict": "action",
        "record_baseline_dashboard": "verified",
        "strength_analysis": "verified",
        "risk_analysis": "uncertainty",
        "recommended_report_direction": "action",
        "roadmap": "action",
        "uncertainty_verification_note": "uncertainty",
        "citation_appendix": "verified",
    }
    return premium if report_mode == "premium_10p" else compact


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
            "strengths_brief": "검증된 강점 요약 1-2문장",
            "weaknesses_risks_brief": "보완/리스크 요약 1-2문장",
            "major_fit_brief": "전공 적합성 요약 1-2문장",
            "section_diagnosis_brief": "섹션별 진단 해석 요약 1-2문장",
            "topic_strategy_brief": "주제 전략 요약 1-2문장",
            "roadmap_bridge": "1m/3m/6m 연결 문장 1개",
            "uncertainty_bridge": "불확실성 경계 문장 1개",
            "final_consultant_memo": "최종 실행 코멘트 3-4문장",
        },
    }

    try:
        registry = get_prompt_registry()
        system_instruction = registry.compose_prompt("diagnosis.consultant-report-orchestration")
        prompt = (
            f"{registry.compose_prompt('diagnosis.executive-summary-writer')}\n\n"
            f"{registry.compose_prompt('diagnosis.roadmap-generator')}\n\n"
            "[진단 컨텍스트 JSON]\n"
            f"{json.dumps(context_payload, ensure_ascii=False, indent=2)}"
        )
    except (PromptAssetNotFoundError, PromptRegistryError) as exc:
        logger.warning(
            "Prompt registry unavailable for consultant narratives. Deterministic fallback applied: %s",
            exc,
        )
        fallback_execution["fallback_reason"] = "prompt_registry_unavailable"
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
    density_focus = ", ".join(f"{k}:{int(float(v) * 100)}%" for k, v in list(section_density.items())[:3]) if section_density else "섹션별 밀도 정보가 제한적입니다."

    executive_summary = _guardrail_text(
        narrative.executive_summary,
        fallback=(
            f"현재 진단 기준에서 확인된 핵심 강점은 '{verified_strength}'입니다. "
            f"우선 보완축은 '{primary_gap}'이며, 문장-근거 정합성 개선이 필요합니다. "
            "검증이 부족한 항목은 '추가 확인 필요'로 분리하여 과장 위험을 차단합니다."
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
            fallback=f"현재 기록 상태는 '{result.recommended_focus or '근거 밀도 보강'}' 축을 우선 정리해야 합니다.",
            max_len=360,
        ),
        strengths_brief=_guardrail_text(
            narrative.strengths_brief,
            fallback=f"확인된 강점은 '{verified_strength}'이며 근거 연결성을 유지해야 합니다.",
            max_len=360,
        ),
        weaknesses_risks_brief=_guardrail_text(
            narrative.weaknesses_risks_brief,
            fallback=f"핵심 리스크는 '{primary_gap}'이고 취약 섹션은 {', '.join(weak_sections[:3]) or '추가 확인 필요 항목'}입니다.",
            max_len=360,
        ),
        major_fit_brief=_guardrail_text(
            narrative.major_fit_brief,
            fallback=f"전공 적합성 해석은 '{major_fit_seed}' 근거를 기준으로 보수적으로 제시합니다.",
            max_len=360,
        ),
        section_diagnosis_brief=_guardrail_text(
            narrative.section_diagnosis_brief,
            fallback=f"섹션별 진단 기준 핵심 지표는 {density_focus} 입니다.",
            max_len=360,
        ),
        topic_strategy_brief=_guardrail_text(
            narrative.topic_strategy_brief,
            fallback=f"주제 전략은 '{(result.recommended_topics or ['전공 연계 심화 주제'])[0]}' 중심으로 연계와 확장을 권장합니다.",
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
    for forbidden in ("합격 보장", "무조건 합격", "확정 합격", "반드시 합격", "전액 선행"):
        text = text.replace(forbidden, "검증 필요")
    if len(text) > max_len:
        text = f"{text[: max_len - 3].rstrip()}..."
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
                body_markdown="- 구조 완결성을 위해 기본 섹션 텍스트를 제공합니다.\n- 근거가 부족한 항목은 추가 확인 필요로 관리합니다.",
            )
        )
    return ordered


def _humanize_section_title(section_id: str) -> str:
    title_map = {
        "cover_title_summary": "표지 / 요약",
        "executive_verdict": "핵심 판정",
        "record_baseline_dashboard": "학업·기록 베이스라인 대시보드",
        "student_evaluation_matrix": "학생 평가 점수 매트릭스",
        "system_quality_reliability": "시스템 품질·신뢰도",
        "section_by_section_diagnosis": "섹션별 학생부 진단",
        "major_fit_interpretation": "전공 적합성 해석",
        "recommended_report_directions": "추천 탐구보고서 방향",
        "recommended_report_direction": "추천 탐구보고서 방향",
        "avoid_repetition_topics": "피해야 할 반복형 주제",
        "interview_readiness": "면접·설명 준비도",
        "uncertainty_verification_note": "불확실성·검증 메모",
        "citation_appendix": "근거/출처 요약",
        "executive_summary": "핵심 요약",
        "narrative_timeline": "서사 타임라인",
        "evidence_cards": "근거 카드",
        "strength_analysis": "강점 분석",
        "risk_analysis": "리스크 분석",
        "weakness_risk_analysis": "약점·리스크 분석",
        "major_fit": "목표 전공 적합성 해석",
        "interview_questions": "면접 예상 질문",
        "roadmap": "실행 로드맵",
    }
    return title_map.get(section_id, section_id)


def _build_fallback_executive_summary(*, result: DiagnosisResultPayload) -> str:
    strength = result.strengths[0] if result.strengths else "현재 기록에서는 사용 가능한 기본 강점이 확인됩니다."
    gap = result.gaps[0] if result.gaps else "다음 단계에서는 근거 밀도와 과정 설명을 우선 보완해야 합니다."
    return (
        f"본 진단은 '{result.headline}'를 중심으로 학생부 근거를 점검했습니다. "
        f"확인된 강점은 '{strength}'이며, 핵심 보완축은 '{gap}'입니다. "
        "현재 단계에서는 검증 가능한 근거를 중심으로 개요를 안정화하고, "
        "근거가 약한 문장은 '추가 확인 필요'로 표기해 과장 가능성을 차단해야 합니다."
    )


def _build_fallback_final_memo(*, result: DiagnosisResultPayload) -> str:
    focus = result.recommended_focus or "근거 연결 강화"
    next_step = result.next_actions[0] if result.next_actions else "개요의 다음 문단 1개를 근거 중심으로 시작"
    return (
        "최종 코멘트입니다. 현재 자료만으로도 방향성은 충분히 도출됩니다. "
        f"다만 '{focus}'를 우선 과제로 두고, '{next_step}'를 실행해 문장-근거 정합성을 먼저 높여야 합니다. "
        "합격 보장 문구나 검증되지 않은 사실 서술은 배제하고, 근거가 명확한 문장부터 완성도를 높여 주세요."
    )


def _build_sections(
    *,
    result: DiagnosisResultPayload,
    report_mode: DiagnosisReportMode,
    target_context: str,
    evidence_items: list[ConsultantDiagnosisEvidenceItem],
    score_groups: list[ConsultantDiagnosisScoreGroup],
    document_structure: dict[str, Any],
    evidence_bank: list[dict[str, Any]],
    roadmap: list[ConsultantDiagnosisRoadmapItem],
    narratives: _ConsultantNarrativePayload,
    uncertainty_notes: list[str],
    reanalysis_required: bool,
    diagnosis_intelligence: dict[str, Any],
) -> list[ConsultantDiagnosisSection]:
    top_citations = _build_diverse_evidence_items(
        evidence_items=evidence_items,
        evidence_bank=evidence_bank,
        limit=24,
    )
    if not top_citations:
        top_citations = evidence_items[:10]
    evidence_cursor = 0

    def pick_evidence(count: int) -> list[ConsultantDiagnosisEvidenceItem]:
        nonlocal evidence_cursor
        if count <= 0 or not top_citations:
            return []
        window_size = min(count, len(top_citations))
        selected = [
            top_citations[(evidence_cursor + offset) % len(top_citations)]
            for offset in range(window_size)
        ]
        evidence_cursor = (evidence_cursor + count) % len(top_citations)
        return selected

    weak_sections = [str(item).strip() for item in document_structure.get("weak_sections", []) if str(item).strip()]
    timeline_signals = [str(item).strip() for item in document_structure.get("timeline_signals", []) if str(item).strip()]
    alignment_signals = [str(item).strip() for item in document_structure.get("subject_major_alignment_signals", []) if str(item).strip()]
    continuity_signals = [str(item).strip() for item in document_structure.get("continuity_signals", []) if str(item).strip()]
    process_signals = [str(item).strip() for item in document_structure.get("process_reflection_signals", []) if str(item).strip()]
    coverage_check = (
        document_structure.get("coverage_check")
        if isinstance(document_structure.get("coverage_check"), dict)
        else {}
    )
    section_density = (
        document_structure.get("section_density")
        if isinstance(document_structure.get("section_density"), dict)
        else {}
    )

    student_score_group = next((group for group in score_groups if group.group == "student_evaluation"), None)
    system_score_group = next((group for group in score_groups if group.group == "system_quality"), None)
    student_matrix_lines = [
        f"{block.label}: {block.score}점 ({block.band}) | {block.evidence_summary or '근거 요약 없음'}"
        for block in (student_score_group.blocks if student_score_group else [])
    ]
    system_matrix_lines = [
        f"{block.label}: {block.score}점 ({block.band}) | {block.uncertainty_note or block.interpretation}"
        for block in (system_score_group.blocks if system_score_group else [])
    ]

    evidence_cards = evidence_bank[:8]
    evidence_card_lines: list[str] = []
    for idx, card in enumerate(evidence_cards, start=1):
        quote = _clean_line(str(card.get("quote") or ""), max_len=90)
        interpretation = _clean_line(str(card.get("theme") or "핵심 활동"), max_len=44)
        section = _clean_line(str(card.get("section") or "학생부"), max_len=24)
        risk_note = "한계 인식 확인" if bool((card.get("process_elements") or {}).get("limitation")) else "과정/한계 설명 보강 필요"
        evidence_card_lines.append(
            f"[근거 {idx}] {section} p.{card.get('page')} | {quote} | 해석: {interpretation} | 검증메모: {risk_note}"
        )

    section_diagnosis_lines: list[str] = []
    for section, density in sorted(
        section_density.items(),
        key=lambda item: float(item[1] or 0.0),
        reverse=True,
    ):
        normalized_density = max(0.0, min(1.0, float(density or 0.0)))
        status = "강점 구간" if normalized_density >= 0.66 else "보통 구간" if normalized_density >= 0.45 else "보완 우선"
        section_diagnosis_lines.append(
            f"{section}: 밀도 {int(round(normalized_density * 100))}% ({status})"
        )

    recommended_directions = (
        diagnosis_intelligence.get("recommended_report_directions")
        if isinstance(diagnosis_intelligence.get("recommended_report_directions"), list)
        else []
    )
    recommended_direction_lines: list[str] = []
    for idx, item in enumerate(recommended_directions[:5], start=1):
        if not isinstance(item, dict):
            continue
        recommended_direction_lines.extend(
            [
                f"[추천 {idx}] {item.get('title') or '추천 방향'}",
                f"- 적합 이유: {item.get('why_it_fits_current_record') or '기존 기록과의 연결성이 높습니다.'}",
                f"- 보완 축: {item.get('compensates_weak_point') or '기록 연결성 강화'}",
                f"- 기존 근거: {', '.join(item.get('existing_evidence') or ['학생부 핵심 활동'])}",
                f"- 추가로 필요한 근거: {item.get('new_evidence_to_collect') or '관찰/과정 근거 보강'}",
                f"- 과장 주의: {item.get('overclaim_guardrail') or '검증되지 않은 성과 단정 금지'}",
            ]
        )

    avoid_directions = (
        diagnosis_intelligence.get("avoid_report_directions")
        if isinstance(diagnosis_intelligence.get("avoid_report_directions"), list)
        else []
    )
    avoid_direction_lines: list[str] = []
    for idx, item in enumerate(avoid_directions[:3], start=1):
        if not isinstance(item, dict):
            continue
        avoid_direction_lines.extend(
            [
                f"[회피 {idx}] {item.get('title') or '반복형 주제'}",
                f"- 위험 이유: {item.get('why_risky') or '근거 대비 반복/과장 위험이 높습니다.'}",
                f"- 대안: {item.get('safer_alternative') or '기존 근거를 재해석하는 보완형 탐구로 조정'}",
            ]
        )

    interview_questions = _dedupe(
        [
            "현재 기록에서 가장 강한 근거 1개를 선택해 전공과의 연결을 2문장으로 설명해 보세요.",
            "활동 과정에서 무엇을 선택했고 왜 그렇게 판단했는지 한계까지 포함해 설명해 보세요.",
            "학년 간 연속성이 가장 잘 보이는 사례와 부족한 사례를 각각 1개씩 말해 보세요.",
            "새 활동을 추가하지 않고도 기존 기록을 더 설득력 있게 보완할 방법은 무엇인가요?",
            *[f"근거 확인 질문: {signal}" for signal in continuity_signals[:2]],
        ],
        limit=8,
    )

    roadmap_lines: list[str] = []
    for item in roadmap:
        roadmap_lines.append(item.title)
        roadmap_lines.extend([f"- {action}" for action in item.actions[:3]])

    missing_required_sections = (
        [str(item).strip() for item in coverage_check.get("missing_required_sections", []) if str(item).strip()]
        if isinstance(coverage_check.get("missing_required_sections"), list)
        else []
    )
    one_line_verdict = (
        "현재 기록에서 확인되는 강점은 유효하지만, 근거 밀도와 섹션 커버리지를 보완해야 안정적 해석이 가능합니다."
        if reanalysis_required
        else "근거 분산과 전공 연결성은 확인되며, 다음 보고서는 보완 축 중심으로 설계하는 것이 안전합니다."
    )
    baseline_lines = [
        target_context,
        f"분석 신뢰도(진단 게이트): {int(round(float(coverage_check.get('coverage_score', 0.0)) * 100))}%",
        f"고유 앵커 수: {len({str(item.get('anchor_id') or '').strip() for item in evidence_bank if str(item.get('anchor_id') or '').strip()})}개",
        f"고유 페이지 수: {len({int(item.get('page') or 0) for item in evidence_bank if int(item.get('page') or 0) > 0})}개",
        f"필수 섹션 누락: {', '.join(missing_required_sections[:5]) or '없음'}",
    ]

    strength_lines = [
        *(result.strengths[:4] or ["현재 기록에서 확인되는 강점 진술이 제한적입니다."]),
        narratives.strengths_brief or "강점은 반드시 페이지 근거와 함께 제시해야 합니다.",
        *[
            f"반복 최소화 권고: {section}"
            for section in (diagnosis_intelligence.get("strong_sections_to_avoid_repeating") or [])[:2]
            if str(section).strip()
        ],
    ]
    risk_lines = [
        *(result.gaps[:4] or ["핵심 리스크 진술이 제한적입니다."]),
        narratives.weaknesses_risks_brief or "불확실한 구간은 단정 대신 검증 과제로 분리해야 합니다.",
        *(weak_sections[:3] or ["취약 섹션 정보가 제한적입니다."]),
        *[f"누락 차원: {item}" for item in (diagnosis_intelligence.get("missing_dimensions") or [])[:3]],
    ]
    major_fit_lines = [
        narratives.major_fit_brief or "전공 적합성은 확인되지만 연결 문장의 일관성 보강이 필요합니다.",
        *(alignment_signals[:3] or ["전공 연계 신호가 제한적이므로 관련 근거를 추가 확보해야 합니다."]),
        "아래 제안은 합격 예측이 아니라 기록 보완 전략입니다.",
    ]
    uncertainty_lines = _dedupe(
        [
            *(uncertainty_notes[:6] or ["현재 근거 범위에서 보수적으로 해석했습니다."]),
            (
                "reference-only: 파싱 커버리지 또는 근거 앵커 조건 미달로 임시 해석 상태입니다."
                if reanalysis_required
                else "verified-ready: 핵심 게이트를 통과했으나 불확실 항목은 별도 검증이 필요합니다."
            ),
            "검증된 사실과 추론 문장을 구분해 해석하세요.",
        ],
        limit=9,
    )

    citation_appendix_lines: list[str] = []
    for item in top_citations[:8]:
        source = _clean_line(item.source_label, max_len=42)
        page = f"p.{item.page_number}" if item.page_number else "p.-"
        citation_appendix_lines.append(
            f"{source} {page}: {_clean_line(item.excerpt, max_len=96)} ({item.support_status})"
        )
    if not citation_appendix_lines:
        citation_appendix_lines.append("출처 근거가 부족해 추가 확인이 필요합니다.")

    premium_sections = [
        ConsultantDiagnosisSection(
            id="cover_title_summary",
            title="표지 / 요약",
            subtitle="진단 목적과 해석 범위",
            body_markdown=_bulleted(
                [
                    target_context,
                    narratives.current_record_status_brief or "현재 진단은 학생부 근거 중심의 보수적 해석입니다.",
                    "본 문서는 합격 예측이 아니라 기록 보완 전략 문서입니다.",
                ]
            ),
            evidence_items=pick_evidence(2),
        ),
        ConsultantDiagnosisSection(
            id="executive_verdict",
            title="핵심 판정",
            subtitle="실행 우선순위 중심 요약",
            body_markdown=_bulleted(
                [
                    one_line_verdict,
                    f"우선 보완 축: {result.recommended_focus}",
                    *(result.next_actions[:3] or ["다음 행동 지시가 제한적입니다."]),
                    "합격 보장/단정 문구 없이 근거 중심으로만 해석합니다.",
                ]
            ),
            evidence_items=pick_evidence(3),
            additional_verification_needed=uncertainty_notes[:2] if reanalysis_required else [],
        ),
        ConsultantDiagnosisSection(
            id="record_baseline_dashboard",
            title="기록 베이스라인 대시보드",
            subtitle="근거 분산·커버리지·누락 섹션 현황",
            body_markdown=_bulleted(baseline_lines),
            evidence_items=pick_evidence(2),
            additional_verification_needed=missing_required_sections[:3],
        ),
        ConsultantDiagnosisSection(
            id="student_evaluation_matrix",
            title="학생 평가 점수 매트릭스",
            subtitle="다차원 학생 평가(근거 조건 포함)",
            body_markdown=_bulleted(student_matrix_lines[:14] or ["학생 평가 매트릭스가 비어 있습니다."]),
            evidence_items=pick_evidence(2),
            additional_verification_needed=[
                block.missing_evidence
                for block in (student_score_group.blocks if student_score_group else [])
                if block.missing_evidence
            ][:3],
        ),
        ConsultantDiagnosisSection(
            id="system_quality_reliability",
            title="시스템 품질 / 신뢰도",
            subtitle="파싱·검증 게이트",
            body_markdown=_bulleted(system_matrix_lines[:10] or ["시스템 품질 데이터가 없습니다."]),
            evidence_items=pick_evidence(2),
            additional_verification_needed=(
                [system_score_group.note] if system_score_group and system_score_group.note else []
            ),
        ),
        ConsultantDiagnosisSection(
            id="strength_analysis",
            title="강점 분석",
            subtitle="검증된 강점과 유지 전략",
            body_markdown=_bulleted(strength_lines),
            evidence_items=(
                [item for item in pick_evidence(4) if item.support_status == "verified"][:3]
                or pick_evidence(3)
            ),
        ),
        ConsultantDiagnosisSection(
            id="weakness_risk_analysis",
            title="약점 / 리스크 분석",
            subtitle="약한 축과 과장 위험 경계",
            body_markdown=_bulleted(risk_lines),
            evidence_items=pick_evidence(3),
            additional_verification_needed=uncertainty_notes[:3],
            unsupported_claims=list(diagnosis_intelligence.get("high_overclaim_risk_claims") or [])[:3],
        ),
        ConsultantDiagnosisSection(
            id="section_by_section_diagnosis",
            title="섹션별 학생부 진단",
            subtitle="섹션 밀도 기반 보완 우선순위",
            body_markdown=_bulleted(section_diagnosis_lines[:10] or ["섹션 분류 데이터가 제한적입니다."]),
            evidence_items=pick_evidence(3),
        ),
        ConsultantDiagnosisSection(
            id="major_fit_interpretation",
            title="전공 적합성 해석",
            subtitle="확인된 강점과 일반화 주의점",
            body_markdown=_bulleted(major_fit_lines),
            evidence_items=pick_evidence(3),
            additional_verification_needed=[
                "전공 적합성은 확정 판정이 아닌 현재 기록 기반 해석입니다.",
                *([_clean_line(item, max_len=90) for item in continuity_signals[:2]]),
            ][:3],
        ),
        ConsultantDiagnosisSection(
            id="recommended_report_directions",
            title="추천 탐구보고서 방향",
            subtitle="3~5개 안전한 추천 방향",
            body_markdown=_bulleted(
                recommended_direction_lines or ["추천 방향 데이터가 제한적이므로 기존 근거 재해석형 보고서를 우선 권장합니다."]
            ),
            evidence_items=pick_evidence(3),
        ),
        ConsultantDiagnosisSection(
            id="avoid_repetition_topics",
            title="피해야 할 반복형 주제",
            subtitle="반복/과장 위험 회피 가이드",
            body_markdown=_bulleted(
                avoid_direction_lines or ["반복형 주제 회피 데이터가 제한적입니다."]
            ),
            evidence_items=pick_evidence(2),
            unsupported_claims=list(diagnosis_intelligence.get("high_overclaim_risk_claims") or [])[:3],
        ),
        ConsultantDiagnosisSection(
            id="evidence_cards",
            title="근거 카드",
            subtitle="검증 근거 카드",
            body_markdown=_bulleted(evidence_card_lines or ["근거 카드 생성을 위한 앵커가 부족합니다."]),
            evidence_items=pick_evidence(4),
            additional_verification_needed=["근거 없는 추정 문장은 본문에서 분리해 주세요."],
        ),
        ConsultantDiagnosisSection(
            id="interview_readiness",
            title="면접/설명 준비도",
            subtitle="설명 가능한 문장 훈련 질문",
            body_markdown=_bulleted(interview_questions),
            evidence_items=pick_evidence(2),
        ),
        ConsultantDiagnosisSection(
            id="roadmap",
            title="실행 로드맵",
            subtitle="1개월 · 3개월 · 6개월",
            body_markdown=_bulleted(
                [
                    narratives.roadmap_bridge or "로드맵은 근거 보강 → 리스크 통제 → 전공 연결 완성 순서로 진행합니다.",
                    *roadmap_lines,
                ]
            ),
            evidence_items=pick_evidence(2),
        ),
        ConsultantDiagnosisSection(
            id="uncertainty_verification_note",
            title="불확실성 / 검증 메모",
            subtitle="검증된 사실·추론·불확실성 분리",
            body_markdown=_bulleted(uncertainty_lines),
            evidence_items=pick_evidence(1),
            additional_verification_needed=uncertainty_notes[:4],
        ),
        ConsultantDiagnosisSection(
            id="citation_appendix",
            title="근거·출처 요약",
            subtitle="주요 인용 앵커",
            body_markdown=_bulleted(citation_appendix_lines),
            evidence_items=pick_evidence(2),
        ),
    ]

    compact_sections = [
        ConsultantDiagnosisSection(
            id="executive_verdict",
            title="핵심 판정",
            subtitle="요약 결론",
            body_markdown=_bulleted(
                [
                    one_line_verdict,
                    f"최우선 보완 축: {result.recommended_focus}",
                    "아래 제안은 합격 예측이 아닌 기록 보완 전략입니다.",
                ]
            ),
            evidence_items=pick_evidence(2),
            additional_verification_needed=uncertainty_notes[:2] if reanalysis_required else [],
        ),
        ConsultantDiagnosisSection(
            id="record_baseline_dashboard",
            title="베이스라인 대시보드",
            subtitle="현재 상태 요약",
            body_markdown=_bulleted(
                [
                    *baseline_lines,
                    *(student_matrix_lines[:4] or ["학생 평가 매트릭스 요약 데이터가 제한적입니다."]),
                ]
            ),
            evidence_items=pick_evidence(2),
        ),
        ConsultantDiagnosisSection(
            id="strength_analysis",
            title="상위 강점",
            subtitle="유지/확장 포인트",
            body_markdown=_bulleted(strength_lines[:6]),
            evidence_items=pick_evidence(2),
        ),
        ConsultantDiagnosisSection(
            id="risk_analysis",
            title="상위 리스크",
            subtitle="보수적 보완 필요 구간",
            body_markdown=_bulleted(risk_lines[:7]),
            evidence_items=pick_evidence(2),
            additional_verification_needed=uncertainty_notes[:3],
            unsupported_claims=list(diagnosis_intelligence.get("high_overclaim_risk_claims") or [])[:2],
        ),
        ConsultantDiagnosisSection(
            id="recommended_report_direction",
            title="추천 다음 보고서 방향",
            subtitle="우선 적용 가능한 제안",
            body_markdown=_bulleted(recommended_direction_lines[:12] or ["추천 방향 정보를 생성하지 못했습니다."]),
            evidence_items=pick_evidence(2),
        ),
        ConsultantDiagnosisSection(
            id="roadmap",
            title="로드맵",
            subtitle="단기·중기·장기 실행",
            body_markdown=_bulleted(roadmap_lines[:10] or ["로드맵 데이터가 제한적입니다."]),
            evidence_items=pick_evidence(1),
        ),
        ConsultantDiagnosisSection(
            id="uncertainty_verification_note",
            title="불확실성 메모",
            subtitle="검증 필요 항목",
            body_markdown=_bulleted(uncertainty_lines[:7]),
            evidence_items=pick_evidence(1),
        ),
        ConsultantDiagnosisSection(
            id="citation_appendix",
            title="출처 요약",
            subtitle="핵심 근거 라인",
            body_markdown=_bulleted(citation_appendix_lines[:6]),
            evidence_items=pick_evidence(1),
        ),
    ]

    if report_mode == "compact":
        return compact_sections
    return premium_sections


def _build_diverse_evidence_items(
    *,
    evidence_items: list[ConsultantDiagnosisEvidenceItem],
    evidence_bank: list[dict[str, Any]],
    limit: int,
) -> list[ConsultantDiagnosisEvidenceItem]:
    candidates: list[ConsultantDiagnosisEvidenceItem] = [*evidence_items]
    for item in evidence_bank:
        quote = _clean_line(str(item.get("quote") or ""), max_len=230)
        if not quote:
            continue
        page_number = _coerce_positive_int(item.get("page"))
        anchor_id = str(item.get("anchor_id") or "").strip()
        section = str(item.get("section") or "").strip()
        confidence = _coerce_float(item.get("confidence"), default=0.7)
        support_status: str
        if confidence >= 0.8:
            support_status = "verified"
        elif confidence >= 0.55:
            support_status = "probable"
        else:
            support_status = "needs_verification"
        source_base = (
            f"학생부 앵커 {anchor_id}"
            if anchor_id
            else f"학생부 p.{page_number}"
            if page_number
            else "학생부 앵커"
        )
        source_label = f"{section} | {source_base}" if section else source_base
        candidates.append(
            ConsultantDiagnosisEvidenceItem(
                source_label=source_label,
                page_number=page_number,
                excerpt=quote,
                relevance_score=round(max(0.0, min(1.0, confidence)) * 2.0, 3),
                support_status=support_status,  # type: ignore[arg-type]
            )
        )

    deduped: list[ConsultantDiagnosisEvidenceItem] = []
    seen: set[tuple[str, int, str]] = set()
    for candidate in candidates:
        key = (
            str(candidate.source_label or "").strip(),
            int(candidate.page_number or 0),
            _clean_line(candidate.excerpt, max_len=90),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    diversified: list[ConsultantDiagnosisEvidenceItem] = []
    seen_pages: set[int] = set()
    remainder: list[ConsultantDiagnosisEvidenceItem] = []
    for candidate in deduped:
        page_number = int(candidate.page_number or 0)
        if page_number > 0 and page_number not in seen_pages:
            diversified.append(candidate)
            seen_pages.add(page_number)
        else:
            remainder.append(candidate)
        if len(diversified) >= limit:
            return diversified[:limit]

    for candidate in remainder:
        diversified.append(candidate)
        if len(diversified) >= limit:
            break
    return diversified[:limit]


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
        quality_score = metadata.get("pipeline_quality_score")
        if isinstance(quality_score, (int, float)):
            notes.append(f"파이프라인 quality_score={round(float(quality_score), 3)}")
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
        title=f"{project.title} 전문 컨설턴트 진단",
        subtitle="생성 실패 - 제한 정보",
        student_target_context=f"프로젝트: {project.title}",
        generated_at=datetime.now(timezone.utc),
        score_blocks=[],
        sections=[
            ConsultantDiagnosisSection(
                id="generation_failed",
                title="진단서 생성 실패",
                subtitle=None,
                body_markdown="요청하신 진단서를 생성하지 못했습니다. 프로젝트 근거 문서를 확인한 뒤 다시 시도해 주세요.",
            )
        ],
        roadmap=[],
        citations=[],
        uncertainty_notes=["리포트 생성 실패로 상세 분석은 포함되지 않았습니다."],
        final_consultant_memo="근거 문서 상태를 확인한 뒤 재생성해 주세요.",
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
    return f"{text[: max_len - 3].rstrip()}..."


def _coerce_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:  # NaN guard
        return default
    return parsed


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


def _normalize_section_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    alias = {
        "grades_subjects": "교과학습발달상황",
        "grades_and_notes": "교과학습발달상황",
        "subject_special_notes": "세특",
        "creative_activities": "창체",
        "extracurricular": "창체",
        "volunteer": "창체",
        "career_signals": "진로",
        "reading": "독서",
        "reading_activity": "독서",
        "behavior_general_comments": "행동특성",
        "behavior_opinion": "행동특성",
    }
    return alias.get(text, text)
