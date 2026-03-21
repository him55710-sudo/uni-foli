from __future__ import annotations

from pathlib import Path

from services.admissions.claim_extraction.schemas import ClaimExtractionBatch, ExtractedClaim
from tests.helpers import login_headers, make_client


def test_source_ingestion_to_claim_retrieval_flow(tmp_path: Path, monkeypatch) -> None:
    from services.admissions.claim_extraction import ollama_extractor as extractor_module

    def fake_extract(request) -> ClaimExtractionBatch:
        assert request.chunks
        return ClaimExtractionBatch(
            claims=[
                ExtractedClaim(
                    claim_text="Academic competence is evaluated through sustained inquiry and evidence-based coursework.",
                    normalized_claim_text="Academic competence is evaluated through sustained inquiry and evidence-based coursework.",
                    claim_type="evaluation_criterion",
                    source_tier="tier_1_official",
                    target_evaluation_dimension="academic_competence",
                    applicable_from_year=2026,
                    applicable_to_year=2026,
                    applicable_cycle_label="susi",
                    confidence_score=0.92,
                    evidence_quote=request.chunks[0].content_text[:120],
                    evidence_page_number=request.chunks[0].page_start,
                    evidence_chunk_index=request.chunks[0].chunk_index,
                    rationale="Direct statement from the uploaded admissions guide.",
                )
            ]
        )

    monkeypatch.setattr(extractor_module.ollama_claim_extractor, "extract", fake_extract)

    with make_client(tmp_path, database_name="vertical-slice.db") as client:
        admin = login_headers(client, email="admin@local.polio")
        source_response = client.post(
            "/api/v1/sources",
            json={
                "name": "Admissions Office",
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
            files={
                "file": (
                    "2026-guide.txt",
                    (
                        "2026 Admissions Guide\n"
                        "Academic competence is evaluated through coursework, inquiry, and demonstrated growth.\n"
                        "Career exploration is evaluated through authentic major-related activity."
                    ).encode("utf-8"),
                    "text/plain",
                )
            },
            data={"source_url": "https://admissions.example.ac.kr/guidebook/2026-guide"},
        )
        assert upload_response.status_code == 201
        ingestion_job_id = upload_response.json()["ingestion_job_id"]

        job_run_response = client.post(f"/api/v1/ingestion/jobs/{ingestion_job_id}/run")
        assert job_run_response.status_code == 200
        assert job_run_response.json()["status"] == "succeeded"
        document_id = job_run_response.json()["document_id"]
        assert document_id

        jobs_response = client.get("/api/v1/ingestion/jobs")
        assert jobs_response.status_code == 200
        assert any(job["id"] == ingestion_job_id for job in jobs_response.json())

        documents_response = client.get("/api/v1/documents")
        assert documents_response.status_code == 200
        assert any(document["id"] == document_id for document in documents_response.json())

        chunks_response = client.get(f"/api/v1/documents/{document_id}/chunks")
        assert chunks_response.status_code == 200
        chunks = chunks_response.json()
        assert chunks
        assert "Academic competence" in chunks[0]["content_text"]

        extract_response = client.post(
            "/api/v1/claims/extract",
            json={"document_id": document_id, "chunk_indexes": [chunks[0]["chunk_index"]]},
        )
        assert extract_response.status_code == 202
        assert extract_response.json()["claims_extracted_count"] == 1

        claims_response = client.get(f"/api/v1/documents/{document_id}/claims")
        assert claims_response.status_code == 200
        claims = claims_response.json()
        assert len(claims) == 1
        assert claims[0]["evidence_items"][0]["document_chunk_id"] == chunks[0]["id"]

        retrieval_response = client.post(
            "/api/v1/retrieval/search",
            json={"query_text": "academic competence coursework inquiry", "limit": 5},
        )
        assert retrieval_response.status_code == 200
        hits = retrieval_response.json()["hits"]
        assert hits
        assert any(hit["document_id"] == document_id for hit in hits)

        admin_chunks_response = client.get(f"/api/v1/admin/documents/{document_id}/chunks", headers=admin)
        assert admin_chunks_response.status_code == 200
        assert len(admin_chunks_response.json()) == len(chunks)
