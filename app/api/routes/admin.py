from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_admin_principal
from app.schemas.analysis import AnalysisRunRead
from app.schemas.claim import ClaimRead, ClaimStatusUpdate
from app.schemas.crawl import CrawlJobRead, DiscoveredUrlRead, FileObjectRead, ParserSummaryRead, SourceSeedRead
from app.schemas.document import DocumentChunkRead, DocumentRead
from app.schemas.eval import (
    EvalDatasetExampleCreate,
    EvalDatasetExampleRead,
    EvalEvidenceSpanCreate,
    EvalEvidenceSpanRead,
    RetrievalEvalCaseCreate,
    RetrievalEvalCaseRead,
    RetrievalEvalRunResult,
)
from app.schemas.extraction import (
    BulkLowConfidenceRequest,
    ClaimReviewUpdate,
    ExtractionBatchRead,
    ExtractionChunkDecisionRead,
    ExtractionFailureRead,
    ExtractionJobRead,
    ExtractionStatsRead,
)
from app.schemas.ingestion_job import IngestionJobRead
from app.schemas.privacy import DeletionEventRead, DeletionRequestCreate, DeletionRequestRead, PrivacyScanRead
from app.schemas.review import DocumentTrustUpdate, PolicyFlagRead, ReviewTaskCreate, ReviewTaskRead, ReviewTaskUpdate
from app.schemas.source import SourceRead
from app.schemas.student_file import StudentFileRead
from services.admissions.analysis_run_service import analysis_run_service
from services.admissions.claim_service import claim_service
from services.admissions.crawl_service import crawl_service
from services.admissions.deletion_service import deletion_service
from services.admissions.document_service import document_service
from services.admissions.eval_service import eval_service
from services.admissions.file_object_service import file_object_service
from services.admissions.ingestion_job_service import ingestion_job_service
from services.admissions.privacy_service import privacy_service
from services.admissions.retrieval_eval_service import retrieval_eval_service
from services.admissions.review_service import review_service
from services.admissions.source_seed_service import source_seed_service
from services.admissions.source_service import source_service
from services.admissions.student_file_service import student_file_service


router = APIRouter()


def _scoped_tenant_id(principal, requested_tenant_id: str | None) -> str | None:
    if principal.global_access:
        return requested_tenant_id
    return str(principal.tenant_id)


