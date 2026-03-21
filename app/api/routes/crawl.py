from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.crawl import CrawlJobCreate, CrawlJobRead, DiscoveredUrlRead, SourceSeedCreate, SourceSeedRead
from services.admissions.crawl_service import crawl_service
from services.admissions.source_seed_service import source_seed_service


router = APIRouter()


@router.get("/seeds", response_model=list[SourceSeedRead])
def list_source_seeds(
    source_id: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[SourceSeedRead]:
    return [SourceSeedRead.model_validate(item) for item in source_seed_service.list_seeds(session, source_id=source_id)]


@router.post("/seeds", response_model=SourceSeedRead, status_code=status.HTTP_201_CREATED)
def create_source_seed(payload: SourceSeedCreate, session: Session = Depends(get_db_session)) -> SourceSeedRead:
    try:
        seed = source_seed_service.create_seed(
            session,
            source_id=payload.source_id,
            seed_type=payload.seed_type,
            label=payload.label,
            seed_url=payload.seed_url,
            allowed_domains=payload.allowed_domains,
            allowed_path_prefixes=payload.allowed_path_prefixes,
            denied_path_prefixes=payload.denied_path_prefixes,
            max_depth=payload.max_depth,
            current_cycle_year_hint=payload.current_cycle_year_hint,
            allow_binary_assets=payload.allow_binary_assets,
            respect_robots_txt=payload.respect_robots_txt,
            metadata_json=payload.metadata_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    session.commit()
    return SourceSeedRead.model_validate(seed)


@router.get("/jobs", response_model=list[CrawlJobRead])
def list_crawl_jobs(
    source_id: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[CrawlJobRead]:
    return [CrawlJobRead.model_validate(item) for item in crawl_service.list_crawl_jobs(session, source_id=source_id)]


@router.post("/jobs", response_model=CrawlJobRead, status_code=status.HTTP_201_CREATED)
def create_crawl_job(payload: CrawlJobCreate, session: Session = Depends(get_db_session)) -> CrawlJobRead:
    try:
        job = crawl_service.create_crawl_job(
            session,
            source_id=payload.source_id,
            source_seed_id=payload.source_seed_id,
            trigger_mode=payload.trigger_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    session.commit()
    return CrawlJobRead.model_validate(job)


@router.post("/jobs/{crawl_job_id}/run", response_model=CrawlJobRead)
def run_crawl_job(
    crawl_job_id: str,
    force_refresh: bool = Query(default=False),
    auto_ingest: bool = Query(default=True),
    session: Session = Depends(get_db_session),
) -> CrawlJobRead:
    try:
        job = crawl_service.run_crawl_job(
            session,
            crawl_job_id=crawl_job_id,
            force_refresh=force_refresh,
            auto_ingest=auto_ingest,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    session.commit()
    return CrawlJobRead.model_validate(job)


@router.get("/discovered-urls", response_model=list[DiscoveredUrlRead])
def list_discovered_urls(
    source_id: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[DiscoveredUrlRead]:
    return [DiscoveredUrlRead.model_validate(item) for item in crawl_service.list_discovered_urls(session, source_id=source_id)]
