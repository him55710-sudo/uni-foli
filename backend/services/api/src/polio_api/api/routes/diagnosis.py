import json
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.core.database import SessionLocal
from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.services.blueprint_service import build_blueprint_signals, create_blueprint_from_signals
from polio_api.services.diagnosis_service import (
    DiagnosisResult,
    build_grounded_diagnosis_result,
    evaluate_student_record,
)
from polio_api.services.document_service import list_documents_for_project
from polio_api.services.project_service import get_project

router = APIRouter()


class DiagnosisRunRequest(BaseModel):
    project_id: str


class DiagnosisRunResponse(BaseModel):
    id: str
    project_id: str
    status: str
    result_payload: dict | None = None
    error_message: str | None = None


async def bg_run_diagnosis(
    run_id: str,
    project_id: str,
    fallback_target_university: str | None,
    fallback_target_major: str | None,
) -> None:
    db = SessionLocal()
    run: DiagnosisRun | None = None
    try:
        run = db.query(DiagnosisRun).filter(DiagnosisRun.id == run_id).first()
        if run is None:
            return

        project = get_project(db, project_id)
        if project is None:
            raise ValueError("Project not found.")

        documents = list_documents_for_project(db, project_id)
        if not documents:
            raise ValueError("Upload a parsed document before running diagnosis.")

        full_text = "\n\n".join(
            document.content_text or document.content_markdown or ""
            for document in documents
            if document.content_text or document.content_markdown
        ).strip()
        if not full_text:
            raise ValueError("Parsed document content is empty.")

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
        else:
            result = build_grounded_diagnosis_result(
                project_title=project.title,
                target_major=target_major,
                document_count=len(documents),
                full_text=full_text,
            )

        run.result_payload = result.model_dump_json()
        run.status = "COMPLETED"

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
    except Exception as exc:  # noqa: BLE001
        if run is not None:
            run.status = "FAILED"
            run.error_message = str(exc)
            db.add(run)
            db.commit()
    finally:
        db.close()


@router.post("/run", response_model=DiagnosisRunResponse)
async def trigger_diagnosis(
    payload: DiagnosisRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DiagnosisRunResponse:
    run = DiagnosisRun(project_id=payload.project_id, status="PENDING")
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(
        bg_run_diagnosis,
        run.id,
        payload.project_id,
        getattr(current_user, "target_university", None),
        getattr(current_user, "target_major", None),
    )

    return DiagnosisRunResponse(id=run.id, project_id=run.project_id, status=run.status)


@router.get("/{diagnosis_id}", response_model=DiagnosisRunResponse)
async def get_diagnosis_status(
    diagnosis_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> DiagnosisRunResponse:
    del current_user
    run = db.query(DiagnosisRun).filter(DiagnosisRun.id == diagnosis_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Diagnosis run not found.")

    payload = json.loads(run.result_payload) if run.result_payload else None
    return DiagnosisRunResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        result_payload=payload,
        error_message=run.error_message,
    )
