from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from unifoli_api.core.config import get_settings
from unifoli_api.core.llm import GeminiClient, OllamaClient, get_llm_client
from unifoli_api.core.security import sanitize_public_error
from unifoli_api.db.models.diagnosis_run import DiagnosisRun
from unifoli_api.db.models.project import Project
from unifoli_api.db.models.response_trace import ResponseTrace
from unifoli_api.db.models.user import User
from unifoli_api.services.blueprint_service import build_blueprint_signals, create_blueprint_from_signals
from unifoli_api.services.diagnosis_scoring_service import (
    DiagnosisScoringSheet,
    build_diagnosis_scoring_sheet,
)
from unifoli_api.services.diagnosis_service import (
    DiagnosisGenerationError,
    DiagnosisCitation,
    attach_policy_flags_to_run,
    build_grounded_diagnosis_result,
    create_response_trace,
    detect_policy_flags,
    ensure_review_task_for_flags,
    evaluate_student_record,
    serialize_citation,
)
from unifoli_api.services.document_service import list_chunks_for_project, list_documents_for_project
from unifoli_api.services.project_service import get_project
from unifoli_api.services.student_record_feature_service import extract_student_record_features
from unifoli_shared.storage import get_storage_provider


RAW_POLICY_SCAN_EXTENSIONS = {".txt", ".md", ".csv", ".json"}
MAX_DOC_TEXT_CHARS = 42_000
MAX_COMBINED_TEXT_CHARS = 120_000
MAX_METADATA_SUMMARY_CHARS = 1_600
MAX_DIAGNOSIS_LLM_INPUT_CHARS = 30_000
MAX_SEMANTIC_INPUT_CHARS = 15_000
SEMANTIC_EXTRACTION_TIMEOUT_SECONDS = 60.0
DIAGNOSIS_GENERATION_TIMEOUT_SECONDS = 45.0

DIAGNOSIS_FALLBACK_REASON_TIMEOUT = "diagnosis_generation_timeout"
DIAGNOSIS_FALLBACK_REASON_PROVIDER_TIMEOUT = "diagnosis_generation_provider_timeout"
DIAGNOSIS_FALLBACK_REASON_CONNECTION_ISSUE = "diagnosis_generation_connection_issue"
DIAGNOSIS_FALLBACK_REASON_INVALID_JSON = "diagnosis_generation_invalid_json"
DIAGNOSIS_FALLBACK_REASON_INVALID_REQUEST = "diagnosis_generation_invalid_request"
DIAGNOSIS_FALLBACK_REASON_MODEL_NOT_FOUND = "diagnosis_generation_model_not_found"
DIAGNOSIS_FALLBACK_REASON_PROVIDER_ERROR = "diagnosis_generation_provider_error"
DIAGNOSIS_FALLBACK_REASON_UNEXPECTED = "diagnosis_generation_unexpected_error"

logger = logging.getLogger("unifoli.api.diagnosis_runtime")


def _is_sqlite_disk_full_error(exc: Exception) -> bool:
    return "database or disk is full" in str(exc).lower()


