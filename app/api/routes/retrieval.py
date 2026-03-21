from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.retrieval import (
    RetrievalCitationRead,
    RetrievalConflictRead,
    RetrievalDiagnosticsRead,
    RetrievalHitRead,
    RetrievalScoreBreakdownRead,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from services.admissions.retrieval_service import RetrievalQuery, hybrid_retrieval_service


router = APIRouter()


@router.post("/search", response_model=RetrievalSearchResponse)
def retrieval_search(payload: RetrievalSearchRequest, session: Session = Depends(get_db_session)) -> RetrievalSearchResponse:
    result = hybrid_retrieval_service.search(
        session,
        RetrievalQuery(
            query_text=payload.query_text,
            limit=payload.limit,
            source_tiers=tuple(payload.source_tiers) if payload.source_tiers else None,
            admissions_year=payload.admissions_year,
            university_id=payload.university_id,
            admission_cycle_id=payload.admission_cycle_id,
            admission_track_id=payload.admission_track_id,
            document_types=tuple(payload.document_types) if payload.document_types else None,
            claim_statuses=tuple(payload.claim_statuses) if payload.claim_statuses else None,
            freshness_states=tuple(payload.freshness_states) if payload.freshness_states else None,
            conflict_states=tuple(payload.conflict_states) if payload.conflict_states else None,
            current_cycle_only=payload.current_cycle_only,
            approved_claims_only=payload.approved_claims_only,
            include_conflicts=payload.include_conflicts,
            include_excluded_sources=payload.include_excluded_sources,
        ),
    )
    return RetrievalSearchResponse(
        hits=[
            RetrievalHitRead(
                record_type=hit.record_type,
                record_id=hit.record_id,
                document_id=hit.document_id,
                text=hit.text,
                title=hit.title,
                source_tier=hit.source_tier,
                freshness_state=hit.freshness_state,
                conflict_state=hit.conflict_state,
                score_breakdown=RetrievalScoreBreakdownRead(**asdict(hit.score_breakdown)),
                metadata=hit.metadata,
                citation=RetrievalCitationRead(**asdict(hit.citation)),
                conflicts=[RetrievalConflictRead(**asdict(item)) for item in hit.conflicts],
            )
            for hit in result.hits
        ],
        diagnostics=RetrievalDiagnosticsRead(**asdict(result.diagnostics)),
        ranking_policy=result.ranking_policy,
        applied_filters=result.applied_filters,
    )
