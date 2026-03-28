from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import func, select

from polio_api.core.config import get_settings
from polio_api.core.database import SessionLocal
from polio_api.db.models.document_chunk import DocumentChunk
from polio_api.db.models.research_chunk import ResearchChunk
from polio_api.db.models.research_document import ResearchDocument
from polio_api.main import app
from polio_api.services.diagnosis_service import DiagnosisResult, evaluate_student_record
from polio_api.services.rag_service import RAGConfig, build_rag_context
from polio_api.services.research_service import search_relevant_research_chunks
from backend.tests.auth_helpers import auth_headers


def _build_sample_pdf_bytes() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 780, "Uni Folia research separation sample")
    pdf.drawString(72, 760, "Student evidence: built a robotics sensor notebook")
    pdf.drawString(72, 740, "Student evidence: compared sensor drift during club experiments")
    pdf.save()
    return buffer.getvalue()


class _FakeEmbeddingService:
    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def metadata(self):
        class _Meta:
            model_name = "test-hashing-1536"

        return _Meta()

    def encode(self, texts):
        items = [texts] if isinstance(texts, str) else list(texts)
        vectors = np.zeros((len(items), self.dimensions), dtype=np.float32)
        for row_index, text in enumerate(items):
            for token in str(text).lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                column = int.from_bytes(digest[:4], byteorder="big") % self.dimensions
                vectors[row_index, column] += 1.0
            norm = np.linalg.norm(vectors[row_index])
            if norm > 0:
                vectors[row_index] /= norm
        return vectors

    def generate_embeddings(self, texts):
        return self.encode(list(texts)).tolist()


class _FakeRerankerService:
    def rerank(self, query: str, passages: list[str]) -> list[float]:
        query_terms = set(query.lower().split())
        return [float(len(query_terms & set(passage.lower().split()))) for passage in passages]


class _FakeDiagnosisLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_json(self, **kwargs) -> DiagnosisResult:
        del kwargs
        self.calls += 1
        return DiagnosisResult(
            headline="Grounded diagnosis",
            strengths=["Has measurable work."],
            gaps=["Needs one clearer limitation."],
            risk_level="warning",
            recommended_focus="Add one explicit method limit.",
        )


