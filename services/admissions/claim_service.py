from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from time import sleep

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from db.models.admissions import EvaluationDimension, Source
from db.models.content import (
    Claim,
    ClaimEvidence,
    Document,
    DocumentChunk,
    ExtractionBatchRun,
    ExtractionChunkDecision,
    ExtractionJob,
    ParsedBlock,
)
from domain.enums import (
    ClaimStatus,
    ClaimType,
    DocumentStatus,
    ExtractionBatchStatus,
    ExtractionChunkDecisionStatus,
    ExtractionFailureCode,
    ExtractionJobStatus,
    ReviewTaskType,
)
from services.admissions.chunk_selection_service import ChunkSelectionDecisionDraft, chunk_selection_service
from services.admissions.claim_extraction.base import ClaimExtractionExecutionResult, ClaimExtractionRequest
from services.admissions.claim_extraction.errors import (
    EmptyExtractionResponseError,
    ExtractionResponseParseError,
    ExtractionSchemaValidationError,
)
from services.admissions.claim_extraction.ollama_extractor import claim_extractor
from services.admissions.model_gateway import ModelGatewayException, extraction_model_gateway
from services.admissions.prompt_registry import prompt_registry
from services.admissions.quality_service import quality_scoring_service
from services.admissions.retrieval_index_service import retrieval_index_service
from services.admissions.review_service import review_service
from services.admissions.utils import ensure_uuid


DIRECT_RULE_TYPES = {
    ClaimType.DOCUMENT_RULE,
    ClaimType.POLICY_STATEMENT,
    ClaimType.ELIGIBILITY_CONDITION,
    ClaimType.CAUTION_RULE,
}