def _extract_document_text(document: Any) -> str:
    primary = str(
        getattr(document, "content_text", "")
        or getattr(document, "content_markdown", "")
        or ""
    ).strip()
    if primary:
        return primary[:MAX_DOC_TEXT_CHARS]

    metadata = getattr(document, "parse_metadata", None)
    if not isinstance(metadata, dict):
        return ""

    canonical = metadata.get("student_record_canonical")
    if isinstance(canonical, dict):
        canonical_parts: list[str] = []
        confidence = canonical.get("document_confidence")
        if isinstance(confidence, (int, float)):
            canonical_parts.append(f"[student_record_confidence] {round(float(confidence), 3)}")

        for field, key in (
            ("timeline_signals", "signal"),
            ("major_alignment_hints", "hint"),
            ("uncertainties", "message"),
        ):
            items = canonical.get(field)
            if isinstance(items, list):
                for item in items[:6]:
                    if not isinstance(item, dict):
                        continue
                    value = str(item.get(key) or "").strip()
                    if value:
                        canonical_parts.append(f"- {value[:220]}")

        for field, key in (
            ("grades_subjects", "subject"),
            ("subject_special_notes", "label"),
            ("extracurricular", "label"),
            ("career_signals", "label"),
            ("reading_activity", "label"),
            ("behavior_opinion", "label"),
        ):
            items = canonical.get(field)
            if isinstance(items, list):
                for item in items[:4]:
                    if not isinstance(item, dict):
                        continue
                    value = str(item.get(key) or "").strip()
                    if value:
                        canonical_parts.append(f"- {value[:220]}")

        canonical_text = "\n".join(canonical_parts).strip()
        if canonical_text:
            return canonical_text[:MAX_DOC_TEXT_CHARS]

    pdf_analysis = metadata.get("pdf_analysis")
    if not isinstance(pdf_analysis, dict):
        return ""

    fallback_parts: list[str] = []
    summary = str(pdf_analysis.get("summary") or "").strip()
    if summary:
        fallback_parts.append(summary[:MAX_METADATA_SUMMARY_CHARS])

    key_points = pdf_analysis.get("key_points")
    if isinstance(key_points, list):
        for item in key_points[:6]:
            normalized = str(item or "").strip()
            if normalized:
                fallback_parts.append(f"- {normalized[:220]}")

    return "\n".join(fallback_parts).strip()


def combine_project_text(project_id: str, db: Session) -> tuple[list[Any], str]:
    documents = list_documents_for_project(db, project_id)
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="진단 실행 전에 파싱이 완료된 문서를 먼저 업로드해 주세요.",
        )

    merged_parts: list[str] = []
    remaining_budget = MAX_COMBINED_TEXT_CHARS
    for document in documents:
        text = _extract_document_text(document)
        if not text:
            continue
        clipped = text[:remaining_budget].strip()
        if not clipped:
            continue
        merged_parts.append(clipped)
        remaining_budget -= len(clipped) + 2
        if remaining_budget <= 0:
            break

    full_text = "\n\n".join(merged_parts).strip()
    if not full_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파싱된 문서 내용이 비어 있습니다. 더 선명한 원본으로 다시 파싱해 주세요.",
        )
    return documents, full_text


def build_policy_scan_text(documents: list) -> str:
    parts: list[str] = []
    storage = get_storage_provider(get_settings())
    for document in documents:
        if document.content_text or document.content_markdown:
            parts.append(document.content_text or document.content_markdown or "")
        stored_path = getattr(document, "stored_path", None)
        source_extension = (getattr(document, "source_extension", "") or "").lower()
        if not stored_path or source_extension not in RAW_POLICY_SCAN_EXTENSIONS:
            continue
        try:
            raw_text = storage.retrieve(stored_path).decode("utf-8", errors="ignore")
        except Exception:
            continue
        if raw_text.strip():
            parts.append(raw_text)
    return "\n\n".join(part for part in parts if part).strip()


def get_run_with_relations(db: Session, run_id: str) -> DiagnosisRun | None:
    return db.scalar(
        select(DiagnosisRun)
        .where(DiagnosisRun.id == run_id)
        .options(
            selectinload(DiagnosisRun.policy_flags),
            selectinload(DiagnosisRun.review_tasks),
            selectinload(DiagnosisRun.response_traces).selectinload(ResponseTrace.citations),
        )
    )


