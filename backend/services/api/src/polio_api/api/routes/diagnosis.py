from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any

from polio_api.api.deps import get_db, get_current_user
from polio_api.services.diagnosis_service import evaluate_student_record, DiagnosisResult
from polio_api.services.project_service import get_project
from polio_api.services.document_service import list_documents_for_project

router = APIRouter()

@router.post("/{project_id}/diagnose", response_model=DiagnosisResult)
async def perform_diagnosis(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
) -> DiagnosisResult:
    """
    Triggers the AI diagnosis based on the project's target major and uploaded documents.
    """
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    # Get the contents of the parsed documents for diagnosis
    docs = list_documents_for_project(db, project_id)
    if not docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No parsed documents found. Please upload a PDF first."
        )

    # Concatenate document content (masking is assumed to be done during ingestion)
    full_text = "\n\n".join([doc.content for doc in docs if doc.content])
    if not full_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Document content is empty."
        )

    # Perform AI evaluation
    result = await evaluate_student_record(
        user_major=project.target_major or current_user.target_major or "일반 학과",
        target_university=current_user.target_university,
        target_major=current_user.target_major or project.target_major,
        masked_text=full_text[:15000] # Simple truncation for token limit safety
    )
    
    return result
