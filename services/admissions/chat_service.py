from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from domain.enums import ResponseTraceKind
from services.admissions.provenance_service import provenance_service
from services.admissions.retrieval_service import RetrievalQuery, hybrid_retrieval_service
from services.admissions.safety_service import safety_service


@dataclass(slots=True)
class ChatResult:
    answer: str
    safety_flags: list[str]
    citations: list[dict[str, object]]


class GroundedChatService:
    def query(self, session: Session, *, owner_key: str, query_text: str, limit: int) -> ChatResult:
        safety_flags = safety_service.evaluate_query_text(query_text)
        if any(flag.severity_score >= 0.85 for flag in safety_flags):
            trace = provenance_service.create_response_trace(
                session,
                response_kind=ResponseTraceKind.CHAT,
                tenant_id=None,
                owner_key=owner_key,
                route_name="chat.query",
                query_text=query_text,
                prompt_template_key=None,
                model_name=None,
                retention_expires_at=None,
                retrieval_trace={"blocked": True},
                response_payload={"answer": "Request blocked by safety policy."},
            )
            return ChatResult(
                answer="I can help interpret official admissions criteria, but I cannot help fabricate or deceptively rewrite records.",
                safety_flags=[flag.message for flag in safety_flags],
                citations=[],
            )

        result = hybrid_retrieval_service.search(session, RetrievalQuery(query_text=query_text, limit=limit))
        hits = result.hits
        snippets = [hit.text[:180] for hit in hits[:3]]
        answer = " ".join(snippets) if snippets else "No grounded evidence found for this query yet."

        trace = provenance_service.create_response_trace(
            session,
            response_kind=ResponseTraceKind.CHAT,
            tenant_id=None,
            owner_key=owner_key,
            route_name="chat.query",
            query_text=query_text,
            prompt_template_key="grounded_summary_v1",
            model_name=None,
            retention_expires_at=None,
            retrieval_trace={
                "hit_count": len(hits),
                "diagnostics": {
                    "candidate_count": result.diagnostics.candidate_count,
                    "backend": result.diagnostics.backend,
                },
            },
            response_payload={"answer": answer},
        )
        citations: list[dict[str, object]] = []
        for hit in hits[:5]:
            citation = provenance_service.add_citation(
                session,
                tenant_id=None,
                response_trace_id=trace.id,
                citation_kind=hit.citation.citation_kind,
                label=hit.citation.label,
                page_number=hit.citation.page_number,
                locator_json=hit.citation.locator,
                quoted_text=hit.citation.quoted_text,
            )
            citations.append(
                {
                    "label": citation.label,
                    "citation_kind": citation.citation_kind,
                    "page_number": citation.page_number,
                    "quoted_text": citation.quoted_text,
                    "locator_json": citation.locator_json,
                }
            )
        return ChatResult(answer=answer, safety_flags=[], citations=citations)


grounded_chat_service = GroundedChatService()
