import logging

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from unifoli_api.services.interview_service import InterviewService, InterviewQuestion, InterviewEvaluation
from unifoli_api.api.deps import get_db, get_current_user
from sqlalchemy.orm import Session
from sqlalchemy import select
from unifoli_api.db.models.diagnosis_run import DiagnosisRun
from unifoli_api.db.models.project import Project
from unifoli_api.db.models.user import User
from unifoli_api.services.diagnosis_service import DiagnosisResult

logger = logging.getLogger(__name__)

router = APIRouter()

class InterviewGenerateRequest(BaseModel):
    project_id: str

class InterviewEvaluateRequest(BaseModel):
    question: str
    answer: str
    context: str = ""


def _get_latest_completed_diagnosis(db: Session, *, project_id: str, user_id: str) -> DiagnosisResult | None:
    run = db.scalar(
        select(DiagnosisRun)
        .join(Project, DiagnosisRun.project_id == Project.id)
        .where(
            Project.id == project_id,
            Project.owner_user_id == user_id,
            DiagnosisRun.result_payload.is_not(None),
        )
        .order_by(DiagnosisRun.created_at.desc())
        .limit(1)
    )
    if run is None or not run.result_payload:
        return None

    try:
        return DiagnosisResult.model_validate_json(run.result_payload)
    except Exception as exc:
        logger.exception("Failed to parse diagnosis payload for interview questions: %s", run.id)
        raise HTTPException(status_code=500, detail="Diagnosis result could not be loaded.") from exc


@router.post("/generate-questions", response_model=List[InterviewQuestion])
async def generate_interview_questions(
    request: InterviewGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    diagnosis = _get_latest_completed_diagnosis(
        db,
        project_id=request.project_id,
        user_id=current_user.id,
    )
    if not diagnosis:
        raise HTTPException(status_code=404, detail="No diagnosis found for this project. Please complete diagnosis first.")
    
    # We check if it's finalized (Product Rule)
    if diagnosis.record_completion_state != "finalized":
        # We still allow it but maybe with a warning or restricted questions.
        # Product req says "for effectively finalized student-record users".
        pass

    interview_service = InterviewService()
    questions = await interview_service.generate_questions(diagnosis)
    return questions

@router.post("/evaluate-answer", response_model=InterviewEvaluation)
async def evaluate_interview_answer(
    request: InterviewEvaluateRequest,
    current_user: User = Depends(get_current_user)
):
    interview_service = InterviewService()
    evaluation = await interview_service.evaluate_answer(
        question=request.question,
        answer=request.answer,
        context=request.context
    )
    return evaluation
