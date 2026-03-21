from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Select, false, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from db.models.admissions import Source
from db.models.content import Claim, ClaimEvidence, ConflictRecord, Document, DocumentChunk, RetrievalIndexRecord
from domain.enums import (
    ClaimStatus,
    ConflictStatus,
    DocumentType,
    FreshnessState,
    RetrievalConflictState,
    RetrievalIndexStatus,
    RetrievalRecordType,
    SourceTier,
)
from services.admissions.model_gateway import extraction_model_gateway
from services.admissions.reranking_service import retrieval_reranking_service
from services.admissions.utils import ensure_uuid


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z\uac00-\ud7a3]+")


@dataclass(slots=True)
class RetrievalScoreBreakdown:
    lexical_score: float
    vector_score: float
    trust_score: float
    quality_score: float
    freshness_score: float
    source_tier_bonus: float
    official_document_boost: float
    current_cycle_boost: float
    approved_claim_boost: float
    direct_rule_boost: float
    stale_penalty: float
    low_trust_penalty: float
    conflict_penalty: float
    rerank_adjustment: float
    final_score: float


@dataclass(slots=True)
class RetrievalCitation:
    citation_key: str
    citation_kind: str
    label: str
    source_name: str | None
    source_tier: SourceTier
    document_id: UUID
    document_version_id: UUID | None
    claim_id: UUID | None
    document_chunk_id: UUID | None
    parsed_block_id: UUID | None
    page_number: int | None
    source_url: str | None
    locator: dict[str, object]
    quoted_text: str | None


@dataclass(slots=True)
class RetrievalConflictInfo:
    conflict_id: UUID
    conflict_type: str
    status: str
    severity_score: float
    winning_claim_id: UUID | None
    other_claim_id: UUID
    other_claim_text: str
    other_source_tier: SourceTier
    resolution_note: str | None
    metadata: dict[str, object]


@dataclass(slots=True)
class RetrievalDiagnostics:
    candidate_count: int
    lexical_candidate_count: int
    vector_candidate_count: int
    reranked: bool
    backend: str
    excluded_tier4: bool


@dataclass(slots=True)
class RetrievalHit:
    record_type: str
    record_id: UUID
    document_id: UUID
    text: str
    title: str | None
    source_tier: SourceTier
    score_breakdown: RetrievalScoreBreakdown
    metadata: dict[str, object]
    citation: RetrievalCitation
    conflicts: list[RetrievalConflictInfo]
    freshness_state: FreshnessState
    conflict_state: RetrievalConflictState


@dataclass(slots=True)
class RetrievalSearchResult:
    hits: list[RetrievalHit]
    diagnostics: RetrievalDiagnostics
    ranking_policy: dict[str, float]
    applied_filters: dict[str, object]


@dataclass(slots=True)
class RetrievalQuery:
    query_text: str
    limit: int = 10
    source_tiers: tuple[SourceTier, ...] | None = None
    admissions_year: int | None = None
    university_id: str | None = None
    admission_cycle_id: str | None = None
    admission_track_id: str | None = None
    document_types: tuple[DocumentType, ...] | None = None
    claim_statuses: tuple[ClaimStatus, ...] | None = None
    freshness_states: tuple[FreshnessState, ...] | None = None
    conflict_states: tuple[RetrievalConflictState, ...] | None = None
    current_cycle_only: bool = False
    approved_claims_only: bool = False
    include_conflicts: bool = True
    include_excluded_sources: bool = False


@dataclass(slots=True)
class _CandidateRecord:
    record: RetrievalIndexRecord
    document: Document
    source: Source | None
    claim: Claim | None
    chunk: DocumentChunk | None
    lexical_score: float = 0.0
    vector_score: float = 0.0
    freshness_state: FreshnessState = FreshnessState.STALE
    conflict_state: RetrievalConflictState = RetrievalConflictState.NONE
    conflicts: list[RetrievalConflictInfo] = field(default_factory=list)


def tokenize_text(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text or "")]


