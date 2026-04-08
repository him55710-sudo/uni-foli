from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.core.llm import LLMRequestError, get_llm_client, get_llm_temperature
from polio_api.core.rate_limit import rate_limit
from polio_api.db.models.user import User
from polio_api.schemas.draft import DraftCreate, DraftRead, DraftUpdate
from polio_api.services.draft_service import create_draft, get_draft, list_drafts_for_project, update_draft
from polio_api.services.chat_fallback_service import build_conversational_fallback
from polio_api.services.guided_chat_state_service import load_guided_chat_state
from polio_api.services.project_service import append_project_discussion_log, get_project
from polio_api.services.prompt_registry import get_prompt_registry
from polio_api.services.workshop_document_grounding_service import build_workshop_document_grounding_context

router = APIRouter()
chat_router = APIRouter()
logger = logging.getLogger("polio.api.drafts")


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

    blocks = ["[참고 자료]"]
    for index, material in enumerate(reference_materials, start=1):
        authors = ", ".join(material.authors[:6]) if material.authors else "저자 정보 없음"
        year_text = str(material.year) if material.year else "연도 미상"
        abstract = (material.abstract or "초록 정보 없음").replace("\n", " ").strip()
        if len(abstract) > 700:
            abstract = f"{abstract[:700]}..."
        blocks.append(
            f"{index}. 제목: {material.title}\n"
            f"   저자: {authors}\n"
            f"   연도: {year_text}\n"
            f"   요약: {abstract}"
        )
    return "\n".join(blocks)


def _safe_json_dump(payload: dict[str, object] | None) -> str:
    if not payload:
        return ""
    return json.dumps(payload, ensure_ascii=False)


def _build_system_instruction(
    target_university: str | None,
    target_major: str | None,
    reference_materials: list[ReferenceMaterial],
    document_grounding_context: str | None = None,
    guided_state_summary: dict[str, object] | None = None,
) -> str:
    profile_context = (
        f"학생 목표 대학: {target_university or '미정'} / 목표 전공: {target_major or '미정'}"
    )
    reference_context = _format_reference_materials(reference_materials)
    guided_context = _safe_json_dump(guided_state_summary)
    base_instruction = get_prompt_registry().compose_prompt("chat.coaching-orchestration")

    sections = [f"[학생 맥락]\n{profile_context}"]
    if guided_context:
        sections.append(f"[가이드드 드래프팅 상태]\n{guided_context}")
    if document_grounding_context:
        sections.append(document_grounding_context)
    if reference_context:
        sections.append(reference_context)
    sections.append(base_instruction)
    return "\n\n".join(sections)


def _validate_reference_limit(reference_materials: list[ReferenceMaterial]) -> None:
    if len(reference_materials) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reference_materials can contain up to 3 papers.",
        )


def _build_deterministic_fallback(
    *,
    user_message: str,
    guided_state_summary: dict[str, object] | None,
    reason: str,
) -> str:
    return build_conversational_fallback(
        user_message=user_message,
        reason=reason,
        summary=guided_state_summary,
    )


def _chunk_text(text: str, chunk_size: int = 80) -> list[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _build_streaming_response(
    payload: ChatRequest,
    current_user: User,
    db: Session,
    project_id: str | None,
    target_university: str | None,
    target_major: str | None,
    document_grounding_context: str | None = None,
) -> StreamingResponse:
    guided_state_summary: dict[str, object] | None = None
    if project_id:
        state = load_guided_chat_state(db, project_id)
        if state:
            guided_state_summary = state.state_summary or None

    system_instruction = _build_system_instruction(
        target_university=target_university,
        target_major=target_major,
        reference_materials=payload.reference_materials,
        document_grounding_context=document_grounding_context,
        guided_state_summary=guided_state_summary,
    )

    def save_chat_to_db(user_message: str, user: User) -> None:
        try:
            if project_id:
                project = get_project(db, project_id, owner_user_id=user.id)
                if project:
                    append_project_discussion_log(db, project, user_message)
        except Exception:  # noqa: BLE001
            return

    async def event_stream():
        full_response = ""
        limited_mode = False
        limited_reason: str | None = None
        profile = "standard"

        yield f"data: {json.dumps({'meta': {'profile': profile, 'limited_mode': False, 'limited_reason': None}}, ensure_ascii=False)}\n\n"

        try:
            llm = get_llm_client(profile="standard")
            async for token in llm.stream_chat(
                prompt=f"[학생 메시지]\n{payload.message}",
                system_instruction=system_instruction,
                temperature=get_llm_temperature(profile="standard"),
            ):
                full_response += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except LLMRequestError as exc:
            limited_mode = True
            limited_reason = exc.limited_reason
        except Exception as exc:  # noqa: BLE001
            logger.warning("Draft chat stream switched to fallback: %s", repr(exc))
            limited_mode = True
            limited_reason = "llm_unavailable"

        if limited_mode:
            yield f"data: {json.dumps({'meta': {'profile': profile, 'limited_mode': True, 'limited_reason': limited_reason}}, ensure_ascii=False)}\n\n"
            fallback = _build_deterministic_fallback(
                user_message=payload.message,
                guided_state_summary=guided_state_summary,
                reason=limited_reason or "llm_unavailable",
            )
            for token in _chunk_text(fallback):
                full_response += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        save_chat_to_db(payload.message, current_user)
        yield f"data: {json.dumps({'status': 'DONE'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _resolve_project_grounding_context(db: Session, project_id: str, user: User, message: str) -> tuple[object, str]:
    project = get_project(db, project_id, owner_user_id=user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    document_grounding_context = build_workshop_document_grounding_context(
        db=db,
        project=project,
        user_message=message,
        profile="standard",
    )
    return project, document_grounding_context


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
    _validate_reference_limit(payload.reference_materials)
    project, document_grounding_context = _resolve_project_grounding_context(
        db=db,
        project_id=project_id,
        user=current_user,
        message=payload.message,
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
    document_grounding_context = None
    if payload.project_id:
        project, document_grounding_context = _resolve_project_grounding_context(
            db=db,
            project_id=payload.project_id,
            user=current_user,
            message=payload.message,
        )
        target_major = project.target_major

    return _build_streaming_response(
        payload=payload,
        current_user=current_user,
        db=db,
        project_id=payload.project_id,
        target_university=current_user.target_university,
        target_major=target_major or current_user.target_major,
        document_grounding_context=document_grounding_context,
    )
