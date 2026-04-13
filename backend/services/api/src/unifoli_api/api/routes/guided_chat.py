from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from unifoli_api.api.deps import get_current_user, get_db
from unifoli_api.core.rate_limit import rate_limit
from unifoli_api.db.models.user import User
from unifoli_api.schemas.guided_chat import (
    GuidedChatStartRequest,
    GuidedChatStartResponse,
    PageRangeSelectionRequest,
    PageRangeSelectionResponse,
    StructureSelectionRequest,
    StructureSelectionResponse,
    TopicSelectionRequest,
    TopicSelectionResponse,
    TopicSuggestionRequest,
    TopicSuggestionResponse,
)
from unifoli_api.services.guided_chat_service import (
    generate_topic_suggestions,
    select_page_range,
    select_structure,
    select_topic,
    start_guided_chat,
)

router = APIRouter()


@router.post("/start", response_model=GuidedChatStartResponse)
def guided_chat_start_route(
    payload: GuidedChatStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="guided_chat_start", limit=40, window_seconds=300, guest_limit=20)),
) -> GuidedChatStartResponse:
    return start_guided_chat(db=db, user=current_user, project_id=payload.project_id)


@router.post("/topic-suggestions", response_model=TopicSuggestionResponse)
async def guided_chat_topic_suggestions_route(
    payload: TopicSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="guided_chat_topic_suggestions", limit=30, window_seconds=300, guest_limit=15)),
) -> TopicSuggestionResponse:
    return await generate_topic_suggestions(
        db=db,
        user=current_user,
        project_id=payload.project_id,
        subject=payload.subject,
    )


@router.post("/topic-selection", response_model=TopicSelectionResponse)
def guided_chat_topic_selection_route(
    payload: TopicSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="guided_chat_topic_selection", limit=40, window_seconds=300, guest_limit=20)),
) -> TopicSelectionResponse:
    return select_topic(
        db=db,
        user=current_user,
        project_id=payload.project_id,
        selected_topic_id=payload.selected_topic_id,
        subject=payload.subject,
        suggestions=payload.suggestions,
    )


@router.post("/page-range-selection", response_model=PageRangeSelectionResponse)
def guided_chat_page_range_selection_route(
    payload: PageRangeSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="guided_chat_page_range_selection", limit=40, window_seconds=300, guest_limit=20)),
) -> PageRangeSelectionResponse:
    return select_page_range(
        db=db,
        user=current_user,
        project_id=payload.project_id,
        selected_page_range_label=payload.selected_page_range_label,
        selected_topic_id=payload.selected_topic_id,
    )


@router.post("/structure-selection", response_model=StructureSelectionResponse)
def guided_chat_structure_selection_route(
    payload: StructureSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="guided_chat_structure_selection", limit=40, window_seconds=300, guest_limit=20)),
) -> StructureSelectionResponse:
    return select_structure(
        db=db,
        user=current_user,
        project_id=payload.project_id,
        selected_structure_id=payload.selected_structure_id,
    )
