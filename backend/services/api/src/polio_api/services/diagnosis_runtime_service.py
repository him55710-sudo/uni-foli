from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from polio_api.core.config import get_settings
from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.db.models.project import Project
from polio_api.db.models.response_trace import ResponseTrace
from polio_api.db.models.user import User
from polio_api.services.blueprint_service import build_blueprint_signals, create_blueprint_from_signals
from polio_api.services.diagnosis_scoring_service import (
    DiagnosisScoringSheet,
    build_diagnosis_scoring_sheet,
)
from polio_api.services.diagnosis_service import (
    DiagnosisCitation,
    attach_policy_flags_to_run,
    build_grounded_diagnosis_result,
    create_response_trace,
    detect_policy_flags,
    ensure_review_task_for_flags,
    evaluate_student_record,
    serialize_citation,
)
from polio_api.services.document_service import list_chunks_for_project, list_documents_for_project
from polio_api.services.project_service import get_project
from polio_api.services.student_record_feature_service import extract_student_record_features
from polio_shared.paths import resolve_stored_path


RAW_POLICY_SCAN_EXTENSIONS = {".txt", ".md", ".csv", ".json"}


def combine_project_text(project_id: str, db: Session) -> tuple[list, str]:
    documents = list_documents_for_project(db, project_id)
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a parsed document before running diagnosis.",
        )

    full_text = "\n\n".join(
        document.content_text or document.content_markdown or ""
        for document in documents
        if document.content_text or document.content_markdown
    ).strip()
    if not full_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parsed document content is empty.",
        )
    return documents, full_text


def build_policy_scan_text(documents: list) -> str:
    parts: list[str] = []
    for document in documents:
        if document.content_text or document.content_markdown:
            parts.append(document.content_text or document.content_markdown or "")
        stored_path = getattr(document, "stored_path", None)
        source_extension = (getattr(document, "source_extension", "") or "").lower()
        if not stored_path or source_extension not in RAW_POLICY_SCAN_EXTENSIONS:
            continue
        try:
            raw_text = resolve_stored_path(stored_path).read_text(encoding="utf-8")
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


def _diagnosis_llm_strategy() -> tuple[bool, str]:
    settings = get_settings()
    provider = (settings.llm_provider or "gemini").strip().lower()
    has_real_gemini_key = bool(settings.gemini_api_key and settings.gemini_api_key != "DUMMY_KEY")

    if provider == "ollama":
        model = (settings.ollama_model or "ollama").strip() or "ollama"
        return True, model
    if provider == "gemini" and has_real_gemini_key:
        return True, "gemini-1.5-pro"
    return False, "grounded-fallback"


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


async def run_diagnosis_run(
    db: Session,
    *,
    run_id: str,
    project_id: str,
    owner_user_id: str,
    fallback_target_university: str | None,
    fallback_target_major: str | None,
) -> DiagnosisRun:
    run = get_run_with_relations(db, run_id)
    if run is None:
        raise ValueError(f"Diagnosis run not found: {run_id}")

    project = get_project(db, project_id, owner_user_id=owner_user_id)
    if project is None:
        raise ValueError("Project not found.")
    owner = db.get(User, owner_user_id)
    if owner is None:
        raise ValueError("Project owner not found.")

    documents, full_text = combine_project_text(project_id, db)
    chunks = list_chunks_for_project(db, project_id)

    policy_scan_text = build_policy_scan_text(documents) or full_text
    
    run.status_message = "검색된 문서들의 정책 준수 여부를 검토하고 있습니다..."
    db.commit()
    
    findings = detect_policy_flags(policy_scan_text)
    flag_records = run.policy_flags
    review_task = run.review_tasks[0] if run.review_tasks else None
    if findings and not run.policy_flags:
        flag_records = attach_policy_flags_to_run(db, run=run, project=project, user=owner, findings=findings)
        review_task = ensure_review_task_for_flags(db, run=run, project=project, user=owner, findings=findings)

    target_major = fallback_target_major or project.target_major
    user_major = project.target_major or fallback_target_major or "General Studies"
    evidence_keys = [
        document.sha256 or document.id
        for document in documents
        if (document.sha256 or document.id)
    ]
    run.status_message = "생활기록부 데이터의 특징점(분량, 키워드 등)을 추출하고 있습니다..."
    db.commit()
    
    features = extract_student_record_features(
        documents=documents,
        full_text=full_text,
        target_major=target_major,
        career_direction=owner.career,
    )
    
    # ---------------------------------------------------------
    # NEW: Semantic Extraction Stage (Expert Evaluation)
    # ---------------------------------------------------------
    run.status_message = "추출된 데이터를 기반으로 전문가 수준의 정성 진단을 수행하고 있습니다..."
    db.commit()
    
    from polio_api.services.diagnosis_scoring_service import extract_semantic_diagnosis
    semantic_data = None
    try:
        semantic_data = await extract_semantic_diagnosis(
            masked_text=full_text,
            target_major=target_major or "일반 전형",
            target_university=fallback_target_university,
        )
    except Exception as e:
        # We don't want to fail the whole run if semantic extraction fails
        print(f"Semantic extraction failed: {e}")
        
    run.status_message = "진단 리포트의 체계를 구성하고 점수를 산출하고 있습니다..."
    db.commit()

    scoring_sheet = build_diagnosis_scoring_sheet(
        features=features,
        project_title=project.title,
        target_major=target_major,
        target_university=fallback_target_university,
        semantic=semantic_data,
    )
    should_use_llm, model_name = _diagnosis_llm_strategy()

    if should_use_llm:
        run.status_message = "상세 진단 내용을 생성하고 근거 데이터를 매핑하고 있습니다..."
        db.commit()

        result = await evaluate_student_record(
            user_major=user_major,
            masked_text=full_text[:30000],
            target_university=fallback_target_university,
            target_major=target_major,
            career_direction=owner.career,
            project_title=project.title,
            scope_key=f"project:{project.id}",
            evidence_keys=evidence_keys,
        )
    else:
        result = build_grounded_diagnosis_result(
            project_title=project.title,
            target_major=target_major,
            target_university=fallback_target_university,
            career_direction=owner.career,
            document_count=len(documents),
            full_text=full_text,
        )
    _apply_structured_backbone(result=result, sheet=scoring_sheet)

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
    run.error_message = None
    db.add(run)

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
    db.commit()
    db.refresh(run)
    return run
