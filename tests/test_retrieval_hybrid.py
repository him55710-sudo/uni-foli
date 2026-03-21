from __future__ import annotations

from pathlib import Path

from services.admissions.claim_extraction.schemas import ClaimExtractionBatch, ExtractedClaim
from db.models.content import ConflictRecord
from db.session import session_scope
from domain.enums import ClaimStatus, ConflictStatus, ConflictType
from services.admissions.utils import ensure_uuid
from tests.helpers import login_headers, make_client


def _create_source(client, *, name: str = "Example Admissions Office") -> str:
    response = client.post(
        "/api/v1/sources",
        json={
            "name": name,
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
    assert response.status_code == 201
    return response.json()["id"]


def _upload_and_ingest(client, *, source_id: str, filename: str, text: str, source_url: str) -> str:
    upload_response = client.post(
        f"/api/v1/sources/{source_id}/files",
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
        data={"source_url": source_url},
    )
    assert upload_response.status_code == 201
    job_id = upload_response.json()["ingestion_job_id"]
    run_response = client.post(f"/api/v1/ingestion/jobs/{job_id}/run")
    assert run_response.status_code == 200
    return run_response.json()["document_id"]


def test_hybrid_retrieval_prefers_current_official_claim_and_exposes_conflicts(tmp_path: Path, monkeypatch) -> None:
    from services.admissions.claim_extraction import ollama_extractor as extractor_module

    def fake_extract(request) -> ClaimExtractionBatch:
        chunk = request.chunks[0]
        year = 2026 if "2026" in chunk.content_text else 2025
        return ClaimExtractionBatch(
            claims=[
                ExtractedClaim(
                    claim_text=f"{year} academic competence is evaluated through inquiry, coursework, and authentic growth.",
                    normalized_claim_text=f"{year} academic competence is evaluated through inquiry, coursework, and authentic growth.",
                    claim_type="policy_statement",
                    source_tier="tier_1_official",
                    target_evaluation_dimension="academic_competence",
                    applicable_from_year=year,
                    applicable_to_year=year,
                    applicable_cycle_label="susi",
                    confidence_score=0.94 if year == 2026 else 0.82,
                    evidence_quote=chunk.content_text[:140],
                    evidence_page_number=chunk.page_start,
                    evidence_chunk_index=chunk.chunk_index,
                    rationale="Official guidebook statement.",
                    evidence_quality_score=0.92 if year == 2026 else 0.74,
                )
            ]
        )

    monkeypatch.setattr(extractor_module.claim_extractor, "extract", fake_extract)

    with make_client(tmp_path, database_name="retrieval-hybrid.db") as client:
        admin = login_headers(client, email="admin@local.polio")
        source_id = _create_source(client)

        old_document_id = _upload_and_ingest(
            client,
            source_id=source_id,
            filename="2025-guide.txt",
            text=(
                "2025 Admissions Guide\n"
                "Academic competence is evaluated through coursework and inquiry.\n"
                "This older guidebook predates the current cycle."
            ),
            source_url="https://admissions.example.ac.kr/guidebook/2025",
        )
        current_document_id = _upload_and_ingest(
            client,
            source_id=source_id,
            filename="2026-guide.txt",
            text=(
                "2026 Admissions Guide\n"
                "Academic competence is evaluated through inquiry, coursework, and authentic growth.\n"
                "Current official guidance emphasizes sustained evidence."
            ),
            source_url="https://admissions.example.ac.kr/guidebook/2026",
        )

        old_extract = client.post("/api/v1/claims/extract", json={"document_id": old_document_id})
        current_extract = client.post("/api/v1/claims/extract", json={"document_id": current_document_id})
        assert old_extract.status_code == 202
        assert current_extract.status_code == 202

        old_claim_id = client.get(f"/api/v1/documents/{old_document_id}/claims").json()[0]["id"]
        current_claim_id = client.get(f"/api/v1/documents/{current_document_id}/claims").json()[0]["id"]

        review_old = client.patch(
            f"/api/v1/admin/claims/{old_claim_id}/review",
            json={"status": "approved", "evidence_quality_score": 0.74},
            headers=admin,
        )
        review_current = client.patch(
            f"/api/v1/admin/claims/{current_claim_id}/review",
            json={"status": "approved", "evidence_quality_score": 0.92},
            headers=admin,
        )
        assert review_old.status_code == 200
        assert review_current.status_code == 200

        with session_scope() as session:
            session.add(
                ConflictRecord(
                    primary_claim_id=ensure_uuid(old_claim_id),
                    conflicting_claim_id=ensure_uuid(current_claim_id),
                    winning_claim_id=ensure_uuid(current_claim_id),
                    conflict_type=ConflictType.OUTDATED_VS_CURRENT,
                    severity_score=0.9,
                    status=ConflictStatus.OPEN,
                    metadata_json={"note": "2026 guidebook supersedes 2025 guidance"},
                )
            )

        response = client.post(
            "/api/v1/retrieval/search",
            json={
                "query_text": "academic competence inquiry coursework growth",
                "limit": 5,
                "source_tiers": ["tier_1_official"],
                "claim_statuses": ["approved"],
                "include_conflicts": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["diagnostics"]["candidate_count"] >= 2
        assert payload["ranking_policy"]["approved_claim_boost"] > 0

        top_hit = payload["hits"][0]
        assert top_hit["document_id"] == current_document_id
        assert top_hit["metadata"]["claim_status"] == ClaimStatus.APPROVED.value
        assert top_hit["citation"]["citation_kind"] == "claim"
        assert top_hit["citation"]["document_id"] == current_document_id

        assert any(hit["conflicts"] for hit in payload["hits"])
        assert any(hit["conflict_state"] == "open" for hit in payload["hits"])

        current_only = client.post(
            "/api/v1/retrieval/search",
            json={
                "query_text": "academic competence inquiry coursework growth",
                "limit": 5,
                "freshness_states": ["current"],
            },
        )
        assert current_only.status_code == 200
        current_hits = current_only.json()["hits"]
        assert current_hits
        assert all(hit["freshness_state"] == "current" for hit in current_hits)


def test_retrieval_eval_case_round_trip(tmp_path: Path, monkeypatch) -> None:
    from services.admissions.claim_extraction import ollama_extractor as extractor_module

    def fake_extract(request) -> ClaimExtractionBatch:
        chunk = request.chunks[0]
        return ClaimExtractionBatch(
            claims=[
                ExtractedClaim(
                    claim_text="Academic competence is interpreted through inquiry and coursework.",
                    normalized_claim_text="Academic competence is interpreted through inquiry and coursework.",
                    claim_type="policy_statement",
                    source_tier="tier_1_official",
                    target_evaluation_dimension="academic_competence",
                    applicable_from_year=2026,
                    applicable_to_year=2026,
                    applicable_cycle_label="susi",
                    confidence_score=0.95,
                    evidence_quote=chunk.content_text[:120],
                    evidence_page_number=chunk.page_start,
                    evidence_chunk_index=chunk.chunk_index,
                    rationale="Official evaluation description.",
                    evidence_quality_score=0.9,
                )
            ]
        )

    monkeypatch.setattr(extractor_module.claim_extractor, "extract", fake_extract)

    with make_client(tmp_path, database_name="retrieval-eval.db") as client:
        admin = login_headers(client, email="admin@local.polio")
        source_id = _create_source(client, name="Evaluation Guide Source")
        document_id = _upload_and_ingest(
            client,
            source_id=source_id,
            filename="2026-evaluation-guide.txt",
            text=(
                "2026 Evaluation Guide\n"
                "Academic competence is interpreted through inquiry and coursework.\n"
                "Official evaluation wording for the current cycle."
            ),
            source_url="https://admissions.example.ac.kr/guidebook/2026-evaluation",
        )
        extract_response = client.post("/api/v1/claims/extract", json={"document_id": document_id})
        assert extract_response.status_code == 202
        claim_id = client.get(f"/api/v1/documents/{document_id}/claims").json()[0]["id"]
        review_response = client.patch(
            f"/api/v1/admin/claims/{claim_id}/review",
            json={"status": "approved", "evidence_quality_score": 0.9},
            headers=admin,
        )
        assert review_response.status_code == 200

        create_case = client.post(
            "/api/v1/admin/retrieval/eval-cases",
            json={
                "dataset_key": "alpha-retrieval",
                "case_key": "approved-current-cycle",
                "query_text": "academic competence inquiry coursework",
                "filters_json": {"claim_statuses": ["approved"], "limit": 5},
                "expected_results_json": {
                    "document_ids": [document_id],
                    "require_approved_claim_top_hit": True,
                },
                "notes": "Approved official claim should be retrieved with a citation.",
                "metadata_json": {"phase": "alpha"},
            },
            headers=admin,
        )
        assert create_case.status_code == 201
        case_id = create_case.json()["id"]

        run_case = client.post(f"/api/v1/admin/retrieval/eval-cases/{case_id}/run", headers=admin)
        assert run_case.status_code == 200
        result = run_case.json()
        assert result["passed"] is True
        assert document_id in result["observed_document_ids"]
        assert result["observed_citation_keys"]
