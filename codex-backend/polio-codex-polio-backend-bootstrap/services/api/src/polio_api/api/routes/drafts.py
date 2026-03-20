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

@router.post("/{project_id}/chat/stream")
async def handle_chat_stream_route(
    project_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Changed from dict to User to match deps.py
) -> StreamingResponse:
    import json
    import asyncio
    
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    # Contextual instruction based on the student's target major
    major_context = f"The student is targeting the {project.target_major} major." if project.target_major else ""
    
    system_instruction = (
        "You are Poli (폴리오), a friendly and encouraging AI research mentor for Korean high school students. "
        "Your goal is to help students write high-quality research reports (탐구보고서) for their school records (생기부). "
        f"{major_context} "
        "Response Rules: "
        "1. Write in Korean. Use friendly and supportive tone. "
        "2. Keep responses concise and use emojis. "
        "3. When suggesting a specific section for the report (like 'Introduction' or 'Conclusion'), "
        "wrap the suggested text inside [CONTENT]...[/CONTENT] tags so the system can extract it. "
    )
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=system_instruction
    )

    async def save_chat_to_db(user_message: str, ai_response: str, user: User):
        try:
            # Sync to DB logic here in the future
            print(f"[DB Save] User: {user.id} | Message: {user_message[:20]}... | AI Response: {ai_response[:20]}...")
        except Exception as e:
            print(f"[DB Save Error] {e}")

    async def event_stream():
        full_response = ""
        try:
            # Use Async SDK to generate stream
            response_stream = await model.generate_content_async(
                contents=f"Student says: {payload.message}",
                stream=True,
                generation_config=genai.GenerationConfig(temperature=0.7)
            )
            
            async for chunk in response_stream:
                if chunk.text:
                    token = chunk.text
                    full_response += token
                    # Yield JSON payload in SSE format
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            
            # Finalize
            asyncio.create_task(save_chat_to_db(payload.message, full_response, current_user))
            yield f"data: {json.dumps({'status': 'DONE'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            error_data = json.dumps({"error": f"AI 생성 도중 오류가 발생했습니다: {str(e)}"}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
            
    return StreamingResponse(event_stream(), media_type="text/event-stream")


