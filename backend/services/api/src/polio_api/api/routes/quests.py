from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.blueprint import Blueprint
from polio_api.db.models.project import Project
from polio_api.db.models.quest import Quest
from polio_api.db.models.user import User
from polio_api.schemas.blueprint import QuestStartResponse
from polio_api.services.blueprint_service import start_quest

router = APIRouter()


@router.post("/{quest_id}/start", response_model=QuestStartResponse)
def start_quest_route(
    quest_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestStartResponse:
    quest = db.scalar(
        select(Quest)
        .join(Quest.blueprint)
        .join(Blueprint.project)
        .where(Quest.id == quest_id, Project.owner_user_id == current_user.id)
    )
    if quest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.")
    return start_quest(db, quest)