def classify_freshness_state(document: Document) -> FreshnessState:
    settings = get_settings()
    if document.is_current_cycle:
        return FreshnessState.CURRENT
    if document.freshness_score >= settings.retrieval_freshness_threshold:
        return FreshnessState.FRESH
    return FreshnessState.STALE


class HybridRetrievalService:
    def search(self, session: Session, query: RetrievalQuery) -> RetrievalSearchResult:
        backend = session.bind.dialect.name if session.bind is not None else "unknown"
        lexical_scores: dict[UUID, float] = {}
        vector_scores: dict[UUID, float] = {}
        if backend == "postgresql":
            lexical_scores = self._postgres_lexical_candidates(session, query)
            vector_scores = self._postgres_vector_candidates(session, query)
            candidate_ids = set(lexical_scores) | set(vector_scores)
            if not candidate_ids:
                candidates = self._sqlite_like_candidates(session, query)
            else:
                candidates = self._load_candidate_context(session, candidate_ids)
                for candidate in candidates:
                    candidate.lexical_score = lexical_scores.get(candidate.record.id, 0.0)
                    candidate.vector_score = vector_scores.get(candidate.record.id, 0.0)
        else:
            candidates = self._sqlite_like_candidates(session, query)
            lexical_scores = {candidate.record.id: candidate.lexical_score for candidate in candidates}
            vector_scores = {candidate.record.id: candidate.vector_score for candidate in candidates}

        candidates = self._apply_post_filters(candidates, query)
        ranked_hits: list[RetrievalHit] = []
        for candidate in candidates:
            hit = self._assemble_hit(candidate)
            if not query.include_conflicts:
                hit.conflicts = []
            if hit.score_breakdown.final_score > 0:
                ranked_hits.append(hit)

        reranker = retrieval_reranking_service.get_reranker()
        reranked_hits = reranker.rerank(query_text=query.query_text, hits=ranked_hits)
        reranked = reranked_hits != ranked_hits
        if reranked:
            reranked_hits = self._apply_rerank_adjustment(ranked_hits, reranked_hits)

        reranked_hits.sort(key=lambda item: item.score_breakdown.final_score, reverse=True)
        diagnostics = RetrievalDiagnostics(
            candidate_count=len(candidates),
            lexical_candidate_count=len(lexical_scores),
            vector_candidate_count=len(vector_scores),
            reranked=reranked,
            backend=backend,
            excluded_tier4=not query.include_excluded_sources,
        )
        return RetrievalSearchResult(
            hits=reranked_hits[: query.limit],
            diagnostics=diagnostics,
            ranking_policy=self._ranking_policy(),
            applied_filters=self._applied_filters(query),
        )

    def _apply_rerank_adjustment(self, original_hits: list[RetrievalHit], reranked_hits: list[RetrievalHit]) -> list[RetrievalHit]:
        original_rank = {hit.record_id: index for index, hit in enumerate(original_hits)}
        for index, hit in enumerate(reranked_hits):
            prior_rank = original_rank.get(hit.record_id, index)
            adjustment = (prior_rank - index) * 0.01
            hit.score_breakdown.rerank_adjustment = adjustment
            hit.score_breakdown.final_score += adjustment
        return reranked_hits

    def _postgres_lexical_candidates(self, session: Session, query: RetrievalQuery) -> dict[UUID, float]:
        settings = get_settings()
        tsquery = func.plainto_tsquery("simple", query.query_text)
        tsvector = func.to_tsvector("simple", RetrievalIndexRecord.searchable_text)
        lexical_rank = func.ts_rank_cd(tsvector, tsquery)
        stmt = (
            self._base_postgres_stmt(query)
            .add_columns(lexical_rank.label("lexical_rank"))
            .where(lexical_rank > 0)
            .order_by(lexical_rank.desc())
            .limit(settings.retrieval_candidate_pool_size)
        )
        return {record.id: min(1.0, float(rank)) for record, rank in session.execute(stmt).all()}

    def _postgres_vector_candidates(self, session: Session, query: RetrievalQuery) -> dict[UUID, float]:
        settings = get_settings()
        query_embedding = extraction_model_gateway.embed_texts([query.query_text]).vectors[0]
        try:
            similarity = (1 - RetrievalIndexRecord.embedding.cosine_distance(query_embedding))
            stmt = (
                self._base_postgres_stmt(query)
                .add_columns(similarity.label("vector_rank"))
                .where(RetrievalIndexRecord.embedding.is_not(None))
                .order_by(similarity.desc())
                .limit(settings.retrieval_candidate_pool_size)
            )
            return {record.id: max(0.0, min(1.0, float(rank))) for record, rank in session.execute(stmt).all()}
        except Exception:
            return {}

    def _base_postgres_stmt(self, query: RetrievalQuery) -> Select[tuple[RetrievalIndexRecord]]:
        stmt = (
            select(RetrievalIndexRecord)
            .join(Document, RetrievalIndexRecord.document_id == Document.id)
            .where(RetrievalIndexRecord.index_status == RetrievalIndexStatus.INDEXED)
            .where(RetrievalIndexRecord.deleted_at.is_(None))
            .where(Document.deleted_at.is_(None))
        )
        if not query.include_excluded_sources:
            stmt = stmt.where(RetrievalIndexRecord.source_tier != SourceTier.TIER_4_EXCLUDED)
        if query.source_tiers:
            stmt = stmt.where(RetrievalIndexRecord.source_tier.in_(query.source_tiers))
        if query.admissions_year is not None:
            stmt = stmt.where(Document.admissions_year == query.admissions_year)
        if query.university_id is not None:
            stmt = stmt.where(RetrievalIndexRecord.university_id == ensure_uuid(query.university_id))
        if query.admission_cycle_id is not None:
            stmt = stmt.where(RetrievalIndexRecord.admission_cycle_id == ensure_uuid(query.admission_cycle_id))
        if query.admission_track_id is not None:
            stmt = stmt.where(RetrievalIndexRecord.admission_track_id == ensure_uuid(query.admission_track_id))
        if query.document_types:
            stmt = stmt.where(Document.document_type.in_(query.document_types))
        if query.current_cycle_only:
            stmt = stmt.where(Document.is_current_cycle.is_(True))
        return stmt

    def _sqlite_like_candidates(self, session: Session, query: RetrievalQuery) -> list[_CandidateRecord]:
        records = self._load_filtered_records(session, query)
        if not records:
            return []
        query_tokens = tokenize_text(query.query_text)
        query_embedding = extraction_model_gateway.embed_texts([query.query_text]).vectors[0]
        idf_lookup = self._idf_lookup([record.searchable_text for record in records], query_tokens)
        candidates = self._load_candidate_context(session, {record.id for record in records})
        by_id = {candidate.record.id: candidate for candidate in candidates}
        for record in records:
            candidate = by_id[record.id]
            candidate.lexical_score = self._bm25_like_score(record.searchable_text, query_tokens, idf_lookup)
            vector = record.embedding if isinstance(record.embedding, list) else []
            candidate.vector_score = extraction_model_gateway.cosine_similarity(query_embedding, vector)
        return list(by_id.values())

    def _load_filtered_records(self, session: Session, query: RetrievalQuery) -> list[RetrievalIndexRecord]:
        stmt = (
            select(RetrievalIndexRecord)
            .join(Document, RetrievalIndexRecord.document_id == Document.id)
            .where(RetrievalIndexRecord.index_status == RetrievalIndexStatus.INDEXED)
            .where(RetrievalIndexRecord.deleted_at.is_(None))
            .where(Document.deleted_at.is_(None))
        )
        if not query.include_excluded_sources:
            stmt = stmt.where(RetrievalIndexRecord.source_tier != SourceTier.TIER_4_EXCLUDED)
        if query.source_tiers:
            stmt = stmt.where(RetrievalIndexRecord.source_tier.in_(query.source_tiers))
        if query.admissions_year is not None:
            stmt = stmt.where(Document.admissions_year == query.admissions_year)
        if query.university_id is not None:
            stmt = stmt.where(RetrievalIndexRecord.university_id == ensure_uuid(query.university_id))
        if query.admission_cycle_id is not None:
            stmt = stmt.where(RetrievalIndexRecord.admission_cycle_id == ensure_uuid(query.admission_cycle_id))
        if query.admission_track_id is not None:
            stmt = stmt.where(RetrievalIndexRecord.admission_track_id == ensure_uuid(query.admission_track_id))
        if query.document_types:
            stmt = stmt.where(Document.document_type.in_(query.document_types))
        if query.current_cycle_only:
            stmt = stmt.where(Document.is_current_cycle.is_(True))
        return list(session.scalars(stmt))

    def _load_candidate_context(self, session: Session, candidate_ids: set[UUID]) -> list[_CandidateRecord]:
        if not candidate_ids:
            return []
        records = list(
            session.scalars(
                select(RetrievalIndexRecord)
                .where(RetrievalIndexRecord.id.in_(candidate_ids))
                .where(RetrievalIndexRecord.deleted_at.is_(None))
            )
        )
        document_ids = {record.document_id for record in records}
        documents = {
            item.id: item
            for item in session.scalars(
                select(Document)
                .where(Document.id.in_(document_ids))
                .options(selectinload(Document.source))
            )
        }
        claim_ids = {record.record_id for record in records if record.record_type == RetrievalRecordType.CLAIM}
        if claim_ids:
            claim_stmt = (
                select(Claim)
                .where(Claim.id.in_(claim_ids))
                .options(
                    selectinload(Claim.evidence_items).selectinload(ClaimEvidence.parsed_block),
                    selectinload(Claim.evidence_items).selectinload(ClaimEvidence.document_chunk),
                )
            )
            claims = {item.id: item for item in session.scalars(claim_stmt)}
        else:
            claims = {}
        chunk_ids = {record.record_id for record in records if record.record_type == RetrievalRecordType.BLOCK}
        if chunk_ids:
            chunk_stmt = select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)).options(selectinload(DocumentChunk.primary_block))
            chunks = {item.id: item for item in session.scalars(chunk_stmt)}
        else:
            chunks = {}

        conflict_lookup = self._load_conflict_lookup(session, claim_ids)
        candidates: list[_CandidateRecord] = []
        for record in records:
            document = documents[record.document_id]
            claim = claims.get(record.record_id) if record.record_type == RetrievalRecordType.CLAIM else None
            chunk = chunks.get(record.record_id) if record.record_type == RetrievalRecordType.BLOCK else None
            conflicts = conflict_lookup.get(record.record_id, []) if claim is not None else []
            candidates.append(
                _CandidateRecord(
                    record=record,
                    document=document,
                    source=document.source,
                    claim=claim,
                    chunk=chunk,
                    freshness_state=classify_freshness_state(document),
                    conflict_state=self._conflict_state(conflicts),
                    conflicts=conflicts,
                )
            )
        return candidates

    def _load_conflict_lookup(self, session: Session, claim_ids: set[UUID]) -> dict[UUID, list[RetrievalConflictInfo]]:
        if not claim_ids:
            return {}
        rows = list(
            session.scalars(
                select(ConflictRecord)
                .where(
                    (ConflictRecord.primary_claim_id.in_(claim_ids)) | (ConflictRecord.conflicting_claim_id.in_(claim_ids))
                )
                .where(ConflictRecord.deleted_at.is_(None))
            )
        )
        related_claim_ids = {row.primary_claim_id for row in rows} | {row.conflicting_claim_id for row in rows}
        related_claims = {
            item.id: item
            for item in session.scalars(select(Claim).where(Claim.id.in_(related_claim_ids) if related_claim_ids else false()))
        }
        lookup: dict[UUID, list[RetrievalConflictInfo]] = {claim_id: [] for claim_id in claim_ids}
        for row in rows:
            for claim_id, other_id in (
                (row.primary_claim_id, row.conflicting_claim_id),
                (row.conflicting_claim_id, row.primary_claim_id),
            ):
                if claim_id not in lookup:
                    continue
                other_claim = related_claims.get(other_id)
                if other_claim is None:
                    continue
                lookup[claim_id].append(
                    RetrievalConflictInfo(
                        conflict_id=row.id,
                        conflict_type=row.conflict_type.value,
                        status=row.status.value,
                        severity_score=row.severity_score,
                        winning_claim_id=row.winning_claim_id,
                        other_claim_id=other_claim.id,
                        other_claim_text=other_claim.normalized_claim_text,
                        other_source_tier=other_claim.source_tier,
                        resolution_note=row.resolution_note,
                        metadata=row.metadata_json,
                    )
                )
        return lookup

    def _apply_post_filters(self, candidates: list[_CandidateRecord], query: RetrievalQuery) -> list[_CandidateRecord]:
        filtered: list[_CandidateRecord] = []
        for candidate in candidates:
            if query.freshness_states and candidate.freshness_state not in query.freshness_states:
                continue
            if query.conflict_states and candidate.conflict_state not in query.conflict_states:
                continue
            if query.claim_statuses and (candidate.claim is None or candidate.claim.status not in query.claim_statuses):
                continue
            if query.approved_claims_only and (candidate.claim is None or candidate.claim.status != ClaimStatus.APPROVED):
                continue
            filtered.append(candidate)
        return filtered

    def _assemble_hit(self, candidate: _CandidateRecord) -> RetrievalHit:
        breakdown = self._score_candidate(candidate)
        metadata = dict(candidate.record.metadata_json or {})
        metadata.update(
            {
                "document_id": str(candidate.document.id),
                "document_type": candidate.document.document_type.value,
                "is_current_cycle": candidate.document.is_current_cycle,
                "freshness_state": candidate.freshness_state.value,
            }
        )
        if candidate.claim is not None:
            metadata["claim_status"] = candidate.claim.status.value
            metadata["claim_type"] = candidate.claim.claim_type.value
        return RetrievalHit(
            record_type=candidate.record.record_type.value,
            record_id=candidate.record.record_id,
            document_id=candidate.document.id,
            text=candidate.record.searchable_text,
            title=metadata.get("title"),
            source_tier=candidate.record.source_tier,
            score_breakdown=breakdown,
            metadata=metadata,
            citation=self._assemble_citation(candidate),
            conflicts=candidate.conflicts,
            freshness_state=candidate.freshness_state,
            conflict_state=candidate.conflict_state,
        )

    def _score_candidate(self, candidate: _CandidateRecord) -> RetrievalScoreBreakdown:
        settings = get_settings()
        claim = candidate.claim
        source_tier_bonus = {
            SourceTier.TIER_1_OFFICIAL: 0.14,
            SourceTier.TIER_2_PUBLIC_SUPPORT: 0.08,
            SourceTier.TIER_3_CONTROLLED_SECONDARY: 0.01,
            SourceTier.TIER_4_EXCLUDED: -0.25,
        }[candidate.record.source_tier]
        official_document_boost = settings.retrieval_official_document_boost if candidate.document.source_tier == SourceTier.TIER_1_OFFICIAL else 0.0
        current_cycle_boost = settings.retrieval_current_cycle_boost if candidate.document.is_current_cycle else 0.0
        approved_claim_boost = settings.retrieval_approved_claim_boost if claim is not None and claim.status == ClaimStatus.APPROVED else 0.0
        direct_rule_boost = settings.retrieval_direct_rule_boost if claim is not None and claim.is_direct_rule else 0.0
        stale_penalty = settings.retrieval_stale_penalty_weight if candidate.freshness_state == FreshnessState.STALE else 0.0
        low_trust_penalty = settings.retrieval_low_trust_penalty_weight if candidate.document.trust_score < 0.45 else 0.0
        conflict_penalty = self._conflict_penalty(candidate.conflicts, claim)
        final_score = (
            candidate.lexical_score * settings.retrieval_lexical_weight
            + candidate.vector_score * settings.retrieval_vector_weight
            + candidate.document.trust_score * settings.retrieval_trust_weight
            + candidate.record.quality_score * settings.retrieval_quality_weight
            + candidate.document.freshness_score * settings.retrieval_freshness_weight
            + source_tier_bonus
            + official_document_boost
            + current_cycle_boost
            + approved_claim_boost
            + direct_rule_boost
            - stale_penalty
            - low_trust_penalty
            - conflict_penalty
        )
        return RetrievalScoreBreakdown(
            lexical_score=round(candidate.lexical_score, 4),
            vector_score=round(candidate.vector_score, 4),
            trust_score=round(candidate.document.trust_score, 4),
            quality_score=round(candidate.record.quality_score, 4),
            freshness_score=round(candidate.document.freshness_score, 4),
            source_tier_bonus=round(source_tier_bonus, 4),
            official_document_boost=round(official_document_boost, 4),
            current_cycle_boost=round(current_cycle_boost, 4),
            approved_claim_boost=round(approved_claim_boost, 4),
            direct_rule_boost=round(direct_rule_boost, 4),
            stale_penalty=round(stale_penalty, 4),
            low_trust_penalty=round(low_trust_penalty, 4),
            conflict_penalty=round(conflict_penalty, 4),
            rerank_adjustment=0.0,
            final_score=round(final_score, 4),
        )

    def _conflict_penalty(self, conflicts: list[RetrievalConflictInfo], claim: Claim | None) -> float:
        if claim is None or not conflicts:
            return 0.0
        settings = get_settings()
        penalty = 0.0
        for conflict in conflicts:
            if conflict.status == ConflictStatus.DISMISSED.value:
                continue
            penalty += conflict.severity_score * settings.retrieval_conflict_penalty_weight
            if conflict.winning_claim_id is not None and conflict.winning_claim_id != claim.id:
                penalty += 0.05
        return penalty

    def _assemble_citation(self, candidate: _CandidateRecord) -> RetrievalCitation:
        document = candidate.document
        source = candidate.source
        if candidate.claim is not None and candidate.claim.evidence_items:
            evidence = sorted(candidate.claim.evidence_items, key=lambda item: item.evidence_rank)[0]
            chunk = evidence.document_chunk
            parsed_block = evidence.parsed_block
            page_number = evidence.page_number or (parsed_block.page_start if parsed_block is not None else None)
            locator = {
                "source_id": str(source.id) if source is not None else None,
                "document_id": str(document.id),
                "document_version_id": str(candidate.claim.document_version_id),
                "claim_id": str(candidate.claim.id),
                "document_chunk_id": str(chunk.id) if chunk is not None else None,
                "parsed_block_id": str(parsed_block.id) if parsed_block is not None else None,
            }
            return RetrievalCitation(
                citation_key=f"claim:{candidate.claim.id}:{chunk.id if chunk is not None else 'none'}:{page_number or 'na'}",
                citation_kind="claim",
                label=f"{source.name if source is not None else 'Source'} / {document.canonical_title}",
                source_name=source.name if source is not None else None,
                source_tier=candidate.record.source_tier,
                document_id=document.id,
                document_version_id=candidate.claim.document_version_id,
                claim_id=candidate.claim.id,
                document_chunk_id=chunk.id if chunk is not None else None,
                parsed_block_id=parsed_block.id if parsed_block is not None else None,
                page_number=page_number,
                source_url=document.source_url,
                locator=locator,
                quoted_text=evidence.evidence_text,
            )

        chunk = candidate.chunk
        page_number = chunk.page_start if chunk is not None else None
        return RetrievalCitation(
            citation_key=f"chunk:{chunk.id if chunk is not None else candidate.record.id}:{page_number or 'na'}",
            citation_kind="chunk",
            label=f"{source.name if source is not None else 'Source'} / {document.canonical_title}",
            source_name=source.name if source is not None else None,
            source_tier=candidate.record.source_tier,
            document_id=document.id,
            document_version_id=chunk.document_version_id if chunk is not None else document.current_version_id,
            claim_id=None,
            document_chunk_id=chunk.id if chunk is not None else None,
            parsed_block_id=chunk.primary_block_id if chunk is not None else None,
            page_number=page_number,
            source_url=document.source_url,
            locator={
                "source_id": str(source.id) if source is not None else None,
                "document_id": str(document.id),
                "document_version_id": str(chunk.document_version_id) if chunk is not None else str(document.current_version_id),
                "document_chunk_id": str(chunk.id) if chunk is not None else None,
            },
            quoted_text=(chunk.content_text[:220] if chunk is not None else candidate.record.searchable_text[:220]),
        )

    def _conflict_state(self, conflicts: list[RetrievalConflictInfo]) -> RetrievalConflictState:
        if not conflicts:
            return RetrievalConflictState.NONE
        if any(conflict.status == ConflictStatus.OPEN.value for conflict in conflicts):
            return RetrievalConflictState.OPEN
        return RetrievalConflictState.RESOLVED

    def _idf_lookup(self, texts: list[str], query_tokens: list[str]) -> dict[str, float]:
        corpus_tokens = [set(tokenize_text(text)) for text in texts]
        document_count = max(1, len(corpus_tokens))
        lookup: dict[str, float] = {}
        for token in query_tokens:
            containing = sum(1 for tokens in corpus_tokens if token in tokens)
            lookup[token] = 1.0 + max(0.0, (document_count - containing + 0.5) / (containing + 0.5))
        return lookup

    def _bm25_like_score(self, text: str, query_tokens: list[str], idf_lookup: dict[str, float]) -> float:
        if not query_tokens:
            return 0.0
        text_tokens = tokenize_text(text)
        if not text_tokens:
            return 0.0
        score = 0.0
        average_length = max(1.0, sum(len(token) for token in text_tokens) / max(1, len(text_tokens)))
        for token in query_tokens:
            term_frequency = text_tokens.count(token)
            if term_frequency == 0:
                continue
            denominator = term_frequency + 1.2 * (1 - 0.75 + 0.75 * (len(text_tokens) / average_length))
            score += idf_lookup.get(token, 1.0) * ((term_frequency * 2.2) / denominator)
        normalized = score / max(1.0, len(query_tokens) * 2.0)
        if query_tokens and " ".join(query_tokens) in " ".join(text_tokens):
            normalized += 0.12
        return max(0.0, min(1.0, normalized))

    def _applied_filters(self, query: RetrievalQuery) -> dict[str, object]:
        return {
            "source_tiers": [item.value for item in query.source_tiers] if query.source_tiers else None,
            "admissions_year": query.admissions_year,
            "university_id": query.university_id,
            "admission_cycle_id": query.admission_cycle_id,
            "admission_track_id": query.admission_track_id,
            "document_types": [item.value for item in query.document_types] if query.document_types else None,
            "claim_statuses": [item.value for item in query.claim_statuses] if query.claim_statuses else None,
            "freshness_states": [item.value for item in query.freshness_states] if query.freshness_states else None,
            "conflict_states": [item.value for item in query.conflict_states] if query.conflict_states else None,
            "current_cycle_only": query.current_cycle_only,
            "approved_claims_only": query.approved_claims_only,
            "include_conflicts": query.include_conflicts,
        }

    def _ranking_policy(self) -> dict[str, float]:
        settings = get_settings()
        return {
            "lexical_weight": settings.retrieval_lexical_weight,
            "vector_weight": settings.retrieval_vector_weight,
            "trust_weight": settings.retrieval_trust_weight,
            "quality_weight": settings.retrieval_quality_weight,
            "freshness_weight": settings.retrieval_freshness_weight,
            "official_document_boost": settings.retrieval_official_document_boost,
            "current_cycle_boost": settings.retrieval_current_cycle_boost,
            "approved_claim_boost": settings.retrieval_approved_claim_boost,
            "direct_rule_boost": settings.retrieval_direct_rule_boost,
            "conflict_penalty_weight": settings.retrieval_conflict_penalty_weight,
            "stale_penalty_weight": settings.retrieval_stale_penalty_weight,
            "low_trust_penalty_weight": settings.retrieval_low_trust_penalty_weight,
        }


hybrid_retrieval_service = HybridRetrievalService()
