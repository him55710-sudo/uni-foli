from __future__ import annotations

import json
import os

import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.user import User
from polio_api.schemas.draft import DraftCreate, DraftRead
from polio_api.services.draft_service import create_draft, get_draft, list_drafts_for_project
from polio_api.services.project_service import append_project_discussion_log, get_project

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "DUMMY_KEY"))

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
) -> str:
    profile_context = (
        f"학생의 목표 대학은 '{target_university or '미정'}'이고, 목표 전공은 '{target_major or '미정'}'이다."
    )
    reference_context = _format_reference_materials(reference_materials)

    base_instruction = (
        "너는 대치동 수석 컨설턴트 Poli다. 사용자가 질문할 때, 내가 제공한 [참고 문헌 데이터]가 있다면 "
        "반드시 그 문헌의 내용을 바탕으로 답변하고, 문장 끝에 [논문 제목, 발행연도] 형태로 명확한 출처(Citation)를 달아라. "
        "제공된 문헌에 없는 내용을 지어내지 마라.\n"
        "추가 응답 규칙:\n"
        "1. 한국어로 답변한다.\n"
        "2. 친절하지만 핵심 위주로 간결하게 답변한다.\n"
        "3. 보고서 문단(예: 서론/결론/분석 파트) 제안을 줄 때는 반드시 [CONTENT]...[/CONTENT] 태그로 감싼다.\n"
        "4. 참고 문헌 데이터가 없는 경우에만 일반 지식 기반으로 답변하되, 추측은 명확히 추측이라고 밝혀라.\n"
        "5. 학생이 통계, 추이 분석, 데이터 시각화를 요구하거나 제공된 📌참고 문헌에 중요한 수치 데이터가 있다면, 분석 결과를 텍스트로 설명한 뒤 반드시 아래 포맷의 JSON 데이터를 생성해라.\n"
        "[CHART]\n"
        '{ "title": "그래프 제목", "type": "bar", "data": [{"name": "항목1", "value": 10}, {"name": "항목2", "value": 20}] }\n'
        "[/CHART]\n"
        "6. 학생이 복잡한 수치 계산, 확률 시뮬레이션, 데이터 전처리를 요구할 경우, 분석 결과를 말로만 설명하지 말고 파이썬 코드를 작성해라.\n"
        "코드는 반드시 [PYTHON] 태그와 [/PYTHON] 태그 사이에 작성해야 한다.\n"
        "예:\n"
        "[PYTHON]\n"
        "def simulate():\n"
        "    return '분석 완료'\n"
        "print(simulate())\n"
        "[/PYTHON]\n"
    )

    if reference_context:
        return f"{reference_context}\n\n[학생 맥락]\n{profile_context}\n\n{base_instruction}"
    return f"[학생 맥락]\n{profile_context}\n\n{base_instruction}"


def _build_chat_model(
    target_university: str | None,
    target_major: str | None,
    reference_materials: list[ReferenceMaterial],
) -> genai.GenerativeModel:
    system_instruction = _build_system_instruction(target_university, target_major, reference_materials)
    return genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=system_instruction,
    )


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
) -> StreamingResponse:
    model = _build_chat_model(
        target_university=target_university,
        target_major=target_major,
        reference_materials=payload.reference_materials,
    )

    async def save_chat_to_db(user_message: str, ai_response: str, user: User) -> None:
        try:
            if project_id:
                project = get_project(db, project_id)
                if project:
                    append_project_discussion_log(db, project, user_message)
            print(
                f"[DB Save] User: {user.id} | Message: {user_message[:30]}... | "
                f"AI Response: {ai_response[:30]}..."
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[DB Save Error] {exc}")

    async def event_stream():
        full_response = ""
        try:
            response_stream = await model.generate_content_async(
                contents=f"Student says: {payload.message}",
                stream=True,
                generation_config=genai.GenerationConfig(temperature=0.5),
            )

            async for chunk in response_stream:
                token = getattr(chunk, "text", None)
                if token:
                    full_response += token
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            await save_chat_to_db(payload.message, full_response, current_user)
            yield f"data: {json.dumps({'status': 'DONE'}, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            error_data = json.dumps(
                {"error": f"AI 생성 도중 오류가 발생했습니다: {str(exc)}"},
                ensure_ascii=False,
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post(
    "/{project_id}/drafts",
    response_model=DraftRead,
    status_code=status.HTTP_201_CREATED,
)
def create_draft_route(
    project_id: str,
    payload: DraftCreate,
    db: Session = Depends(get_db),
) -> DraftRead:
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    draft = create_draft(db, project_id=project_id, payload=payload)
    return DraftRead.model_validate(draft)


@router.get("/{project_id}/drafts", response_model=list[DraftRead])
def list_drafts_route(project_id: str, db: Session = Depends(get_db)) -> list[DraftRead]:
    return [DraftRead.model_validate(item) for item in list_drafts_for_project(db, project_id)]


@router.get("/{project_id}/drafts/{draft_id}", response_model=DraftRead)
def get_draft_route(project_id: str, draft_id: str, db: Session = Depends(get_db)) -> DraftRead:
    draft = get_draft(db, draft_id)
    if not draft or draft.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    return DraftRead.model_validate(draft)


@router.post("/{project_id}/chat/stream")
async def handle_chat_stream_route(
    project_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    _validate_reference_limit(payload.reference_materials)
    return _build_streaming_response(
        payload=payload,
        current_user=current_user,
        db=db,
        project_id=project.id,
        target_university=current_user.target_university or project.target_university,
        target_major=project.target_major or current_user.target_major,
    )


@chat_router.post("/chat/stream")
async def handle_drafts_chat_stream_route(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    _validate_reference_limit(payload.reference_materials)

    target_major: str | None = None
    if payload.project_id:
        project = get_project(db, payload.project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        target_major = project.target_major

    return _build_streaming_response(
        payload=payload,
        current_user=current_user,
        db=db,
        project_id=payload.project_id,
        target_university=current_user.target_university,
        target_major=target_major or current_user.target_major,
    )