def test_research_ingest_stays_separate_and_rag_preserves_provenance(monkeypatch) -> None:
    fake_embeddings = _FakeEmbeddingService()
    fake_reranker = _FakeRerankerService()
    headers = auth_headers(f"research-user-{uuid4().hex}")
    settings = get_settings()
    previous_inline = settings.async_jobs_inline_dispatch
    settings.async_jobs_inline_dispatch = False

    monkeypatch.setattr("polio_shared.embeddings.get_embedding_service", lambda *args, **kwargs: fake_embeddings)
    monkeypatch.setattr("polio_api.services.vector_service.get_embedding_service", lambda *args, **kwargs: fake_embeddings)
    monkeypatch.setattr("polio_api.services.vector_service.get_reranker_service", lambda *args, **kwargs: fake_reranker)
    monkeypatch.setattr("polio_api.services.research_service.get_embedding_service", lambda *args, **kwargs: fake_embeddings)
    monkeypatch.setattr("polio_api.services.research_service.get_reranker_service", lambda *args, **kwargs: fake_reranker)

    try:
        with TestClient(app) as client:
            project_response = client.post(
                "/api/v1/projects",
                json={"title": f"Research RAG {uuid4()}", "target_major": "Computer Science"},
                headers=headers,
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            upload_response = client.post(
                f"/api/v1/projects/{project_id}/uploads",
                files={"file": ("student-record.pdf", _build_sample_pdf_bytes(), "application/pdf")},
                headers=headers,
            )
            assert upload_response.status_code == 201

            ingest_response = client.post(
                "/api/v1/research/sources/ingest",
                json={
                    "project_id": project_id,
                    "items": [
                        {
                            "source_type": "paper",
                            "source_classification": "OFFICIAL_SOURCE",
                            "title": "Sensor calibration study",
                            "publisher": "Journal of Robotics",
                            "abstract": "Sensor calibration reduces drift in robotics measurements.",
                            "extracted_text": "Researchers compared calibration routines and sensor drift over time.",
                            "metadata": {"topic": "robotics"},
                        }
                    ],
                },
                headers=headers,
            )
            assert ingest_response.status_code == 200
            payload = ingest_response.json()
            job_id = payload["jobs"][0]["id"]
            research_document_id = payload["documents"][0]["id"]

            process_response = client.post(f"/api/v1/jobs/{job_id}/process", headers=headers)
            assert process_response.status_code == 200
            assert process_response.json()["status"] == "succeeded"

            documents_response = client.get(f"/api/v1/projects/{project_id}/documents", headers=headers)
            assert documents_response.status_code == 200
            assert len(documents_response.json()) == 1

            research_response = client.get(f"/api/v1/research/sources?project_id={project_id}", headers=headers)
            assert research_response.status_code == 200
            assert len(research_response.json()) == 1
            assert research_response.json()[0]["provenance_type"] == "EXTERNAL_RESEARCH"
            assert research_response.json()[0]["source_classification"] == "OFFICIAL_SOURCE"
            assert research_response.json()[0]["trust_rank"] == 400

            answer_response = client.post(
                f"/api/v1/projects/{project_id}/grounded-answer",
                json={"question": "What student evidence exists about sensor drift?"},
                headers=headers,
            )
            assert answer_response.status_code == 200
            assert all(item["provenance_type"] == "STUDENT_RECORD" for item in answer_response.json()["provenance"])

        with SessionLocal() as db:
            student_chunk_count = db.scalar(
                select(func.count()).select_from(DocumentChunk).where(DocumentChunk.project_id == project_id)
            )
            research_chunk_count = db.scalar(
                select(func.count()).select_from(ResearchChunk).where(ResearchChunk.project_id == project_id)
            )
            assert student_chunk_count
            assert research_chunk_count

            rag_context = asyncio.run(
                build_rag_context(
                    db,
                    project_id=project_id,
                    query_keywords=["sensor", "drift", "robotics"],
                    pinned_references=[SimpleNamespace(text_content="Student measured sensor drift.", source_type="note")],
                    config=RAGConfig(enabled=True, source="internal", pin_required=False),
                )
            )
            assert rag_context.internal_chunks
            assert rag_context.research_chunks
            assert "STUDENT_RECORD" in rag_context.injection_text
            assert "EXTERNAL_RESEARCH" in rag_context.injection_text
            assert "OFFICIAL_SOURCE" in rag_context.injection_text

            research_document = db.get(ResearchDocument, research_document_id)
            assert research_document is not None
            assert research_document.status == "indexed"
            assert research_document.source_classification == "OFFICIAL_SOURCE"
            assert research_document.trust_rank == 400
    finally:
        settings.async_jobs_inline_dispatch = previous_inline


def test_research_retrieval_prioritizes_official_sources(monkeypatch) -> None:
    fake_embeddings = _FakeEmbeddingService()
    fake_reranker = _FakeRerankerService()
    headers = auth_headers(f"official-rank-user-{uuid4().hex}")
    settings = get_settings()
    previous_inline = settings.async_jobs_inline_dispatch
    settings.async_jobs_inline_dispatch = False

    monkeypatch.setattr("polio_shared.embeddings.get_embedding_service", lambda *args, **kwargs: fake_embeddings)
    monkeypatch.setattr("polio_api.services.vector_service.get_embedding_service", lambda *args, **kwargs: fake_embeddings)
    monkeypatch.setattr("polio_api.services.vector_service.get_reranker_service", lambda *args, **kwargs: fake_reranker)
    monkeypatch.setattr("polio_api.services.research_service.get_embedding_service", lambda *args, **kwargs: fake_embeddings)
    monkeypatch.setattr("polio_api.services.research_service.get_reranker_service", lambda *args, **kwargs: fake_reranker)

    try:
        with TestClient(app) as client:
            project_response = client.post(
                "/api/v1/projects",
                json={"title": f"Trust ranking {uuid4()}", "target_major": "Architecture"},
                headers=headers,
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            ingest_response = client.post(
                "/api/v1/research/sources/ingest",
                json={
                    "project_id": project_id,
                    "items": [
                        {
                            "source_type": "pdf_document",
                            "source_classification": "OFFICIAL_SOURCE",
                            "title": "Official admissions guide",
                            "publisher": "Example University",
                            "extracted_text": "Official architecture admissions guide covering portfolio review and studio readiness.",
                        },
                        {
                            "source_type": "web_article",
                            "source_classification": "EXPERT_COMMENTARY",
                            "title": "Architect reviews portfolio tips",
                            "text": "Architecture experts discuss portfolio review and studio readiness in general terms.",
                        },
                    ],
                },
                headers=headers,
            )
            assert ingest_response.status_code == 200

            for job in ingest_response.json()["jobs"]:
                process_response = client.post(f"/api/v1/jobs/{job['id']}/process", headers=headers)
                assert process_response.status_code == 200
                assert process_response.json()["status"] == "succeeded"

        with SessionLocal() as db:
            matches = search_relevant_research_chunks(
                db,
                project_id,
                "architecture portfolio review studio readiness",
                limit=2,
            )
            assert len(matches) == 2
            assert matches[0].source_classification == "OFFICIAL_SOURCE"
            assert matches[0].trust_rank > matches[1].trust_rank
            assert matches[0].chunk.document.title == "Official admissions guide"
    finally:
        settings.async_jobs_inline_dispatch = previous_inline


def test_diagnosis_cache_hits_and_misses(monkeypatch) -> None:
    fake_llm = _FakeDiagnosisLLM()
    unique_scope = f"project:{uuid4()}"

    monkeypatch.setattr("polio_api.services.diagnosis_service.get_llm_client", lambda: fake_llm)

    first = asyncio.run(
        evaluate_student_record(
            user_major="Computer Science",
            masked_text="Measured robotics data and reflected on limits.",
            target_major="Computer Science",
            scope_key=unique_scope,
            evidence_keys=["doc:1"],
        )
    )
    second = asyncio.run(
        evaluate_student_record(
            user_major="Computer Science",
            masked_text="Measured robotics data and reflected on limits.",
            target_major="Computer Science",
            scope_key=unique_scope,
            evidence_keys=["doc:1"],
        )
    )
    third = asyncio.run(
        evaluate_student_record(
            user_major="Computer Science",
            masked_text="Measured robotics data and reflected on limits.",
            target_major="Computer Science",
            scope_key=unique_scope,
            evidence_keys=["doc:2"],
        )
    )

    assert first.headline == second.headline == third.headline
    assert fake_llm.calls == 2


def test_job_failure_retry_and_dead_letter_are_visible_via_api() -> None:
    headers = auth_headers(f"jobs-user-{uuid4().hex}")
    settings = get_settings()
    previous_inline = settings.async_jobs_inline_dispatch
    settings.async_jobs_inline_dispatch = False

    try:
        with TestClient(app) as client:
            project_response = client.post(
                "/api/v1/projects",
                json={"title": f"Jobs {uuid4()}", "target_major": "Computer Science"},
                headers=headers,
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            ingest_response = client.post(
                "/api/v1/research/sources/ingest",
                json={
                    "project_id": project_id,
                    "items": [{"source_type": "youtube_transcript", "title": "Broken transcript"}],
                },
                headers=headers,
            )
            assert ingest_response.status_code == 200
            job_id = ingest_response.json()["jobs"][0]["id"]

            status_response = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
            assert status_response.status_code == 200
            assert status_response.json()["status"] == "queued"

            first_process = client.post(f"/api/v1/jobs/{job_id}/process", headers=headers)
            assert first_process.status_code == 200
            assert first_process.json()["status"] == "retrying"
            assert first_process.json()["retry_count"] == 1
            assert "requires transcript text" in (first_process.json()["failure_reason"] or "")

            second_queue = client.post(f"/api/v1/jobs/{job_id}/retry", headers=headers)
            assert second_queue.status_code == 200
            second_process = client.post(f"/api/v1/jobs/{job_id}/process", headers=headers)
            assert second_process.status_code == 200
            assert second_process.json()["status"] == "retrying"
            assert second_process.json()["retry_count"] == 2

            third_queue = client.post(f"/api/v1/jobs/{job_id}/retry", headers=headers)
            assert third_queue.status_code == 200
            third_process = client.post(f"/api/v1/jobs/{job_id}/process", headers=headers)
            assert third_process.status_code == 200
            assert third_process.json()["status"] == "failed"
            assert third_process.json()["dead_lettered_at"] is not None

            research_sources = client.get(f"/api/v1/research/sources?project_id={project_id}", headers=headers)
            assert research_sources.status_code == 200
            assert research_sources.json()[0]["status"] == "failed"
            assert research_sources.json()[0]["last_error"]
    finally:
        settings.async_jobs_inline_dispatch = previous_inline
