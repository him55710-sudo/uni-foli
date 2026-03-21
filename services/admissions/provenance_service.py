from __future__ import annotations

from sqlalchemy.orm import Session

from db.models.audit import Citation, ResponseTrace
from domain.enums import ResponseTraceKind


class ProvenanceService:
    def create_response_trace(
        self,
        session: Session,
        *,
        response_kind: ResponseTraceKind,
        tenant_id,
        owner_key: str,
        route_name: str,
        query_text: str,
        prompt_template_key: str | None,
        model_name: str | None,
        retention_expires_at=None,
        retrieval_trace: dict[str, object],
        response_payload: dict[str, object],
    ) -> ResponseTrace:
        trace = ResponseTrace(
            tenant_id=tenant_id,
            response_kind=response_kind,
            owner_key=owner_key,
            route_name=route_name,
            query_text=query_text,
            prompt_template_key=prompt_template_key,
            model_name=model_name,
            retention_expires_at=retention_expires_at,
            retrieval_trace=retrieval_trace,
            response_payload=response_payload,
        )
        session.add(trace)
        session.flush()
        session.refresh(trace)
        return trace

    def add_citation(
        self,
        session: Session,
        *,
        tenant_id=None,
        response_trace_id,
        analysis_run_id=None,
        claim_id=None,
        student_artifact_id=None,
        citation_kind: str,
        label: str,
        page_number: int | None,
        locator_json: dict[str, object],
        quoted_text: str | None,
    ) -> Citation:
        citation = Citation(
            tenant_id=tenant_id,
            response_trace_id=response_trace_id,
            analysis_run_id=analysis_run_id,
            claim_id=claim_id,
            student_artifact_id=student_artifact_id,
            citation_kind=citation_kind,
            label=label,
            page_number=page_number,
            locator_json=locator_json,
            quoted_text=quoted_text,
        )
        session.add(citation)
        session.flush()
        session.refresh(citation)
        return citation


provenance_service = ProvenanceService()
