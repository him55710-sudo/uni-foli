from __future__ import annotations

from io import BytesIO
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from polio_api.main import app


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
    output_paths: list[Path] = []
    upload_paths: list[Path] = []

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
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            upload_response = client.post(
                f"/api/v1/projects/{project_id}/uploads",
                files={"file": ("student-record.pdf", _build_sample_pdf_bytes(), "application/pdf")},
            )
            assert upload_response.status_code == 201
            upload_payload = upload_response.json()
            assert upload_payload["status"] == "parsed"
            upload_paths.append(Path(upload_payload["stored_path"]))

            documents_response = client.get(f"/api/v1/projects/{project_id}/documents")
            assert documents_response.status_code == 200
            documents = documents_response.json()
            assert len(documents) == 1
            document_id = documents[0]["id"]

            chunks_response = client.get(f"/api/v1/projects/{project_id}/documents/{document_id}/chunks")
            assert chunks_response.status_code == 200
            assert len(chunks_response.json()) >= 1

            draft_response = client.post(
                f"/api/v1/projects/{project_id}/documents/{document_id}/drafts",
                json={"title": "학생부 기반 초안", "include_excerpt_limit": 2000},
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
                )
                assert job_response.status_code == 201
                job_id = job_response.json()["id"]

                process_response = client.post(f"/api/v1/render-jobs/{job_id}/process")
                assert process_response.status_code == 200
                processed = process_response.json()
                assert processed["status"] == "completed"
                assert processed["output_path"]
                output_paths.append(Path(processed["output_path"]))
    finally:
        for output_path in output_paths:
            absolute_output = Path.cwd() / output_path
            if absolute_output.exists():
                absolute_output.unlink()
            parent = absolute_output.parent
            if parent.exists():
                shutil.rmtree(parent, ignore_errors=True)

        for upload_path in upload_paths:
            absolute_upload = Path.cwd() / upload_path
            if absolute_upload.exists():
                absolute_upload.unlink()
