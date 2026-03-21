from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_owner_key
from app.schemas.chat import ChatCitationRead, ChatQueryRequest, ChatQueryResponse
from services.admissions.chat_service import grounded_chat_service


router = APIRouter()


@router.post("/query", response_model=ChatQueryResponse)
def chat_query(
    payload: ChatQueryRequest,
    owner_key: str = Depends(get_owner_key),
    session: Session = Depends(get_db_session),
) -> ChatQueryResponse:
    result = grounded_chat_service.query(
        session,
        owner_key=owner_key,
        query_text=payload.query_text,
        limit=payload.limit,
    )
    session.commit()
    return ChatQueryResponse(
        answer=result.answer,
        safety_flags=result.safety_flags,
        citations=[ChatCitationRead(**item) for item in result.citations],
    )