def _diagnosis_llm_strategy() -> dict[str, Any]:
    settings = get_settings()
    requested_provider = (settings.llm_provider or "gemini").strip().lower()
    requested_model = (
        (settings.ollama_standard_model or settings.ollama_model or "gemma4").strip()
        if requested_provider == "ollama"
        else "gemini-1.5-pro"
    )
    base = {
        "requested_llm_provider": requested_provider,
        "requested_llm_model": requested_model,
        "llm_profile_used": "standard",
        "actual_llm_provider": None,
        "actual_llm_model": None,
        "should_use_llm": False,
        "fallback_used": True,
        "fallback_reason": "llm_unavailable",
    }

    try:
        llm = get_llm_client(profile="standard")
    except Exception as exc:  # noqa: BLE001
        base["fallback_reason"] = f"client_init_failed:{type(exc).__name__}"
        return base

    if isinstance(llm, OllamaClient):
        actual_provider = "ollama"
        actual_model = llm.model
    elif isinstance(llm, GeminiClient):
        actual_provider = "gemini"
        actual_model = llm.model_name
    else:
        actual_provider = requested_provider
        actual_model = requested_model

    provider_fallback_used = actual_provider != requested_provider or actual_model != requested_model
    return {
        **base,
        "actual_llm_provider": actual_provider,
        "actual_llm_model": actual_model,
        "should_use_llm": True,
        "fallback_used": provider_fallback_used,
        "fallback_reason": "provider_auto_fallback" if provider_fallback_used else None,
    }


