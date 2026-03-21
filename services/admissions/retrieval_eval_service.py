from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.eval import RetrievalEvalCase
from domain.enums import ClaimStatus, DocumentType, FreshnessState, LifecycleStatus, RetrievalConflictState, SourceTier
from services.admissions.retrieval_service import RetrievalQuery, hybrid_retrieval_service
from services.admissions.utils import ensure_uuid


class RetrievalEvalService:
    def list_cases(self, session: Session) -> list[RetrievalEvalCase]:
        stmt = select(RetrievalEvalCase).where(RetrievalEvalCase.deleted_at.is_(None)).order_by(RetrievalEvalCase.created_at.desc())
        return list(session.scalars(stmt))

    def create_case(
        self,
        session: Session,
        *,
        dataset_key: str,
        case_key: str,
        status: LifecycleStatus,
        query_text: str,
        filters_json: dict[str, object],
        expected_results_json: dict[str, object],
        notes: str | None,
        metadata_json: dict[str, object],
    ) -> RetrievalEvalCase:
        case = RetrievalEvalCase(
            dataset_key=dataset_key,
            case_key=case_key,
            status=status,
            query_text=query_text,
            filters_json=filters_json,
            expected_results_json=expected_results_json,
            notes=notes,
            metadata_json=metadata_json,
        )
        session.add(case)
        session.flush()
        session.refresh(case)
        return case

    def run_case(self, session: Session, *, case_id: str) -> dict[str, object] | None:
        case = session.get(RetrievalEvalCase, ensure_uuid(case_id))
        if case is None:
            return None
        result = hybrid_retrieval_service.search(session, self._build_query(case.query_text, case.filters_json))
        observed_record_ids = [str(hit.record_id) for hit in result.hits]
        observed_document_ids = [str(hit.document_id) for hit in result.hits]
        observed_citation_keys = [hit.citation.citation_key for hit in result.hits]
        expected = case.expected_results_json or {}
        expected_record_ids = set(expected.get("record_ids", []))
        expected_document_ids = set(expected.get("document_ids", []))
        require_current_cycle_top_hit = bool(expected.get("require_current_cycle_top_hit"))
        require_approved_claim_top_hit = bool(expected.get("require_approved_claim_top_hit"))

        top_hit = result.hits[0] if result.hits else None
        passed = True
        if expected_record_ids and not expected_record_ids.intersection(observed_record_ids):
            passed = False
        if expected_document_ids and not expected_document_ids.intersection(observed_document_ids):
            passed = False
        if require_current_cycle_top_hit and (top_hit is None or not top_hit.metadata.get("is_current_cycle")):
            passed = False
        if require_approved_claim_top_hit and (top_hit is None or top_hit.metadata.get("claim_status") != ClaimStatus.APPROVED.value):
            passed = False

        return {
            "case_id": str(case.id),
            "passed": passed,
            "observed_record_ids": observed_record_ids,
            "observed_document_ids": observed_document_ids,
            "observed_citation_keys": observed_citation_keys,
            "diagnostics": {
                "backend": result.diagnostics.backend,
                "candidate_count": result.diagnostics.candidate_count,
                "applied_filters": result.applied_filters,
            },
        }

    def _build_query(self, query_text: str, filters_json: dict[str, object]) -> RetrievalQuery:
        source_tiers = tuple(SourceTier(item) for item in filters_json.get("source_tiers", [])) or None
        document_types = tuple(DocumentType(item) for item in filters_json.get("document_types", [])) or None
        claim_statuses = tuple(ClaimStatus(item) for item in filters_json.get("claim_statuses", [])) or None
        freshness_states = tuple(FreshnessState(item) for item in filters_json.get("freshness_states", [])) or None
        conflict_states = tuple(RetrievalConflictState(item) for item in filters_json.get("conflict_states", [])) or None
        return RetrievalQuery(
            query_text=query_text,
            limit=int(filters_json.get("limit", 10)),
            source_tiers=source_tiers,
            admissions_year=filters_json.get("admissions_year"),
            university_id=filters_json.get("university_id"),
            admission_cycle_id=filters_json.get("admission_cycle_id"),
            admission_track_id=filters_json.get("admission_track_id"),
            document_types=document_types,
            claim_statuses=claim_statuses,
            freshness_states=freshness_states,
            conflict_states=conflict_states,
            current_cycle_only=bool(filters_json.get("current_cycle_only", False)),
            approved_claims_only=bool(filters_json.get("approved_claims_only", False)),
            include_conflicts=bool(filters_json.get("include_conflicts", True)),
            include_excluded_sources=bool(filters_json.get("include_excluded_sources", False)),
        )


retrieval_eval_service = RetrievalEvalService()
