from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models.content import Claim, DocumentChunk, RetrievalIndexRecord
from domain.enums import RetrievalIndexStatus, RetrievalRecordType
from services.admissions.model_gateway import extraction_model_gateway
from services.admissions.retrieval_service import classify_freshness_state


class RetrievalIndexService:
    def refresh_document_chunks(self, session: Session, *, document_id) -> int:
        chunks = list(session.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id)))
        session.execute(
            delete(RetrievalIndexRecord).where(
                RetrievalIndexRecord.document_id == document_id,
                RetrievalIndexRecord.record_type == RetrievalRecordType.BLOCK,
            )
        )
        if not chunks:
            session.flush()
            return 0

        embeddings = extraction_model_gateway.embed_texts([chunk.content_text for chunk in chunks]).vectors
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            session.add(
                RetrievalIndexRecord(
                    record_type=RetrievalRecordType.BLOCK,
                    record_id=chunk.id,
                    document_id=chunk.document_id,
                    document_version_id=chunk.document_version_id,
                    source_tier=chunk.document.source_tier,
                    source_id=chunk.document.source_id,
                    university_id=chunk.document.university_id,
                    admission_cycle_id=chunk.document.admission_cycle_id,
                    admission_track_id=chunk.document.admission_track_id,
                    searchable_text=chunk.content_text,
                    embedding=embedding,
                    embedding_model=extraction_model_gateway.get_embedding_config().litellm_model,
                    lexical_weight=1.0,
                    vector_weight=0.75,
                    freshness_score=chunk.document.freshness_score,
                    trust_score=chunk.document.trust_score,
                    quality_score=chunk.document.quality_score,
                    index_status=RetrievalIndexStatus.INDEXED,
                    metadata_json={
                        "title": chunk.document.canonical_title,
                        "page_start": chunk.page_start,
                        "chunk_index": chunk.chunk_index,
                        "admissions_year": chunk.document.admissions_year,
                        "admission_track_id": str(chunk.document.admission_track_id) if chunk.document.admission_track_id else None,
                        "university_id": str(chunk.document.university_id) if chunk.document.university_id else None,
                        "admission_cycle_id": str(chunk.document.admission_cycle_id) if chunk.document.admission_cycle_id else None,
                        "document_type": chunk.document.document_type.value,
                        "is_current_cycle": chunk.document.is_current_cycle,
                        "freshness_state": classify_freshness_state(chunk.document).value,
                        "source_url": chunk.document.source_url,
                        "heading_path": chunk.heading_path,
                    },
                )
            )
        session.flush()
        return len(chunks)

    def upsert_claim_record(self, session: Session, *, claim: Claim) -> None:
        existing = session.scalar(
            select(RetrievalIndexRecord).where(
                RetrievalIndexRecord.record_type == RetrievalRecordType.CLAIM,
                RetrievalIndexRecord.record_id == claim.id,
            )
        )
        embedding = extraction_model_gateway.embed_texts([claim.normalized_claim_text]).vectors[0]
        payload = {
            "document_type": claim.document.document_type.value,
            "title": claim.document.canonical_title,
            "claim_type": claim.claim_type.value,
            "claim_status": claim.status.value,
            "is_current_cycle": claim.document.is_current_cycle,
            "freshness_state": classify_freshness_state(claim.document).value,
            "admissions_year": claim.applicable_from_year or claim.document.admissions_year,
            "admission_track_id": str(claim.document.admission_track_id) if claim.document.admission_track_id else None,
            "university_id": str(claim.document.university_id) if claim.document.university_id else None,
            "admission_cycle_id": str(claim.document.admission_cycle_id) if claim.document.admission_cycle_id else None,
            "source_url": claim.document.source_url,
            "is_direct_rule": claim.is_direct_rule,
            "unsafe_flagged": claim.unsafe_flagged,
            "overclaim_flagged": claim.overclaim_flagged,
        }
        if existing is None:
            existing = RetrievalIndexRecord(
                record_type=RetrievalRecordType.CLAIM,
                record_id=claim.id,
                document_id=claim.document_id,
                document_version_id=claim.document_version_id,
            )
            session.add(existing)

        existing.source_id = claim.document.source_id
        existing.university_id = claim.document.university_id
        existing.admission_cycle_id = claim.document.admission_cycle_id
        existing.admission_track_id = claim.document.admission_track_id
        existing.source_tier = claim.source_tier
        existing.searchable_text = claim.normalized_claim_text
        existing.embedding = embedding
        existing.embedding_model = extraction_model_gateway.get_embedding_config().litellm_model
        existing.lexical_weight = 1.0
        existing.vector_weight = 1.0
        existing.freshness_score = claim.document.freshness_score
        existing.trust_score = claim.document.trust_score
        existing.quality_score = claim.quality_score
        existing.index_status = RetrievalIndexStatus.INDEXED
        existing.metadata_json = payload
        session.flush()


retrieval_index_service = RetrievalIndexService()
