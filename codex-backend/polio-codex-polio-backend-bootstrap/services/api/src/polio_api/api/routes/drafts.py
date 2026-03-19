from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from polio_api.api.deps import get_db, get_current_user
from polio_api.schemas.draft import DraftCreate, DraftRead
from polio_api.services.draft_service import create_draft, get_draft, list_drafts_for_project
from polio_api.services.project_service import get_project
from pydantic import BaseModel
import google.generativeai as genai
import os

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "DUMMY_KEY"))

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

router = APIRouter()


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

@router.post("/chat/stream")
async def handle_chat_stream_route(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> StreamingResponse:
    import json
    import asyncio
    
    system_instruction = (
        "You are Poli, a friendly and encouraging AI mentor for Korean high school students "
        "preparing their university admission portfolio (생기부). "
        "The student is writing a report. Keep responses short, empathetic, and use emojis. "
    )
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=system_instruction
    )

    # Note: Using Depends(get_db) creates a session bound to the request. 
    # To safely insert async *after* stream completes without Session Closed errors, 
    # we simulate an asynchronous background save operation.
    async def save_chat_to_db(user_message: str, ai_response: str, user_info: dict):
        try:
            # Here you would typically instantiate a new session maker to write to DB
            # like: with SessionLocal() as async_db:
            #          async_db.add(ChatSession(...))
            print(f"[DB Save] User: {user_info.get('uid')} | Message: {user_message[:10]}... | AI length: {len(ai_response)}")
        except Exception as e:
            print(f"[DB Save Error] Failed to save chat history: {e}")

    async def event_stream():
        full_response = ""
        try:
            response_stream = await model.generate_content_async(
                contents=f"Student says: {payload.message}",
                stream=True,
                generation_config=genai.GenerationConfig(temperature=0.7)
            )
            
            async for chunk in response_stream:
                text = chunk.text
                if text:
                    full_response += text
                    # Yield data payload in SSE format
                    sse_data = json.dumps({"text": text}, ensure_ascii=False)
                    yield f"data: {sse_data}\n\n"
                    
            # 스트리밍이 정상적으로 완료된 후, 대화 내역 전체를 비동기로 저장 (Timeout 없는 백그라운드 태스크)
            asyncio.create_task(save_chat_to_db(payload.message, full_response, current_user))
            
            # SSE End indicator
            yield f"data: {json.dumps({'status': 'DONE'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            # API 제한 도달, Timeout 예외 방어
            error_msg = f"앗! AI 생성 중 서버 오류가 발생했어요: {str(e)} 🤕"
            error_data = json.dumps({"error": error_msg}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
            
    return StreamingResponse(event_stream(), media_type="text/event-stream")

