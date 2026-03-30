from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.core.rate_limit import rate_limit
from polio_api.db.models.user import User
from polio_api.schemas.async_job import AsyncJobRead
from polio_api.schemas.research import (
    ResearchChunkRead,
    ResearchDocumentRead,
    ResearchIngestRequest,
    ResearchIngestResponse,
)
from polio_api.services.async_job_service import create_async_job, dispatch_job_if_enabled
from polio_api.services.project_service import get_project
from polio_api.services.research_service import (
    create_research_placeholder,
    get_research_document,
    list_research_chunks,
    list_research_documents,
)
from polio_api.services.scholar_service import (
    ScholarSearchResult,
    ScholarServiceError,
    search_kci_papers,
    search_semantic_scholar_papers,
)
from polio_domain.enums import AsyncJobType

router = APIRouter()


@router.get("/papers", response_model=ScholarSearchResult)
async def search_research_papers(
    query: Annotated[str, Query(min_length=2, max_length=200, description="Paper search keyword")],
    limit: Annotated[int, Query(ge=1, le=20, description="Number of results to return")] = 5,
    source: Annotated[str, Query(description="Search source: semantic or kci")] = "semantic",
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="research_papers", limit=30, window_seconds=300)),
) -> ScholarSearchResult:
    del current_user
    try:
        if source == "kci":
            return await search_kci_papers(query=query, limit=limit)
        return await search_semantic_scholar_papers(query=query, limit=limit)
    except ScholarServiceError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers=headers) from exc


@router.post("/sources/ingest", response_model=ResearchIngestResponse)
def ingest_research_sources(
    payload: ResearchIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="research_ingest", limit=10, window_seconds=300)),
) -> ResearchIngestResponse:
    project = get_project(db, payload.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    documents: list[ResearchDocumentRead] = []
    jobs: list[AsyncJobRead] = []
    for item in payload.items:
        document = create_research_placeholder(db, project_id=payload.project_id, payload=item)
        job = create_async_job(
            db,
            job_type=AsyncJobType.RESEARCH_INGEST.value,
            resource_type="research_document",
            resource_id=document.id,
            project_id=payload.project_id,
            payload={
                "document_id": document.id,
                "research_payload": item.model_dump(mode="json"),
            },
        )
        dispatch_job_if_enabled(job.id)
        documents.append(ResearchDocumentRead.model_validate(document))
        jobs.append(AsyncJobRead.model_validate(job))

    return ResearchIngestResponse(documents=documents, jobs=jobs)


@router.get("/sources", response_model=list[ResearchDocumentRead])
def list_research_sources(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResearchDocumentRead]:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return [ResearchDocumentRead.model_validate(item) for item in list_research_documents(db, project_id)]


@router.get("/sources/{document_id}", response_model=ResearchDocumentRead)
def get_research_source(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearchDocumentRead:
    document = get_research_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Research document not found.")
    project = get_project(db, document.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Research document not found.")
    return ResearchDocumentRead.model_validate(document)


@router.get("/sources/{document_id}/chunks", response_model=list[ResearchChunkRead])
def get_research_source_chunks(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResearchChunkRead]:
    document = get_research_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Research document not found.")
    project = get_project(db, document.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Research document not found.")
    return [ResearchChunkRead.model_validate(item) for item in list_research_chunks(db, document_id)]
