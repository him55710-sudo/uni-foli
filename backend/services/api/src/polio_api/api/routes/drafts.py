from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.core.rate_limit import rate_limit
from polio_api.db.models.user import User
from polio_api.core.llm import get_llm_client
from polio_api.schemas.draft import DraftCreate, DraftUpdate, DraftRead
from polio_api.services.draft_service import create_draft, update_draft, get_draft, list_drafts_for_project
from polio_api.services.prompt_registry import get_prompt_registry
from polio_api.services.project_service import append_project_discussion_log, get_project
from polio_api.services.workshop_document_grounding_service import build_workshop_document_grounding_context

router = APIRouter()
chat_router = APIRouter()


class ReferenceMaterial(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=20)
    abstract: str | None = Field(default=None, max_length=6000)
    year: int | None = Field(default=None, ge=1800, le=2100)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    project_id: str | None = None
    reference_materials: list[ReferenceMaterial] = Field(default_factory=list, max_length=3)


def _format_reference_materials(reference_materials: list[ReferenceMaterial]) -> str:
    if not reference_materials:
        return ""

    blocks = ["[참고 문헌 데이터]"]
    for index, material in enumerate(reference_materials, start=1):
        authors = ", ".join(material.authors[:6]) if material.authors else "저자 정보 없음"
        year_text = str(material.year) if material.year else "발행연도 미상"
        abstract = (material.abstract or "초록 정보 없음").replace("\n", " ").strip()
        if len(abstract) > 1200:
            abstract = f"{abstract[:1200]}..."
        blocks.append(
            f"{index}. 제목: {material.title}\n"
            f"   저자: {authors}\n"
            f"   발행연도: {year_text}\n"
            f"   초록: {abstract}"
        )
    return "\n".join(blocks)


def _build_system_instruction(
    target_university: str | None,
    target_major: str | None,
    reference_materials: list[ReferenceMaterial],
    document_grounding_context: str | None = None,
) -> str:
    profile_context = (
        f"학생의 목표 대학은 '{target_university or '미정'}'이고, 목표 전공은 '{target_major or '미정'}'이다."
    )
    reference_context = _format_reference_materials(reference_materials)
    base_instruction = _build_chat_base_instruction()

    sections = []
    if reference_context:
        sections.append(reference_context)
    if document_grounding_context:
        sections.append(document_grounding_context)
    sections.append(f"[학생 맥락]\n{profile_context}")
    sections.append(base_instruction)
    return "\n\n".join(sections)




def _validate_reference_limit(reference_materials: list[ReferenceMaterial]) -> None:
    if len(reference_materials) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reference_materials can contain up to 3 papers.",
        )


def _build_streaming_response(
    payload: ChatRequest,
    current_user: User,
    db: Session,
    project_id: str | None,
    target_university: str | None,
    target_major: str | None,
    document_grounding_context: str | None = None,
) -> StreamingResponse:
    llm = get_llm_client()
    system_instruction = _build_system_instruction(
        target_university=target_university,
        target_major=target_major,
        reference_materials=payload.reference_materials,
        document_grounding_context=document_grounding_context,
    )

    async def save_chat_to_db(user_message: str, ai_response: str, user: User) -> None:
        try:
            if project_id:
                project = get_project(db, project_id, owner_user_id=user.id)
                if project:
                    append_project_discussion_log(db, project, user_message)
        except Exception:  # noqa: BLE001
            return

    async def event_stream():
        full_response = ""
        try:
            async for token in llm.stream_chat(
                prompt=f"[학생 메시지]\n{payload.message}",
                system_instruction=system_instruction,
                temperature=0.5,
            ):
                full_response += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            await save_chat_to_db(payload.message, full_response, current_user)
            yield f"data: {json.dumps({'status': 'DONE'}, ensure_ascii=False)}\n\n"
        except Exception:  # noqa: BLE001
            error_data = json.dumps(
                {"error": "AI 생성 도중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."},
                ensure_ascii=False,
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _build_chat_base_instruction() -> str:
    return get_prompt_registry().compose_prompt("chat.coaching-orchestration")


@router.post(
    "/{project_id}/drafts",
    response_model=DraftRead,
    status_code=status.HTTP_201_CREATED,
)
def create_draft_route(
    project_id: str,
    payload: DraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRead:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    draft = create_draft(db, project_id=project_id, payload=payload)
    return DraftRead.model_validate(draft)


@router.get("/{project_id}/drafts", response_model=list[DraftRead])
def list_drafts_route(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DraftRead]:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return [DraftRead.model_validate(item) for item in list_drafts_for_project(db, project_id)]


@router.get("/{project_id}/drafts/{draft_id}", response_model=DraftRead)
def get_draft_route(
    project_id: str,
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRead:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    draft = get_draft(db, draft_id)
    if not draft or draft.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    return DraftRead.model_validate(draft)


@router.patch("/{project_id}/drafts/{draft_id}", response_model=DraftRead)
def update_draft_route(
    project_id: str,
    draft_id: str,
    payload: DraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRead:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    
    draft = get_draft(db, draft_id)
    if not draft or draft.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    
    updated = update_draft(db, draft_id, payload)
    return DraftRead.model_validate(updated)


@router.post("/{project_id}/chat/stream")
async def handle_chat_stream_route(
    project_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="project_draft_chat", limit=30, window_seconds=300, guest_limit=20)),
) -> StreamingResponse:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    _validate_reference_limit(payload.reference_materials)
    document_grounding_context = build_workshop_document_grounding_context(
        db=db,
        project=project,
        user_message=payload.message,
    )
    return _build_streaming_response(
        payload=payload,
        current_user=current_user,
        db=db,
        project_id=project.id,
        target_university=current_user.target_university or project.target_university,
        target_major=project.target_major or current_user.target_major,
        document_grounding_context=document_grounding_context,
    )


@chat_router.post("/chat/stream")
async def handle_drafts_chat_stream_route(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="draft_chat", limit=30, window_seconds=300, guest_limit=20)),
) -> StreamingResponse:
    _validate_reference_limit(payload.reference_materials)

    project = None
    target_major: str | None = None
    if payload.project_id:
        project = get_project(db, payload.project_id, owner_user_id=current_user.id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        target_major = project.target_major

    document_grounding_context = None
    if project is not None:
        document_grounding_context = build_workshop_document_grounding_context(
            db=db,
            project=project,
            user_message=payload.message,
        )

    return _build_streaming_response(
        payload=payload,
        current_user=current_user,
        db=db,
        project_id=payload.project_id,
        target_university=current_user.target_university,
        target_major=target_major or current_user.target_major,
        document_grounding_context=document_grounding_context,
    )