@router.get("/sources", response_model=list[SourceRead])
def admin_list_sources(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[SourceRead]:
    return [SourceRead.model_validate(item) for item in source_service.list_sources(session)]


@router.get("/source-seeds", response_model=list[SourceSeedRead])
def admin_list_source_seeds(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[SourceSeedRead]:
    return [SourceSeedRead.model_validate(item) for item in source_seed_service.list_seeds(session)]


@router.get("/crawl-jobs", response_model=list[CrawlJobRead])
def admin_list_crawl_jobs(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[CrawlJobRead]:
    return [CrawlJobRead.model_validate(item) for item in crawl_service.list_crawl_jobs(session)]


@router.get("/discovered-urls", response_model=list[DiscoveredUrlRead])
def admin_list_discovered_urls(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[DiscoveredUrlRead]:
    return [DiscoveredUrlRead.model_validate(item) for item in crawl_service.list_discovered_urls(session)]


@router.get("/file-objects", response_model=list[FileObjectRead])
def admin_list_file_objects(
    tenant_id: str | None = Query(default=None),
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[FileObjectRead]:
    scoped_tenant_id = _scoped_tenant_id(principal, tenant_id)
    return [FileObjectRead.model_validate(item) for item in file_object_service.list_file_objects(session, tenant_id=scoped_tenant_id)]


@router.get("/ingestion-jobs", response_model=list[IngestionJobRead])
def admin_list_ingestion_jobs(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[IngestionJobRead]:
    return [IngestionJobRead.model_validate(item) for item in ingestion_job_service.list_jobs(session)]


@router.get("/documents", response_model=list[DocumentRead])
def admin_list_documents(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[DocumentRead]:
    return [DocumentRead.model_validate(item) for item in document_service.list_documents(session)]


@router.get("/documents/{document_id}", response_model=DocumentRead)
def admin_get_document(
    document_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> DocumentRead:
    document = document_service.get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentRead.model_validate(document)


@router.get("/documents/{document_id}/parser-summary", response_model=ParserSummaryRead)
def admin_get_document_parser_summary(
    document_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> ParserSummaryRead:
    document = document_service.get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    version = document_service.get_current_version(session, document_id=document_id)
    payload = version.normalized_payload if version is not None else {}
    return ParserSummaryRead.model_validate(
        {
            "document_id": document.id,
            "document_version_id": version.id if version is not None else None,
            "parser_name": payload.get("parser_name") if isinstance(payload, dict) else None,
            "parser_version": payload.get("parser_version") if isinstance(payload, dict) else None,
            "parser_trace": payload.get("parser_trace", []) if isinstance(payload, dict) else [],
            "parser_fallback_reason": payload.get("fallback_reason") if isinstance(payload, dict) else None,
            "page_count": payload.get("metadata", {}).get("page_count", 0) if isinstance(payload, dict) else 0,
            "block_count": len(payload.get("blocks", [])) if isinstance(payload, dict) else 0,
            "chunk_count": len(document_service.list_document_chunks(session, document_id=document_id)),
            "freshness_score": document.freshness_score,
            "quality_score": document.quality_score,
            "is_current_cycle": document.is_current_cycle,
        }
    )


@router.get("/documents/{document_id}/chunks", response_model=list[DocumentChunkRead])
def admin_list_document_chunks(
    document_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[DocumentChunkRead]:
    return [DocumentChunkRead.model_validate(item) for item in document_service.list_document_chunks(session, document_id=document_id)]


@router.get("/documents/{document_id}/claims", response_model=list[ClaimRead])
def admin_list_document_claims(
    document_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ClaimRead]:
    return [ClaimRead.model_validate(item) for item in claim_service.list_claims_for_document(session, document_id=document_id)]


@router.get("/student-files", response_model=list[StudentFileRead])
def admin_list_student_files(
    tenant_id: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[StudentFileRead]:
    scoped_tenant_id = _scoped_tenant_id(principal, tenant_id)
    return [
        StudentFileRead.model_validate(item)
        for item in student_file_service.list_student_files(session, tenant_id=scoped_tenant_id, include_deleted=include_deleted)
    ]


@router.get("/analysis-runs", response_model=list[AnalysisRunRead])
def admin_list_analysis_runs(
    tenant_id: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[AnalysisRunRead]:
    scoped_tenant_id = _scoped_tenant_id(principal, tenant_id)
    return [
        AnalysisRunRead.model_validate(item)
        for item in analysis_run_service.list_runs(session, tenant_id=scoped_tenant_id, include_deleted=include_deleted)
    ]


@router.get("/review-tasks", response_model=list[ReviewTaskRead])
def list_review_tasks(
    tenant_id: str | None = Query(default=None),
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ReviewTaskRead]:
    scoped_tenant_id = _scoped_tenant_id(principal, tenant_id)
    return [ReviewTaskRead.model_validate(item) for item in review_service.list_review_tasks(session, tenant_id=scoped_tenant_id)]


@router.post("/review-tasks", response_model=ReviewTaskRead, status_code=status.HTTP_201_CREATED)
def create_review_task(
    payload: ReviewTaskCreate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> ReviewTaskRead:
    tenant_id = payload.tenant_id if principal.global_access and payload.tenant_id else principal.tenant_id
    task = review_service.create_review_task(
        session,
        task_type=payload.task_type,
        target_kind=payload.target_kind,
        target_id=payload.target_id,
        rationale=payload.rationale,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        tenant_id=tenant_id,
        metadata_json=payload.metadata_json,
    )
    session.commit()
    return ReviewTaskRead.model_validate(task)


@router.patch("/review-tasks/{review_task_id}", response_model=ReviewTaskRead)
def update_review_task(
    review_task_id: str,
    payload: ReviewTaskUpdate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> ReviewTaskRead:
    task = review_service.update_review_task(
        session,
        review_task_id=review_task_id,
        status=payload.status,
        resolution_note=payload.resolution_note,
        assigned_to=payload.assigned_to,
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review task not found")
    session.commit()
    return ReviewTaskRead.model_validate(task)


@router.get("/claims/pending", response_model=list[ClaimRead])
def list_claims_for_review(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ClaimRead]:
    return [ClaimRead.model_validate(item) for item in review_service.list_claims_for_review(session)]


@router.post("/claims/bulk-low-confidence", response_model=list[ClaimRead])
def bulk_mark_low_confidence_claims(
    payload: BulkLowConfidenceRequest,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ClaimRead]:
    claims = review_service.bulk_mark_low_confidence_claims(
        session,
        threshold=payload.threshold,
        limit=payload.limit,
        reviewer_id=payload.reviewer_id or str(principal.account_id),
        reviewer_note=payload.reviewer_note,
    )
    session.commit()
    return [ClaimRead.model_validate(item) for item in claims]


@router.get("/claims/{claim_id}", response_model=ClaimRead)
def admin_get_claim(
    claim_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> ClaimRead:
    claim = claim_service.get_claim(session, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return ClaimRead.model_validate(claim)


@router.patch("/claims/{claim_id}", response_model=ClaimRead)
def update_claim_status(
    claim_id: str,
    payload: ClaimStatusUpdate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> ClaimRead:
    claim = review_service.update_claim_status(session, claim_id=claim_id, status=payload.status)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    session.commit()
    return ClaimRead.model_validate(claim)


@router.patch("/claims/{claim_id}/review", response_model=ClaimRead)
def review_claim(
    claim_id: str,
    payload: ClaimReviewUpdate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> ClaimRead:
    try:
        claim = review_service.review_claim(
            session,
            claim_id=claim_id,
            status=payload.status,
            reviewer_id=payload.reviewer_id or str(principal.account_id),
            reviewer_note=payload.reviewer_note,
            evidence_quality_score=payload.evidence_quality_score,
            university_exception_note=payload.university_exception_note,
            unsafe_flagged=payload.unsafe_flagged,
            overclaim_flagged=payload.overclaim_flagged,
            claim_type=payload.claim_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    session.commit()
    return ClaimRead.model_validate(claim)


@router.get("/extraction/jobs", response_model=list[ExtractionJobRead])
def admin_list_extraction_jobs(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ExtractionJobRead]:
    return [ExtractionJobRead.model_validate(item) for item in claim_service.list_extraction_jobs(session)]


@router.get("/extraction/jobs/{extraction_job_id}", response_model=ExtractionJobRead)
def admin_get_extraction_job(
    extraction_job_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> ExtractionJobRead:
    job = claim_service.get_extraction_job(session, extraction_job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction job not found")
    return ExtractionJobRead.model_validate(job)


@router.get("/extraction/jobs/{extraction_job_id}/batches", response_model=list[ExtractionBatchRead])
def admin_list_extraction_batches(
    extraction_job_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ExtractionBatchRead]:
    return [ExtractionBatchRead.model_validate(item) for item in claim_service.list_extraction_batches(session, extraction_job_id=extraction_job_id)]


@router.get("/extraction/jobs/{extraction_job_id}/chunk-decisions", response_model=list[ExtractionChunkDecisionRead])
def admin_list_extraction_chunk_decisions(
    extraction_job_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ExtractionChunkDecisionRead]:
    return [
        ExtractionChunkDecisionRead.model_validate(item)
        for item in claim_service.list_chunk_decisions(session, extraction_job_id=extraction_job_id)
    ]


@router.get("/extraction/failures", response_model=list[ExtractionFailureRead])
def admin_list_extraction_failures(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ExtractionFailureRead]:
    return [ExtractionFailureRead.model_validate(item) for item in claim_service.list_extraction_failures(session)]


@router.get("/extraction/stats", response_model=list[ExtractionStatsRead])
def admin_list_extraction_stats(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[ExtractionStatsRead]:
    return [ExtractionStatsRead.model_validate(item) for item in claim_service.list_extraction_stats(session)]


@router.get("/eval/examples", response_model=list[EvalDatasetExampleRead])
def admin_list_eval_examples(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[EvalDatasetExampleRead]:
    return [EvalDatasetExampleRead.model_validate(item) for item in eval_service.list_examples(session)]


@router.post("/eval/examples", response_model=EvalDatasetExampleRead, status_code=status.HTTP_201_CREATED)
def admin_create_eval_example(
    payload: EvalDatasetExampleCreate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> EvalDatasetExampleRead:
    example = eval_service.create_example(
        session,
        dataset_key=payload.dataset_key,
        example_key=payload.example_key,
        example_kind=payload.example_kind,
        status=payload.status,
        document_id=payload.document_id,
        document_chunk_id=payload.document_chunk_id,
        prompt_text=payload.prompt_text,
        source_text=payload.source_text,
        expected_claims_json=payload.expected_claims_json,
        expected_flags_json=payload.expected_flags_json,
        notes=payload.notes,
        metadata_json=payload.metadata_json,
    )
    session.commit()
    session.refresh(example)
    return EvalDatasetExampleRead.model_validate(example)


@router.post("/eval/examples/{eval_example_id}/spans", response_model=EvalEvidenceSpanRead, status_code=status.HTTP_201_CREATED)
def admin_add_eval_evidence_span(
    eval_example_id: str,
    payload: EvalEvidenceSpanCreate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> EvalEvidenceSpanRead:
    span = eval_service.add_evidence_span(
        session,
        eval_example_id=eval_example_id,
        document_chunk_id=payload.document_chunk_id,
        span_rank=payload.span_rank,
        page_number=payload.page_number,
        char_start=payload.char_start,
        char_end=payload.char_end,
        quoted_text=payload.quoted_text,
        label=payload.label,
        metadata_json=payload.metadata_json,
    )
    session.commit()
    return EvalEvidenceSpanRead.model_validate(span)


@router.get("/retrieval/eval-cases", response_model=list[RetrievalEvalCaseRead])
def admin_list_retrieval_eval_cases(
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[RetrievalEvalCaseRead]:
    return [RetrievalEvalCaseRead.model_validate(item) for item in retrieval_eval_service.list_cases(session)]


@router.post("/retrieval/eval-cases", response_model=RetrievalEvalCaseRead, status_code=status.HTTP_201_CREATED)
def admin_create_retrieval_eval_case(
    payload: RetrievalEvalCaseCreate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> RetrievalEvalCaseRead:
    case = retrieval_eval_service.create_case(
        session,
        dataset_key=payload.dataset_key,
        case_key=payload.case_key,
        status=payload.status,
        query_text=payload.query_text,
        filters_json=payload.filters_json,
        expected_results_json=payload.expected_results_json,
        notes=payload.notes,
        metadata_json=payload.metadata_json,
    )
    session.commit()
    return RetrievalEvalCaseRead.model_validate(case)


@router.post("/retrieval/eval-cases/{case_id}/run", response_model=RetrievalEvalRunResult)
def admin_run_retrieval_eval_case(
    case_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> RetrievalEvalRunResult:
    result = retrieval_eval_service.run_case(session, case_id=case_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retrieval eval case not found")
    return RetrievalEvalRunResult.model_validate(result)


@router.patch("/documents/{document_id}/trust", response_model=DocumentRead)
def update_document_trust(
    document_id: str,
    payload: DocumentTrustUpdate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> DocumentRead:
    document = review_service.update_document_trust(
        session,
        document_id=document_id,
        low_trust=payload.low_trust,
        note=payload.note,
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    session.commit()
    return DocumentRead.model_validate(document)


@router.get("/policy-flags", response_model=list[PolicyFlagRead])
def list_policy_flags(
    tenant_id: str | None = Query(default=None),
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[PolicyFlagRead]:
    scoped_tenant_id = _scoped_tenant_id(principal, tenant_id)
    return [PolicyFlagRead.model_validate(item) for item in review_service.list_policy_flags(session, tenant_id=scoped_tenant_id)]


@router.get("/privacy-scans", response_model=list[PrivacyScanRead])
def admin_list_privacy_scans(
    tenant_id: str | None = Query(default=None),
    student_file_id: str | None = Query(default=None),
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[PrivacyScanRead]:
    scoped_tenant_id = _scoped_tenant_id(principal, tenant_id)
    return [
        PrivacyScanRead.model_validate(item)
        for item in privacy_service.list_privacy_scans(session, tenant_id=scoped_tenant_id, student_file_id=student_file_id)
    ]


@router.get("/deletion-requests", response_model=list[DeletionRequestRead])
def admin_list_deletion_requests(
    tenant_id: str | None = Query(default=None),
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[DeletionRequestRead]:
    scoped_tenant_id = _scoped_tenant_id(principal, tenant_id)
    return [DeletionRequestRead.model_validate(item) for item in deletion_service.list_requests(session, tenant_id=scoped_tenant_id)]


@router.post("/deletion-requests", response_model=DeletionRequestRead, status_code=status.HTTP_201_CREATED)
def admin_create_deletion_request(
    payload: DeletionRequestCreate,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> DeletionRequestRead:
    try:
        deletion_request = deletion_service.create_request(
            session,
            principal=principal,
            target_kind=payload.target_kind,
            target_id=str(payload.target_id),
            deletion_mode=payload.deletion_mode,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    session.commit()
    return DeletionRequestRead.model_validate(deletion_request)


@router.post("/deletion-requests/{deletion_request_id}/execute", response_model=DeletionRequestRead)
def admin_execute_deletion_request(
    deletion_request_id: str,
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> DeletionRequestRead:
    deletion_request = deletion_service.execute_request(session, deletion_request_id=deletion_request_id, principal=principal)
    if deletion_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deletion request not found")
    session.commit()
    return DeletionRequestRead.model_validate(deletion_request)


@router.get("/deletion-events", response_model=list[DeletionEventRead])
def admin_list_deletion_events(
    tenant_id: str | None = Query(default=None),
    principal=Depends(require_admin_principal),
    session: Session = Depends(get_db_session),
) -> list[DeletionEventRead]:
    scoped_tenant_id = _scoped_tenant_id(principal, tenant_id)
    return [DeletionEventRead.model_validate(item) for item in deletion_service.list_events(session, tenant_id=scoped_tenant_id)]