class ClaimService:
    def list_claims(self, session: Session, *, status: ClaimStatus | None = None) -> list[Claim]:
        stmt = select(Claim).order_by(Claim.created_at.desc())
        if status is not None:
            stmt = stmt.where(Claim.status == status)
        return list(session.scalars(stmt))

    def get_claim(self, session: Session, claim_id: str) -> Claim | None:
        return session.get(Claim, ensure_uuid(claim_id))

    def list_claims_for_document(self, session: Session, *, document_id: str) -> list[Claim]:
        stmt = (
            select(Claim)
            .where(Claim.document_id == ensure_uuid(document_id))
            .options(selectinload(Claim.evidence_items))
            .order_by(Claim.created_at.desc())
        )
        return list(session.scalars(stmt))

    def list_extraction_jobs(self, session: Session) -> list[ExtractionJob]:
        stmt = (
            select(ExtractionJob)
            .options(selectinload(ExtractionJob.batch_runs), selectinload(ExtractionJob.chunk_decisions))
            .order_by(ExtractionJob.created_at.desc())
        )
        return list(session.scalars(stmt))

    def get_extraction_job(self, session: Session, extraction_job_id: str) -> ExtractionJob | None:
        stmt = (
            select(ExtractionJob)
            .where(ExtractionJob.id == ensure_uuid(extraction_job_id))
            .options(selectinload(ExtractionJob.batch_runs), selectinload(ExtractionJob.chunk_decisions))
        )
        return session.scalar(stmt)

    def list_extraction_batches(self, session: Session, *, extraction_job_id: str) -> list[ExtractionBatchRun]:
        stmt = (
            select(ExtractionBatchRun)
            .where(ExtractionBatchRun.extraction_job_id == ensure_uuid(extraction_job_id))
            .order_by(ExtractionBatchRun.batch_index.asc())
        )
        return list(session.scalars(stmt))

    def list_chunk_decisions(self, session: Session, *, extraction_job_id: str) -> list[ExtractionChunkDecision]:
        stmt = (
            select(ExtractionChunkDecision)
            .where(ExtractionChunkDecision.extraction_job_id == ensure_uuid(extraction_job_id))
            .order_by(ExtractionChunkDecision.priority_score.desc(), ExtractionChunkDecision.created_at.asc())
        )
        return list(session.scalars(stmt))

    def list_extraction_failures(self, session: Session) -> list[dict[str, object]]:
        stmt = (
            select(ExtractionBatchRun, ExtractionJob, Document, Source)
            .join(ExtractionJob, ExtractionBatchRun.extraction_job_id == ExtractionJob.id)
            .join(Document, ExtractionJob.document_id == Document.id)
            .outerjoin(Source, Document.source_id == Source.id)
            .where(ExtractionBatchRun.status == ExtractionBatchStatus.FAILED)
            .order_by(ExtractionBatchRun.created_at.desc())
        )
        failures: list[dict[str, object]] = []
        for batch, job, document, source in session.execute(stmt).all():
            failures.append(
                {
                    "id": batch.id,
                    "extraction_job_id": job.id,
                    "document_id": document.id,
                    "batch_id": batch.id,
                    "source_id": source.id if source is not None else None,
                    "model_provider": batch.model_provider,
                    "model_name": batch.model_name,
                    "prompt_template_key": batch.prompt_template_key,
                    "prompt_template_version": batch.prompt_template_version,
                    "failure_reason_code": batch.failure_reason_code,
                    "error_message": batch.error_message,
                    "trace_id": batch.trace_id,
                    "created_at": batch.created_at,
                }
            )
        return failures

    def list_extraction_stats(self, session: Session) -> list[dict[str, object]]:
        jobs = list(
            session.scalars(
                select(ExtractionJob)
                .options(selectinload(ExtractionJob.batch_runs), selectinload(ExtractionJob.document).selectinload(Document.source))
                .order_by(ExtractionJob.created_at.desc())
            )
        )
        aggregates: dict[tuple[str | None, str | None, str, str], dict[str, object]] = {}
        for job in jobs:
            source = job.document.source if job.document is not None else None
            key = (
                str(source.id) if source is not None else None,
                source.name if source is not None else None,
                job.model_provider,
                job.model_name,
            )
            bucket = aggregates.setdefault(
                key,
                {
                    "source_id": key[0],
                    "source_name": key[1],
                    "model_provider": key[2],
                    "model_name": key[3],
                    "total_jobs": 0,
                    "total_batches": 0,
                    "failed_batches": 0,
                    "claims_extracted_count": 0,
                    "latencies": [],
                },
            )
            bucket["total_jobs"] += 1
            bucket["claims_extracted_count"] += job.claims_extracted_count
            bucket["total_batches"] += len(job.batch_runs)
            bucket["failed_batches"] += sum(1 for batch in job.batch_runs if batch.status == ExtractionBatchStatus.FAILED)
            bucket["latencies"].extend(batch.latency_ms for batch in job.batch_runs if batch.latency_ms is not None)

        rows: list[dict[str, object]] = []
        for bucket in aggregates.values():
            latencies = bucket.pop("latencies")
            bucket["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2) if latencies else None
            rows.append(bucket)
        rows.sort(key=lambda item: (item["source_name"] or "", item["model_provider"], item["model_name"]))
        return rows

    def extract_claims_for_document(
        self,
        session: Session,
        *,
        document_id: str,
        model_name: str | None = None,
        chunk_indexes: list[int] | None = None,
        strategy_key: str | None = None,
    ) -> ExtractionJob:
        document = session.get(Document, ensure_uuid(document_id))
        if document is None or document.current_version_id is None:
            raise ValueError("Document not found or missing current version.")

        all_chunks = list(
            session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.chunk_index.asc())
            )
        )
        blocks = list(
            session.scalars(
                select(ParsedBlock).where(ParsedBlock.document_id == document.id).order_by(ParsedBlock.block_index.asc())
            )
        )
        prompt_template = prompt_registry.get(get_settings().extraction_prompt_key)
        model_config = extraction_model_gateway.get_config(model_name_override=model_name)
        strategy = chunk_selection_service.resolve_strategy(document=document, override=strategy_key)
        decisions = chunk_selection_service.evaluate(
            document=document,
            chunks=all_chunks,
            strategy_key=strategy,
            manual_chunk_indexes=chunk_indexes,
        )

        extraction_job = ExtractionJob(
            document_id=document.id,
            document_version_id=document.current_version_id,
            status=ExtractionJobStatus.RUNNING,
            extractor_name=claim_extractor.name,
            model_provider=model_config.provider,
            model_name=model_config.litellm_model,
            prompt_template_key=prompt_template.key,
            prompt_template_version=prompt_template.version,
            selection_policy_key=strategy,
            chunk_count=sum(1 for decision in decisions if decision.selected),
            batch_count=0,
            started_at=datetime.now(UTC),
            job_config={
                "document_id": str(document.id),
                "manual_chunk_indexes": chunk_indexes or [],
                "batch_size": model_config.batch_size,
                "max_retries": model_config.max_retries,
            },
            selection_summary_json=self._build_selection_summary(decisions),
        )
        session.add(extraction_job)
        session.flush()
        self._persist_chunk_decisions(session, extraction_job=extraction_job, decisions=decisions)

        selected_chunks = [decision.chunk for decision in decisions if decision.selected]
        if not selected_chunks:
            extraction_job.status = ExtractionJobStatus.REVIEW_REQUIRED
            extraction_job.failure_reason_code = ExtractionFailureCode.NO_CANDIDATE_CHUNKS
            extraction_job.error_message = "No chunks matched the extraction selection policy."
            extraction_job.finished_at = datetime.now(UTC)
            review_service.create_review_task(
                session,
                task_type=ReviewTaskType.EXTRACTION_FAILURE_REVIEW,
                target_kind="extraction_job",
                target_id=extraction_job.id,
                rationale="No candidate chunks matched the extraction policy. Manual inspection required.",
                priority=2,
                metadata_json={"document_id": str(document.id), "strategy_key": strategy},
            )
            session.flush()
            session.refresh(extraction_job)
            return extraction_job

        chunk_lookup = {chunk.chunk_index: chunk for chunk in selected_chunks}
        block_lookup = {block.id: block for block in blocks}
        decision_lookup = {decision.chunk.id: decision for decision in decisions}
        dimension_lookup = {
            item.code: item.id
            for item in session.scalars(select(EvaluationDimension))
        }

        batches = self._build_batches(selected_chunks, model_config.batch_size)
        extraction_job.batch_count = len(batches)
        created_count = 0
        low_confidence_count = 0
        batch_failures = 0
        retry_count = 0

        for batch_index, batch_chunks in enumerate(batches):
            batch_run = ExtractionBatchRun(
                extraction_job_id=extraction_job.id,
                batch_index=batch_index,
                status=ExtractionBatchStatus.QUEUED,
                model_provider=model_config.provider,
                model_name=model_config.litellm_model,
                prompt_template_key=prompt_template.key,
                prompt_template_version=prompt_template.version,
                chunk_count=len(batch_chunks),
                request_payload={
                    "chunk_indexes": [chunk.chunk_index for chunk in batch_chunks],
                    "strategy_key": strategy,
                },
                response_payload={},
                metadata_json={},
            )
            session.add(batch_run)
            session.flush()

            result, attempts_used = self._execute_batch(
                session,
                batch_run=batch_run,
                document=document,
                batch_chunks=batch_chunks,
                prompt_template=prompt_template,
                model_name=model_name,
                strategy_key=strategy,
            )
            retry_count += max(0, attempts_used - 1)

            if result is None:
                batch_failures += 1
                continue

            extraction_job.successful_batch_count += 1
            extraction_job.last_latency_ms = result.latency_ms
            extraction_job.trace_id = extraction_job.trace_id or result.trace_id

            for extracted in result.batch.claims:
                claim_hash = sha256(extracted.normalized_claim_text.encode("utf-8")).hexdigest()
                existing_claim = session.scalar(
                    select(Claim).where(
                        Claim.document_version_id == document.current_version_id,
                        Claim.claim_hash == claim_hash,
                    )
                )
                if existing_claim is not None:
                    continue

                matched_chunk = None
                if extracted.evidence_chunk_index is not None:
                    matched_chunk = chunk_lookup.get(extracted.evidence_chunk_index)
                if matched_chunk is None and batch_chunks:
                    matched_chunk = batch_chunks[0]
                matched_block = block_lookup.get(matched_chunk.primary_block_id) if matched_chunk is not None else None
                evidence_quality_score = extracted.evidence_quality_score or extracted.confidence_score
                overclaim_flagged = extracted.claim_type == ClaimType.INTERPRETATION_NOTE and extracted.confidence_score < 0.7
                unsafe_flagged = False

                claim = Claim(
                    document_id=document.id,
                    document_version_id=document.current_version_id,
                    extraction_job_id=extraction_job.id,
                    evaluation_dimension_id=dimension_lookup.get(extracted.target_evaluation_dimension),
                    claim_type=extracted.claim_type,
                    claim_text=extracted.claim_text,
                    normalized_claim_text=extracted.normalized_claim_text,
                    claim_hash=claim_hash,
                    source_tier=extracted.source_tier,
                    applicable_from_year=extracted.applicable_from_year,
                    applicable_to_year=extracted.applicable_to_year,
                    applicable_cycle_label=extracted.applicable_cycle_label,
                    confidence_score=extracted.confidence_score,
                    quality_score=quality_scoring_service.claim_quality_score(
                        claim_type=extracted.claim_type,
                        confidence_score=extracted.confidence_score,
                        has_evidence=matched_block is not None,
                        source_tier=extracted.source_tier,
                    ),
                    overclaim_risk_score=max(0.0, 1.0 - extracted.confidence_score),
                    evidence_quality_score=evidence_quality_score,
                    is_direct_quote_based=True,
                    is_direct_rule=extracted.claim_type in DIRECT_RULE_TYPES,
                    unsafe_flagged=unsafe_flagged,
                    overclaim_flagged=overclaim_flagged,
                    model_provider=result.provider_name,
                    model_name=result.model_name,
                    prompt_template_key=prompt_template.key,
                    prompt_template_version=prompt_template.version,
                    status=ClaimStatus.PENDING_REVIEW,
                    metadata_json={
                        "rationale": extracted.rationale,
                        "batch_index": batch_index,
                        "strategy_key": strategy,
                        "trace_id": result.trace_id,
                        "observation_id": result.observation_id,
                        "selection_reason_codes": decision_lookup.get(matched_chunk.id).reason_codes if matched_chunk is not None else [],
                    },
                )
                session.add(claim)
                session.flush()

                if matched_block is not None:
                    session.add(
                        ClaimEvidence(
                            claim_id=claim.id,
                            parsed_block_id=matched_block.id,
                            document_chunk_id=matched_chunk.id if matched_chunk is not None else None,
                            document_version_id=document.current_version_id,
                            evidence_rank=1,
                            page_number=extracted.evidence_page_number or matched_block.page_start,
                            char_start=matched_block.char_start,
                            char_end=matched_block.char_end,
                            evidence_text=extracted.evidence_quote,
                            confidence_score=evidence_quality_score,
                        )
                    )

                retrieval_index_service.upsert_claim_record(session, claim=claim)
                created_count += 1
                if claim.confidence_score < 0.65 or claim.evidence_quality_score < 0.65 or claim.overclaim_flagged:
                    low_confidence_count += 1

        extraction_job.claims_extracted_count = created_count
        extraction_job.failed_batch_count = batch_failures
        extraction_job.retry_count = retry_count
        extraction_job.finished_at = datetime.now(UTC)

        if created_count > 0:
            document.status = DocumentStatus.EXTRACTED
            extraction_job.status = ExtractionJobStatus.SUCCEEDED if batch_failures == 0 and low_confidence_count == 0 else ExtractionJobStatus.REVIEW_REQUIRED
            review_service.create_review_task(
                session,
                task_type=ReviewTaskType.CLAIM_APPROVAL,
                target_kind="extraction_job",
                target_id=extraction_job.id,
                rationale=f"{created_count} claims extracted and waiting for reviewer approval.",
                priority=2 if low_confidence_count == 0 else 1,
                metadata_json={
                    "document_id": str(document.id),
                    "claims_extracted_count": created_count,
                    "low_confidence_claims": low_confidence_count,
                },
            )
        else:
            extraction_job.status = ExtractionJobStatus.REVIEW_REQUIRED if batch_failures < len(batches) else ExtractionJobStatus.FAILED
            extraction_job.failure_reason_code = (
                ExtractionFailureCode.ALL_BATCHES_FAILED if batch_failures == len(batches) else ExtractionFailureCode.EMPTY_RESPONSE
            )
            extraction_job.error_message = extraction_job.error_message or "No reviewable claims were extracted."
            review_service.create_review_task(
                session,
                task_type=ReviewTaskType.EXTRACTION_FAILURE_REVIEW,
                target_kind="extraction_job",
                target_id=extraction_job.id,
                rationale="Extraction finished without reviewable claims. Manual review required.",
                priority=1,
                metadata_json={"document_id": str(document.id), "failed_batches": batch_failures},
            )

        session.flush()
        session.refresh(extraction_job)
        return extraction_job

    def _build_selection_summary(self, decisions: list[ChunkSelectionDecisionDraft]) -> dict[str, object]:
        selected_reasons: Counter[str] = Counter()
        skipped_reasons: Counter[str] = Counter()
        for decision in decisions:
            target = selected_reasons if decision.selected else skipped_reasons
            target.update(decision.reason_codes)
        return {
            "total_chunks": len(decisions),
            "selected_chunks": sum(1 for decision in decisions if decision.selected),
            "skipped_chunks": sum(1 for decision in decisions if not decision.selected),
            "selected_reason_counts": dict(selected_reasons),
            "skipped_reason_counts": dict(skipped_reasons),
        }

    def _persist_chunk_decisions(
        self,
        session: Session,
        *,
        extraction_job: ExtractionJob,
        decisions: list[ChunkSelectionDecisionDraft],
    ) -> None:
        for decision in decisions:
            session.add(
                ExtractionChunkDecision(
                    extraction_job_id=extraction_job.id,
                    document_chunk_id=decision.chunk.id,
                    status=(
                        ExtractionChunkDecisionStatus.SELECTED
                        if decision.selected
                        else ExtractionChunkDecisionStatus.SKIPPED
                    ),
                    selection_policy_key=decision.strategy_key,
                    priority_score=decision.priority_score,
                    reason_codes=decision.reason_codes,
                    metadata_json={
                        "chunk_index": decision.chunk.chunk_index,
                        "page_start": decision.chunk.page_start,
                        "heading_path": decision.chunk.heading_path,
                    },
                )
            )
        session.flush()

    def _build_batches(self, chunks: list[DocumentChunk], batch_size: int) -> list[list[DocumentChunk]]:
        ordered = sorted(chunks, key=lambda chunk: chunk.chunk_index)
        return [ordered[index : index + batch_size] for index in range(0, len(ordered), batch_size)]

    def _execute_batch(
        self,
        session: Session,
        *,
        batch_run: ExtractionBatchRun,
        document: Document,
        batch_chunks: list[DocumentChunk],
        prompt_template,
        model_name: str | None,
        strategy_key: str,
    ) -> tuple[ClaimExtractionExecutionResult | None, int]:
        settings = get_settings()
        attempts = settings.extraction_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            batch_run.status = ExtractionBatchStatus.RUNNING
            batch_run.attempt_count = attempt
            batch_run.started_at = datetime.now(UTC)
            batch_run.error_message = None
            session.flush()

            try:
                raw_result = claim_extractor.extract(
                    ClaimExtractionRequest(
                        document_id=str(document.id),
                        document_version_id=str(document.current_version_id),
                        chunks=batch_chunks,
                        source_tier=document.source_tier.value,
                        model_name=model_name,
                        prompt_template=prompt_template,
                        batch_index=batch_run.batch_index,
                        strategy_key=strategy_key,
                    )
                )
                result = self._normalize_extraction_result(raw_result, batch_chunks=batch_chunks)
                batch_run.status = ExtractionBatchStatus.SUCCEEDED
                batch_run.failure_reason_code = None
                batch_run.latency_ms = result.latency_ms
                batch_run.trace_id = result.trace_id
                batch_run.observation_id = result.observation_id
                batch_run.finished_at = datetime.now(UTC)
                batch_run.request_payload = result.request_payload
                batch_run.response_payload = result.response_payload
                batch_run.metadata_json = {"usage_details": result.usage_details}
                session.flush()
                return result, attempt
            except Exception as exc:
                last_error = exc
                batch_run.failure_reason_code = self._classify_failure(exc)
                batch_run.error_message = str(exc)
                batch_run.finished_at = datetime.now(UTC)
                if isinstance(exc, ModelGatewayException):
                    batch_run.trace_id = exc.trace_id
                    batch_run.observation_id = exc.observation_id
                    batch_run.latency_ms = exc.latency_ms
                session.flush()
                if attempt < attempts:
                    sleep(settings.extraction_retry_backoff_seconds * attempt)

        batch_run.status = ExtractionBatchStatus.FAILED
        batch_run.metadata_json = {"final_attempts": attempts}
        session.flush()
        review_service.create_review_task(
            session,
            task_type=ReviewTaskType.EXTRACTION_FAILURE_REVIEW,
            target_kind="extraction_batch_run",
            target_id=batch_run.id,
            rationale=f"Extraction batch {batch_run.batch_index} failed after {attempts} attempts.",
            priority=1,
            metadata_json={
                "document_id": str(document.id),
                "failure_reason_code": batch_run.failure_reason_code.value if batch_run.failure_reason_code else None,
                "error_message": str(last_error) if last_error is not None else None,
            },
        )
        return None, attempts

    def _normalize_extraction_result(
        self,
        raw_result: ClaimExtractionExecutionResult | object,
        *,
        batch_chunks: list[DocumentChunk],
    ) -> ClaimExtractionExecutionResult:
        if isinstance(raw_result, ClaimExtractionExecutionResult):
            return raw_result
        batch = getattr(raw_result, "claims", None)
        if batch is None:
            raise TypeError("Unsupported extraction result type.")
        return ClaimExtractionExecutionResult(
            batch=raw_result,
            provider_name="unknown",
            model_name="unknown",
            latency_ms=None,
            trace_id=None,
            observation_id=None,
            request_payload={"chunk_indexes": [chunk.chunk_index for chunk in batch_chunks]},
            response_payload=raw_result.model_dump() if hasattr(raw_result, "model_dump") else {"claims": []},
            usage_details={},
        )

    def _classify_failure(self, exc: Exception) -> ExtractionFailureCode:
        if isinstance(exc, TimeoutError):
            return ExtractionFailureCode.TIMEOUT
        if isinstance(exc, EmptyExtractionResponseError):
            return ExtractionFailureCode.EMPTY_RESPONSE
        if isinstance(exc, (ExtractionSchemaValidationError, ExtractionResponseParseError)):
            return ExtractionFailureCode.SCHEMA_VALIDATION_FAILED
        if isinstance(exc, ModelGatewayException) and "timeout" in str(exc).lower():
            return ExtractionFailureCode.TIMEOUT
        return ExtractionFailureCode.GATEWAY_ERROR


claim_service = ClaimService()
