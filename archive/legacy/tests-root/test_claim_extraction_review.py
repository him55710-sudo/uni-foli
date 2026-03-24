from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from domain.enums import ClaimType, DocumentType, SourceTier
from services.admissions.chunk_selection_service import chunk_selection_service
from services.admissions.claim_extraction.base import ClaimExtractionExecutionResult
from services.admissions.claim_extraction.errors import EmptyExtractionResponseError
from services.admissions.claim_extraction.schemas import ClaimExtractionBatch, ExtractedClaim
from tests.helpers import login_headers, make_client


def _seed_document(client, *, text: str) -> str:
    source_response = client.post(
        "/api/v1/sources",
        json={
            "name": "Official Admissions",
            "organization_name": "Example University",
            "base_url": "https://admissions.example.ac.kr",
            "source_tier": "tier_1_official",
            "source_category": "university",
            "is_official": True,
            "allow_crawl": True,
            "freshness_days": 30,
            "crawl_policy": {"allowed_paths": ["/guidebook"]},
        },
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/sources/{source_id}/files",
        files={"file": ("2026-guide.txt", text.encode("utf-8"), "text/plain")},
        data={"source_url": "https://admissions.example.ac.kr/guidebook/2026-guide"},
    )
    assert upload_response.status_code == 201
    job_id = upload_response.json()["ingestion_job_id"]

    job_run_response = client.post(f"/api/v1/ingestion/jobs/{job_id}/run")
    assert job_run_response.status_code == 200
    return job_run_response.json()["document_id"]


def test_chunk_selection_prefers_evaluation_sections() -> None:
    document = SimpleNamespace(
        document_type=DocumentType.EVALUATION_GUIDE,
        source_tier=SourceTier.TIER_1_OFFICIAL,
        is_current_cycle=True,
    )
    evaluation_chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=0,
        content_text="서류평가에서는 수업역량과 전공적합성을 종합적으로 평가하고 탐구 과정과 분석 과정을 본다.",
        heading_path=["서류평가"],
        page_start=1,
    )
    noise_chunk = SimpleNamespace(
        id=uuid4(),
        chunk_index=1,
        content_text="문의 02-000-0000 copyright all rights reserved 개인정보 처리방침",
        heading_path=["문의"],
        page_start=28,
    )

    decisions = chunk_selection_service.evaluate(
        document=document,
        chunks=[evaluation_chunk, noise_chunk],
        strategy_key="official_evaluation_focus",
    )

    assert decisions[0].selected is True
    assert "evaluation_terms" in decisions[0].reason_codes
    assert decisions[1].selected is False
    assert "boilerplate_or_noise" in decisions[1].reason_codes


def test_prompt_version_and_trace_capture(tmp_path, monkeypatch) -> None:
    from services.admissions.claim_extraction import ollama_extractor as extractor_module

    def fake_extract(request):
        return ClaimExtractionExecutionResult(
            batch=ClaimExtractionBatch(
                claims=[
                    ExtractedClaim(
                        claim_text="수업역량은 교과 탐구의 지속성과 분석 과정을 본다.",
                        normalized_claim_text="수업역량은 교과 탐구의 지속성과 분석 과정을 본다.",
                        claim_type=ClaimType.EVALUATION_CRITERION,
                        source_tier=SourceTier.TIER_1_OFFICIAL,
                        target_evaluation_dimension="academic_competence",
                        applicable_from_year=2026,
                        applicable_to_year=2026,
                        applicable_cycle_label="수시",
                        confidence_score=0.93,
                        evidence_quote=request.chunks[0].content_text[:100],
                        evidence_page_number=request.chunks[0].page_start,
                        evidence_chunk_index=request.chunks[0].chunk_index,
                        rationale="공식 가이드의 직접 진술이다.",
                        evidence_quality_score=0.91,
                    )
                ]
            ),
            provider_name="ollama",
            model_name="ollama/llama3.1:8b",
            latency_ms=321,
            trace_id="trace-123",
            observation_id="obs-456",
            request_payload={"chunk_indexes": [chunk.chunk_index for chunk in request.chunks]},
            response_payload={"claims": [{"claim_text": "수업역량은 교과 탐구의 지속성과 분석 과정을 본다."}]},
            usage_details={"prompt_tokens": 10, "completion_tokens": 20},
        )

    monkeypatch.setattr(extractor_module.claim_extractor, "extract", fake_extract)

    with make_client(tmp_path, database_name="claim-review.db") as client:
        admin = login_headers(client, email="admin@local.polio")
        document_id = _seed_document(
            client,
            text=(
                "# 2026학년도 모집요강\n"
                "서류평가에서는 수업역량과 전공적합성을 함께 본다.\n"
                "교과 탐구의 지속성과 분석 과정, 수업 맥락을 중요하게 평가한다.\n"
            ),
        )
        response = client.post("/api/v1/claims/extract", json={"document_id": document_id})
        assert response.status_code == 202
        payload = response.json()
        assert payload["prompt_template_version"] == "2.0.0"
        assert payload["trace_id"] == "trace-123"
        assert payload["claims_extracted_count"] == 1

        batch_response = client.get(f"/api/v1/admin/extraction/jobs/{payload['id']}/batches", headers=admin)
        assert batch_response.status_code == 200
        batches = batch_response.json()
        assert batches[0]["trace_id"] == "trace-123"
        assert batches[0]["prompt_template_version"] == "2.0.0"

        decisions_response = client.get(f"/api/v1/admin/extraction/jobs/{payload['id']}/chunk-decisions", headers=admin)
        assert decisions_response.status_code == 200
        assert any(item["status"] == "selected" for item in decisions_response.json())


def test_extraction_failure_persistence(tmp_path, monkeypatch) -> None:
    from services.admissions.claim_extraction import ollama_extractor as extractor_module

    def failing_extract(request):
        raise EmptyExtractionResponseError("empty extraction payload")

    monkeypatch.setattr(extractor_module.claim_extractor, "extract", failing_extract)

    with make_client(tmp_path, database_name="claim-review.db") as client:
        document_id = _seed_document(
            client,
            text="# 2026학년도 모집요강\n서류평가에서는 수업역량을 평가한다.\n",
        )
        response = client.post("/api/v1/claims/extract", json={"document_id": document_id})
        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "failed"
        assert payload["failed_batch_count"] == 1
