from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.user import User
from polio_api.schemas.grounded_answer import GroundedAnswerRequest, GroundedAnswerResponse
from polio_api.services.grounded_answer_service import answer_project_question
from polio_api.services.project_service import get_project

router = APIRouter()


@router.post("/{project_id}/grounded-answer", response_model=GroundedAnswerResponse)
def grounded_answer_route(
    project_id: str,
    payload: GroundedAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroundedAnswerResponse:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return answer_project_question(
        db,
        project=project,
        question=payload.question,
        top_k=payload.top_k,
    )
