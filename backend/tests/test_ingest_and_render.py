from __future__ import annotations

from io import BytesIO
import shutil

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from polio_api.main import app
from backend.tests.auth_helpers import auth_headers
from polio_shared.paths import get_export_root, get_upload_root


def _build_sample_pdf_bytes() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 780, "Polio Sample Student Record")
    pdf.drawString(72, 760, "Student: Kim Backend")
    pdf.drawString(72, 740, "Activity: Robotics club captain")
    pdf.drawString(72, 720, "Achievement: Regional hackathon finalist")
    pdf.save()
    return buffer.getvalue()


def test_pdf_ingest_and_selected_render_flow() -> None:
    project_ids: list[str] = []
    headers = auth_headers("render-flow-user")

    try:
        with TestClient(app) as client:
            project_response = client.post(
                "/api/v1/projects",
                json={
                    "title": "Render Flow Test",
                    "description": "End-to-end test for ingest and render flow.",
                    "target_university": "Test University",
                    "target_major": "Computer Science",
                },
                headers=headers,
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]
            project_ids.append(project_id)

            upload_response = client.post(
                f"/api/v1/projects/{project_id}/uploads",
                files={"file": ("student-record.pdf", _build_sample_pdf_bytes(), "application/pdf")},
                headers=headers,
            )
            assert upload_response.status_code == 201
            upload_payload = upload_response.json()
            assert upload_payload["status"] == "parsed"
            assert "stored_path" not in upload_payload

            documents_response = client.get(f"/api/v1/projects/{project_id}/documents", headers=headers)
            assert documents_response.status_code == 200
            documents = documents_response.json()
            assert len(documents) == 1
            document_id = documents[0]["id"]

            document_response = client.get(f"/api/v1/projects/{project_id}/documents/{document_id}", headers=headers)
            assert document_response.status_code == 200
            document_payload = document_response.json()
            assert document_payload["parse_metadata"]["chunk_count"] >= 1
            assert "chunk_evidence_map" not in document_payload["parse_metadata"]
            assert "raw_artifact" not in document_payload["parse_metadata"]

            chunks_response = client.get(f"/api/v1/projects/{project_id}/documents/{document_id}/chunks", headers=headers)
            assert chunks_response.status_code == 200
            assert len(chunks_response.json()) >= 1

            draft_response = client.post(
                f"/api/v1/projects/{project_id}/documents/{document_id}/drafts",
                json={"title": "학생부 기반 초안", "include_excerpt_limit": 2000},
                headers=headers,
            )
            assert draft_response.status_code == 201
            draft_id = draft_response.json()["id"]

            for render_format in ["pdf", "pptx", "hwpx"]:
                job_response = client.post(
                    "/api/v1/render-jobs",
                    json={
                        "project_id": project_id,
                        "draft_id": draft_id,
                        "render_format": render_format,
                        "requested_by": "pytest",
                    },
                    headers=headers,
                )
                assert job_response.status_code == 201
                job_id = job_response.json()["id"]

                process_response = client.post(f"/api/v1/render-jobs/{job_id}/process", headers=headers)
                assert process_response.status_code == 200
                processed = process_response.json()
                assert processed["status"] == "completed"
                assert processed["download_url"] == f"/api/v1/render-jobs/{job_id}/download"
    finally:
        for project_id in project_ids:
            shutil.rmtree(get_export_root() / project_id, ignore_errors=True)
            shutil.rmtree(get_upload_root() / project_id, ignore_errors=True)
