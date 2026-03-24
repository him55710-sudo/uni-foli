from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.quest import Quest
from polio_api.schemas.blueprint import QuestStartResponse
from polio_api.services.blueprint_service import start_quest

router = APIRouter()


@router.post("/{quest_id}/start", response_model=QuestStartResponse)
def start_quest_route(
    quest_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> QuestStartResponse:
    del current_user
    quest = db.get(Quest, quest_id)
    if quest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.")
    return start_quest(db, quest)
