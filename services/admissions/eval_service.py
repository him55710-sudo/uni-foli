from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.models.eval import EvalDatasetExample, EvalEvidenceSpan
from services.admissions.utils import ensure_uuid


class EvalService:
    def list_examples(self, session: Session) -> list[EvalDatasetExample]:
        stmt = select(EvalDatasetExample).options(selectinload(EvalDatasetExample.evidence_spans)).order_by(
            EvalDatasetExample.created_at.desc()
        )
        return list(session.scalars(stmt))

    def create_example(
        self,
        session: Session,
        *,
        dataset_key: str,
        example_key: str,
        example_kind,
        status,
        document_id,
        document_chunk_id,
        prompt_text: str | None,
        source_text: str | None,
        expected_claims_json: dict[str, object],
        expected_flags_json: dict[str, object],
        notes: str | None,
        metadata_json: dict[str, object],
    ) -> EvalDatasetExample:
        example = EvalDatasetExample(
            dataset_key=dataset_key,
            example_key=example_key,
            example_kind=example_kind,
            status=status,
            document_id=document_id,
            document_chunk_id=document_chunk_id,
            prompt_text=prompt_text,
            source_text=source_text,
            expected_claims_json=expected_claims_json,
            expected_flags_json=expected_flags_json,
            notes=notes,
            metadata_json=metadata_json,
        )
        session.add(example)
        session.flush()
        session.refresh(example)
        return example

    def add_evidence_span(
        self,
        session: Session,
        *,
        eval_example_id,
        document_chunk_id,
        span_rank: int,
        page_number: int | None,
        char_start: int | None,
        char_end: int | None,
        quoted_text: str,
        label: str | None,
        metadata_json: dict[str, object],
    ) -> EvalEvidenceSpan:
        span = EvalEvidenceSpan(
            eval_example_id=ensure_uuid(eval_example_id),
            document_chunk_id=document_chunk_id,
            span_rank=span_rank,
            page_number=page_number,
            char_start=char_start,
            char_end=char_end,
            quoted_text=quoted_text,
            label=label,
            metadata_json=metadata_json,
        )
        session.add(span)
        session.flush()
        session.refresh(span)
        return span


eval_service = EvalService()
