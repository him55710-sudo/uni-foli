import json
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from polio_api.api.deps import get_current_user, get_db
from polio_api.core.database import SessionLocal
from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.db.models.project import Project
from polio_api.db.models.response_trace import ResponseTrace
from polio_api.db.models.user import User
from polio_api.services.blueprint_service import build_blueprint_signals, create_blueprint_from_signals
from polio_api.services.diagnosis_service import (
    DiagnosisCitation,
    DiagnosisResult,
    attach_policy_flags_to_run,
    build_grounded_diagnosis_result,
    create_response_trace,
    detect_policy_flags,
    ensure_review_task_for_flags,
    evaluate_student_record,
    latest_response_trace,
    serialize_citation,
    serialize_policy_flag,
)
from polio_api.services.document_service import list_chunks_for_project, list_documents_for_project
from polio_api.services.project_service import get_project
from polio_shared.paths import resolve_stored_path

router = APIRouter()
RAW_POLICY_SCAN_EXTENSIONS = {".txt", ".md", ".csv", ".json"}


class DiagnosisRunRequest(BaseModel):
    project_id: str


class DiagnosisRunResponse(BaseModel):
    id: str
    project_id: str
    status: str
    result_payload: dict[str, object] | None = None
    error_message: str | None = None
    review_required: bool = False
    policy_flags: list[dict[str, object]] = Field(default_factory=list)
    citations: list[dict[str, object]] = Field(default_factory=list)
    response_trace_id: str | None = None


def _combine_project_text(project_id: str, db: Session) -> tuple[list, str]:
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


def _build_policy_scan_text(documents: list) -> str:
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


async def bg_run_diagnosis(
    run_id: str,
    project_id: str,
    owner_user_id: str,
    fallback_target_university: str | None,
    fallback_target_major: str | None,
) -> None:
    db = SessionLocal()
    run: DiagnosisRun | None = None
    try:
        run = db.scalar(
            select(DiagnosisRun)
            .where(DiagnosisRun.id == run_id)
            .options(
                selectinload(DiagnosisRun.policy_flags),
                selectinload(DiagnosisRun.review_tasks),
                selectinload(DiagnosisRun.response_traces).selectinload(ResponseTrace.citations),
            )
        )
        if run is None:
            return

        project = get_project(db, project_id, owner_user_id=owner_user_id)
        if project is None:
            raise ValueError("Project not found.")
        owner = db.get(User, owner_user_id)
        if owner is None:
            raise ValueError("Project owner not found.")

        documents, full_text = _combine_project_text(project_id, db)
        chunks = list_chunks_for_project(db, project_id)

        policy_scan_text = _build_policy_scan_text(documents) or full_text
        findings = detect_policy_flags(policy_scan_text)
        flag_records = run.policy_flags
        review_task = run.review_tasks[0] if run.review_tasks else None
        if findings and not run.policy_flags:
            flag_records = attach_policy_flags_to_run(db, run=run, project=project, user=owner, findings=findings)
            review_task = ensure_review_task_for_flags(db, run=run, project=project, user=owner, findings=findings)

        target_major = fallback_target_major or project.target_major
        user_major = project.target_major or fallback_target_major or "General Studies"
        has_real_gemini_key = bool(os.environ.get("GEMINI_API_KEY")) and os.environ.get("GEMINI_API_KEY") != "DUMMY_KEY"

        if has_real_gemini_key:
            result = await evaluate_student_record(
                user_major=user_major,
                masked_text=full_text[:30000],
                target_university=fallback_target_university,
                target_major=target_major,
            )
            model_name = "gemini-1.5-pro"
        else:
            result = build_grounded_diagnosis_result(
                project_title=project.title,
                target_major=target_major,
                document_count=len(documents),
                full_text=full_text,
            )
            model_name = "grounded-fallback"

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
    except HTTPException as exc:
        if run is not None:
            run.status = "FAILED"
            run.error_message = exc.detail
            db.add(run)
            db.commit()
    except Exception as exc:  # noqa: BLE001
        if run is not None:
            run.status = "FAILED"
            run.error_message = str(exc)
            db.add(run)
            db.commit()
    finally:
        db.close()


def _get_run_for_user(db: Session, diagnosis_id: str, user_id: str) -> DiagnosisRun | None:
    return db.scalar(
        select(DiagnosisRun)
        .join(Project, DiagnosisRun.project_id == Project.id)
        .where(DiagnosisRun.id == diagnosis_id, Project.owner_user_id == user_id)
        .options(
            selectinload(DiagnosisRun.policy_flags),
            selectinload(DiagnosisRun.review_tasks),
            selectinload(DiagnosisRun.response_traces).selectinload(ResponseTrace.citations),
        )
    )


def _build_run_response(run: DiagnosisRun) -> DiagnosisRunResponse:
    payload = json.loads(run.result_payload) if run.result_payload else None
    trace = latest_response_trace(run)
    citations = [serialize_citation(item) for item in (trace.citations if trace else [])]
    return DiagnosisRunResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        result_payload=payload,
        error_message=run.error_message,
        review_required=bool(run.review_tasks or run.policy_flags),
        policy_flags=[serialize_policy_flag(item) for item in run.policy_flags],
        citations=citations,
        response_trace_id=trace.id if trace else None,
    )


@router.post("/run", response_model=DiagnosisRunResponse)
@router.post("/runs", response_model=DiagnosisRunResponse)
async def trigger_diagnosis(
    payload: DiagnosisRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DiagnosisRunResponse:
    project = get_project(db, payload.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    documents, full_text = _combine_project_text(project.id, db)
    policy_scan_text = _build_policy_scan_text(documents) or full_text

    run = DiagnosisRun(project_id=payload.project_id, status="PENDING")
    db.add(run)
    db.flush()

    findings = detect_policy_flags(policy_scan_text)
    flag_records = attach_policy_flags_to_run(db, run=run, project=project, user=current_user, findings=findings)
    review_task = ensure_review_task_for_flags(db, run=run, project=project, user=current_user, findings=findings)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(
        bg_run_diagnosis,
        run.id,
        payload.project_id,
        current_user.id,
        current_user.target_university or project.target_university,
        current_user.target_major or project.target_major,
    )

    return DiagnosisRunResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        review_required=review_task is not None,
        policy_flags=[serialize_policy_flag(item) for item in flag_records],
    )


@router.get("/{diagnosis_id}", response_model=DiagnosisRunResponse)
@router.get("/runs/{diagnosis_id}", response_model=DiagnosisRunResponse)
async def get_diagnosis_status(
    diagnosis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DiagnosisRunResponse:
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
    return _build_run_response(run)
