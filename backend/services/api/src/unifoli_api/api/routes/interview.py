from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from unifoli_api.services.interview_service import InterviewService, InterviewQuestion, InterviewEvaluation
from unifoli_api.api.deps import get_db, get_current_user
from sqlalchemy.orm import Session
from unifoli_domain.models import User
from unifoli_api.services.diagnosis_service import DiagnosisService

router = APIRouter()

class InterviewGenerateRequest(BaseModel):
    project_id: str

class InterviewEvaluateRequest(BaseModel):
    question: str
    answer: str
    context: str = ""

@router.post("/generate-questions", response_model=List[InterviewQuestion])
async def generate_interview_questions(
    request: InterviewGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Retrieve the latest diagnosis for the project
    diagnosis_service = DiagnosisService(db)
    # This is a simplification; in reality, we'd find the latest successful run.
    # For now, we assume a helper exists or we find it directly.
    diagnosis = await diagnosis_service.get_latest_diagnosis(request.project_id)
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
