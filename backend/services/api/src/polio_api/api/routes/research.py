from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from polio_api.services.scholar_service import (
    ScholarSearchResult,
    ScholarServiceError,
    search_semantic_scholar_papers,
    search_kci_papers,
)

router = APIRouter()


@router.get("/papers", response_model=ScholarSearchResult)
async def search_research_papers(
    query: Annotated[str, Query(min_length=2, max_length=200, description="Paper search keyword")],
    limit: Annotated[int, Query(ge=1, le=20, description="Number of results to return")] = 5,
    source: Annotated[str, Query(description="Search source: semantic or kci")] = "semantic",
) -> ScholarSearchResult:
    try:
        if source == "kci":
            return await search_kci_papers(query=query, limit=limit)
        return await search_semantic_scholar_papers(query=query, limit=limit)
    except ScholarServiceError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers=headers) from exc