def _merge_unique(items: list[str], extra: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for raw in [*items, *extra]:
        normalized = str(raw or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
        if len(merged) >= limit:
            break
    return merged


def _normalize_interest_universities(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    normalized = [str(item).strip() for item in values if str(item).strip()]
    return normalized or None


def _apply_structured_backbone(*, result, sheet: DiagnosisScoringSheet) -> None:  # noqa: ANN001
    result.overview = sheet.overview
    result.document_quality = sheet.document_quality
    result.section_analysis = sheet.section_analysis
    result.admission_axes = sheet.admission_axes
    result.risks = _merge_unique(sheet.risk_flags, getattr(result, "risks", []) or [], limit=10)
    result.next_actions = _merge_unique(sheet.next_action_seeds, getattr(result, "next_actions", []) or [], limit=10)
    result.recommended_topics = _merge_unique(
        sheet.recommended_topics,
        getattr(result, "recommended_topics", []) or [],
        limit=10,
    )
    result.strengths = _merge_unique(sheet.strengths_candidates, result.strengths, limit=8)
    result.gaps = _merge_unique(sheet.gap_candidates, result.gaps, limit=8)
    result.recommended_focus = sheet.recommended_focus or result.recommended_focus
    result.risk_level = sheet.risk_level


def _safe_db_rollback(db: Session) -> None:
    rollback = getattr(db, "rollback", None)
    if callable(rollback):
        rollback()


def _persist_run(db: Session, run: DiagnosisRun, *, commit: bool = True) -> None:
    db.add(run)
    if commit:
        db.commit()


def _update_run_status(
    db: Session,
    run: DiagnosisRun,
    *,
    status_message: str,
    status: str | None = None,
) -> None:
    if status is not None:
        run.status = status
    run.status_message = status_message
    _persist_run(db, run)


def _diagnosis_runtime_failure_message(exc: Exception) -> str:
    fallback = "진단 작업이 실패했습니다. 프로젝트 근거를 확인한 뒤 다시 시도해 주세요."
    normalized = sanitize_public_error(str(exc), fallback=fallback)
    lowered = normalized.lower()
    if "database is locked" in lowered:
        return "진단 저장소가 일시적으로 사용 중입니다. 잠시 후 다시 시도해 주세요."
    if "database or disk is full" in lowered:
        return "진단 저장소 용량이 일시적으로 포화 상태입니다. 잠시 후 다시 시도해 주세요."
    return normalized


def _resolve_diagnosis_generation_timeout_seconds() -> float:
    settings = get_settings()
    raw = getattr(settings, "diagnosis_generation_timeout_seconds", DIAGNOSIS_GENERATION_TIMEOUT_SECONDS)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = DIAGNOSIS_GENERATION_TIMEOUT_SECONDS
    if value <= 0:
        return DIAGNOSIS_GENERATION_TIMEOUT_SECONDS
    return value


def _normalize_generation_fallback_reason(exc: Exception) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return DIAGNOSIS_FALLBACK_REASON_TIMEOUT

    if isinstance(exc, DiagnosisGenerationError):
        code = str(exc.reason_code or "").strip().lower()
        if code == "provider_timeout":
            return DIAGNOSIS_FALLBACK_REASON_PROVIDER_TIMEOUT
        if code == "connection_issue":
            return DIAGNOSIS_FALLBACK_REASON_CONNECTION_ISSUE
        if code == "invalid_json":
            return DIAGNOSIS_FALLBACK_REASON_INVALID_JSON
        if code == "invalid_request":
            return DIAGNOSIS_FALLBACK_REASON_INVALID_REQUEST
        if code == "model_not_found":
            return DIAGNOSIS_FALLBACK_REASON_MODEL_NOT_FOUND
        if code == "provider_error":
            return DIAGNOSIS_FALLBACK_REASON_PROVIDER_ERROR
        return DIAGNOSIS_FALLBACK_REASON_UNEXPECTED

    name = type(exc).__name__.strip().lower()
    if "timeout" in name:
        return DIAGNOSIS_FALLBACK_REASON_PROVIDER_TIMEOUT
    if "notfound" in name or ("not" in name and "found" in name):
        return DIAGNOSIS_FALLBACK_REASON_MODEL_NOT_FOUND
    if "connection" in name or "connect" in name or "network" in name:
        return DIAGNOSIS_FALLBACK_REASON_CONNECTION_ISSUE
    if "json" in name or "decode" in name or "validation" in name:
        return DIAGNOSIS_FALLBACK_REASON_INVALID_JSON
    return DIAGNOSIS_FALLBACK_REASON_UNEXPECTED


async def run_diagnosis_run(
    db: Session,
    *,
    run_id: str,
    project_id: str,
    owner_user_id: str,
    fallback_target_university: str | None,
    fallback_target_major: str | None,
    interest_universities: list[str] | None = None,
) -> DiagnosisRun:
    run = get_run_with_relations(db, run_id)
    if run is None:
        raise ValueError(f"Diagnosis run not found: {run_id}")

    try:
        resolved_owner_user_id = owner_user_id.strip() or None
        if resolved_owner_user_id:
            project = get_project(db, project_id, owner_user_id=resolved_owner_user_id)
        else:
            project = db.get(Project, project_id)
        if project is None:
            raise ValueError("Project not found.")
        if not resolved_owner_user_id:
            resolved_owner_user_id = project.owner_user_id
        owner = db.get(User, resolved_owner_user_id) if resolved_owner_user_id else None
        if owner is None:
            raise ValueError("Project owner not found.")
        owner_interest_universities = getattr(owner, "interest_universities", None)
        resolved_interest_universities = _normalize_interest_universities(
            interest_universities if interest_universities is not None else owner_interest_universities
        )

        documents, full_text = combine_project_text(project_id, db)
        try:
            chunks = list_chunks_for_project(db, project_id)
        except OperationalError as exc:
            if not _is_sqlite_disk_full_error(exc):
                raise
            _safe_db_rollback(db)
            logger.warning(
                "Skipping chunk hydration due sqlite disk pressure. run_id=%s project_id=%s",
                run_id,
                project_id,
            )
            chunks = []
        started_at = time.perf_counter()

        policy_scan_text = build_policy_scan_text(documents) or full_text
        diagnosis_input_text = full_text[:MAX_DIAGNOSIS_LLM_INPUT_CHARS]
        semantic_input_text = full_text[:MAX_SEMANTIC_INPUT_CHARS]
        llm_strategy = _diagnosis_llm_strategy()
        should_use_llm = bool(llm_strategy.get("should_use_llm"))
        model_name = str(llm_strategy.get("actual_llm_model") or "grounded-fallback")
        generation_timeout_seconds = _resolve_diagnosis_generation_timeout_seconds()

        _update_run_status(
            db,
            run,
            status="RUNNING",
            status_message="업로드한 문서 근거를 점검하고 있습니다...",
        )
        findings = detect_policy_flags(policy_scan_text)
        flag_records = run.policy_flags
        review_task = run.review_tasks[0] if run.review_tasks else None
        if findings and not run.policy_flags:
            flag_records = attach_policy_flags_to_run(db, run=run, project=project, user=owner, findings=findings)
            review_task = ensure_review_task_for_flags(db, run=run, project=project, user=owner, findings=findings)

        target_major = fallback_target_major or project.target_major
        user_major = project.target_major or fallback_target_major or "일반 탐구"
        evidence_keys = [document.sha256 or document.id for document in documents if (document.sha256 or document.id)]

        _update_run_status(
            db,
            run,
            status_message="학생부 핵심 지표를 추출하고 있습니다...",
        )
        features = extract_student_record_features(
            documents=documents,
            full_text=full_text,
            target_major=target_major,
            career_direction=owner.career,
        )

        semantic_data = None
        if should_use_llm and semantic_input_text:
            from unifoli_api.services.diagnosis_scoring_service import extract_semantic_diagnosis

            _update_run_status(
                db,
                run,
                status_message="추출된 근거를 바탕으로 심화 의미 분석을 수행하고 있습니다...",
            )
            try:
                semantic_data = await asyncio.wait_for(
                    extract_semantic_diagnosis(
                        masked_text=semantic_input_text,
                        target_major=target_major or "일반 탐구",
                        target_university=fallback_target_university,
                        interest_universities=resolved_interest_universities,
                    ),
                    timeout=SEMANTIC_EXTRACTION_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Semantic extraction timed out for run %s after %.1fs",
                    run.id,
                    SEMANTIC_EXTRACTION_TIMEOUT_SECONDS,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Semantic extraction skipped for run %s: %s", run.id, exc)

        scoring_sheet = build_diagnosis_scoring_sheet(
            features=features,
            project_title=project.title,
            target_major=target_major,
            target_university=fallback_target_university,
            interest_universities=resolved_interest_universities,
            semantic=semantic_data,
        )

        if should_use_llm:
            _update_run_status(
                db,
                run,
                status_message="정밀 진단 내용을 생성하고 근거 데이터를 매핑하고 있습니다...",
            )
            try:
                result = await asyncio.wait_for(
                    evaluate_student_record(
                        user_major=user_major,
                        masked_text=diagnosis_input_text,
                        target_university=fallback_target_university,
                        target_major=target_major,
                        interest_universities=resolved_interest_universities,
                        career_direction=owner.career,
                        project_title=project.title,
                        scope_key=f"project:{project.id}",
                        evidence_keys=evidence_keys,
                        raise_on_llm_failure=True,
                    ),
                    timeout=generation_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                logger.warning(
                    "LLM diagnosis generation timed out for run %s after %.1fs",
                    run.id,
                    generation_timeout_seconds,
                )
                model_name = "grounded-fallback"
                llm_strategy["actual_llm_provider"] = "deterministic_fallback"
                llm_strategy["actual_llm_model"] = "grounded-fallback"
                llm_strategy["fallback_used"] = True
                llm_strategy["fallback_reason"] = DIAGNOSIS_FALLBACK_REASON_TIMEOUT
                result = build_grounded_diagnosis_result(
                    project_title=project.title,
                    target_major=target_major,
                    target_university=fallback_target_university,
                    interest_universities=resolved_interest_universities,
                    career_direction=owner.career,
                    document_count=len(documents),
                    full_text=diagnosis_input_text or full_text,
                )
            except Exception as exc:  # noqa: BLE001
                normalized_reason = _normalize_generation_fallback_reason(exc)
                logger.warning(
                    "LLM diagnosis failed for run %s. Falling back with reason=%s detail=%s",
                    run.id,
                    normalized_reason,
                    exc,
                )
                model_name = "grounded-fallback"
                llm_strategy["actual_llm_provider"] = "deterministic_fallback"
                llm_strategy["actual_llm_model"] = "grounded-fallback"
                llm_strategy["fallback_used"] = True
                llm_strategy["fallback_reason"] = normalized_reason
                result = build_grounded_diagnosis_result(
                    project_title=project.title,
                    target_major=target_major,
                    target_university=fallback_target_university,
                    interest_universities=resolved_interest_universities,
                    career_direction=owner.career,
                    document_count=len(documents),
                    full_text=diagnosis_input_text or full_text,
                )
        else:
            llm_strategy["actual_llm_provider"] = "deterministic_fallback"
            llm_strategy["actual_llm_model"] = "grounded-fallback"
            result = build_grounded_diagnosis_result(
                project_title=project.title,
                target_major=target_major,
                target_university=fallback_target_university,
                interest_universities=resolved_interest_universities,
                career_direction=owner.career,
                document_count=len(documents),
                full_text=diagnosis_input_text or full_text,
            )

        _apply_structured_backbone(result=result, sheet=scoring_sheet)
        processing_duration_ms = int(max(0.0, (time.perf_counter() - started_at) * 1000.0))
        result.requested_llm_provider = str(llm_strategy.get("requested_llm_provider") or "")
        result.requested_llm_model = str(llm_strategy.get("requested_llm_model") or "")
        result.actual_llm_provider = str(llm_strategy.get("actual_llm_provider") or "")
        result.actual_llm_model = str(llm_strategy.get("actual_llm_model") or "")
        result.llm_profile_used = str(llm_strategy.get("llm_profile_used") or "standard")
        result.fallback_used = bool(llm_strategy.get("fallback_used"))
        result.fallback_reason = str(llm_strategy.get("fallback_reason") or "").strip() or None
        result.processing_duration_ms = processing_duration_ms

        _update_run_status(
            db,
            run,
            status_message="진단 근거 추적과 인용 데이터를 저장하고 있습니다...",
        )
        trace, citation_records = create_response_trace(
            db,
            run=run,
            project=project,
            user=owner,
            input_text=full_text,
            result=result,
            chunks=chunks,
            model_name=model_name,
        )
        result.citations = [DiagnosisCitation.model_validate(serialize_citation(item)) for item in citation_records]
        result.policy_codes = [flag.code for flag in flag_records]
        result.review_required = bool(review_task or run.review_tasks or findings)
        result.response_trace_id = trace.id

        run.result_payload = result.model_dump_json()
        run.status = "COMPLETED"
        run.status_message = "진단이 완료되었습니다."
        run.error_message = None
        _persist_run(db, run)
        db.refresh(run)

        try:
            create_blueprint_from_signals(
                db,
                project=project,
                diagnosis_run_id=run.id,
                signals=build_blueprint_signals(
                    headline=result.headline,
                    strengths=result.strengths,
                    gaps=result.gaps,
                    risk_level=result.risk_level,
                    recommended_focus=result.recommended_focus,
                ),
            )
        except Exception:  # noqa: BLE001
            _safe_db_rollback(db)
            logger.exception(
                "Blueprint generation failed after diagnosis completion. run_id=%s project_id=%s",
                run.id,
                run.project_id,
            )
        return run
    except Exception as exc:  # noqa: BLE001
        _safe_db_rollback(db)
        public_reason = _diagnosis_runtime_failure_message(exc)
        logger.exception(
            "Diagnosis run failed. run_id=%s project_id=%s reason=%s",
            run_id,
            project_id,
            public_reason,
        )

        try:
            latest_run = get_run_with_relations(db, run_id) or run
            latest_run.status = "FAILED"
            latest_run.status_message = "진단 실행이 실패했습니다."
            latest_run.error_message = public_reason
            _persist_run(db, latest_run)
        except Exception:  # noqa: BLE001
            _safe_db_rollback(db)
            logger.exception(
                "Failed to persist diagnosis failure state. run_id=%s project_id=%s",
                run_id,
                project_id,
            )
        raise

