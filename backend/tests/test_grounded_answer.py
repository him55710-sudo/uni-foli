from __future__ import annotations

import hashlib
from io import BytesIO

import numpy as np
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from polio_api.core.database import engine
from polio_api.main import app


def _build_sample_pdf_bytes() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 780, "Uni Folia grounded evidence sample")
    pdf.drawString(72, 760, "Activity: Robotics club captain")
    pdf.drawString(72, 740, "Achievement: Regional hackathon finalist")
    pdf.drawString(72, 720, "Reflection: Compared sensor data and recorded method limits")
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
        scores: list[float] = []
        for passage in passages:
            passage_terms = set(passage.lower().split())
            scores.append(float(len(query_terms & passage_terms)))
        return scores


def test_grounded_answer_returns_provenance_with_sqlite_fallback(monkeypatch) -> None:
    fake_embeddings = _FakeEmbeddingService()
    fake_reranker = _FakeRerankerService()
    monkeypatch.setattr(
        "polio_shared.embeddings.get_embedding_service",
        lambda *args, **kwargs: fake_embeddings,
    )
    monkeypatch.setattr(
        "polio_api.services.vector_service.get_embedding_service",
        lambda *args, **kwargs: fake_embeddings,
    )
    monkeypatch.setattr(
        "polio_api.services.vector_service.get_reranker_service",
        lambda *args, **kwargs: fake_reranker,
    )

    with TestClient(app) as client:
        project_response = client.post(
            "/api/v1/projects",
            json={
                "title": "Grounded Answer Test",
                "description": "Ensure provenance-backed answers are returned.",
                "target_major": "Computer Science",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/api/v1/projects/{project_id}/uploads",
            files={"file": ("record.pdf", _build_sample_pdf_bytes(), "application/pdf")},
        )
        assert upload_response.status_code == 201

        answer_response = client.post(
            f"/api/v1/projects/{project_id}/grounded-answer",
            json={"question": "What evidence exists about robotics and hackathon work?"},
        )
        assert answer_response.status_code == 200
        payload = answer_response.json()

        assert engine.dialect.name == "sqlite"
        assert set(payload.keys()) == {
            "answer",
            "insufficient_evidence",
            "missing_information",
            "next_safe_action",
            "provenance",
            "status",
        }
        assert payload["status"] == "answered"
        assert payload["insufficient_evidence"] is False
        assert payload["provenance"]
        assert "robotics" in payload["answer"].lower()
        assert set(payload["provenance"][0].keys()) == {
            "char_end",
            "char_start",
            "chunk_id",
            "document_id",
            "excerpt",
            "lexical_overlap_score",
            "page_number",
            "rerank_score",
            "score",
            "similarity_score",
            "source_label",
        }
        assert payload["provenance"][0]["document_id"]
        assert payload["provenance"][0]["chunk_id"]
        assert payload["provenance"][0]["excerpt"]
        assert payload["provenance"][0]["similarity_score"] is not None


def test_grounded_answer_refuses_when_evidence_is_weak_and_keeps_contract(monkeypatch) -> None:
    fake_embeddings = _FakeEmbeddingService()
    fake_reranker = _FakeRerankerService()
    monkeypatch.setattr(
        "polio_shared.embeddings.get_embedding_service",
        lambda *args, **kwargs: fake_embeddings,
    )
    monkeypatch.setattr(
        "polio_api.services.vector_service.get_embedding_service",
        lambda *args, **kwargs: fake_embeddings,
    )
    monkeypatch.setattr(
        "polio_api.services.vector_service.get_reranker_service",
        lambda *args, **kwargs: fake_reranker,
    )

    with TestClient(app) as client:
        project_response = client.post(
            "/api/v1/projects",
            json={
                "title": "Grounded Answer Refusal Test",
                "description": "Ensure unsupported claims are refused.",
                "target_major": "Computer Science",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/api/v1/projects/{project_id}/uploads",
            files={"file": ("record.pdf", _build_sample_pdf_bytes(), "application/pdf")},
        )
        assert upload_response.status_code == 201

        answer_response = client.post(
            f"/api/v1/projects/{project_id}/grounded-answer",
            json={"question": "What evidence proves violin competition leadership?"},
        )
        assert answer_response.status_code == 200
        payload = answer_response.json()

        assert set(payload.keys()) == {
            "answer",
            "insufficient_evidence",
            "missing_information",
            "next_safe_action",
            "provenance",
            "status",
        }
        assert payload["status"] == "insufficient_evidence"
        assert payload["insufficient_evidence"] is True
        assert payload["next_safe_action"]
        assert payload["missing_information"]
        assert isinstance(payload["provenance"], list)
