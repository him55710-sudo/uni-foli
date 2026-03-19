from fastapi import APIRouter, Depends, HTTPException, status
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

@router.post("/chat", response_model=ChatResponse)
def handle_chat_route(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> ChatResponse:
    # 1. System Prompt for Poli
    system_instruction = (
        "You are Poli, a friendly and encouraging AI mentor for Korean high school students "
        "preparing their university admission portfolio (생기부). "
        "The student is writing a report. Keep responses short, empathetic, and use emojis. "
        "If the student provides content for the report, acknowledge it and suggest adding it to the document."
    )
    
    try:
        # Use simple generative model call
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction
        )
        response = model.generate_content(
            f"Student says: {payload.message}"
        )
        reply_text = response.text or "Poli가 응답을 생성하지 못했어요. 다시 시도해주세요!"
        
        # NOTE: Ideally save chat to the database here (Draft segment, etc) if needed.
        # For this integration, we just return it.
        return ChatResponse(response=reply_text)
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return ChatResponse(response="앗! 서버에 잠깐 과부하가 걸렸나 봐요. Poli가 얼른 고치고 올게요! 🤕")
