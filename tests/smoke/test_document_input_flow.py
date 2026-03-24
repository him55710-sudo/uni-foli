from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.pdfgen import canvas

from tests.smoke.helpers import make_client


def _build_school_record_pdf() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 780, "School Record Intake Sample")
    pdf.drawString(72, 760, "Student phone: 010-1234-5678")
    pdf.drawString(72, 740, "Email: student@example.com")
    pdf.drawString(72, 720, "The student completed a robotics research reflection.")
    pdf.drawString(72, 700, "The student compared two prototypes and documented the limits.")
    pdf.save()
    return buffer.getvalue()


def test_document_input_flow(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        upload = client.post(
            "/api/v1/documents/upload",
            data={
                "title": "School Record Intake",
                "target_major": "Computer Science",
            },
            files={
                "file": (
                    "school-record.pdf",
                    _build_school_record_pdf(),
                    "application/pdf",
                )
            },
        )
        assert upload.status_code == 201, upload.text
        uploaded_document = upload.json()
        assert uploaded_document["status"] == "uploaded"
        assert uploaded_document["masking_status"] == "pending"
        document_id = uploaded_document["id"]

        parse = client.post(
            f"/api/v1/documents/{document_id}/parse",
            params={"wait_for_completion": "true"},
        )
        assert parse.status_code == 202, parse.text
        parsed_document = parse.json()
        assert parsed_document["status"] in {"parsed", "partial"}
        assert parsed_document["masking_status"] == "masked"
        assert parsed_document["parse_attempts"] == 1
        assert parsed_document["project_id"]
        assert parsed_document["parse_metadata"]["chunk_count"] >= 1
        assert parsed_document["parse_metadata"]["masking"]["replacement_count"] >= 2
        assert "[PHONE_MASKED]" in parsed_document["content_text"]
        assert "[EMAIL_MASKED]" in parsed_document["content_text"]

        fetched = client.get(f"/api/v1/documents/{document_id}")
        assert fetched.status_code == 200, fetched.text
        fetched_document = fetched.json()
        assert fetched_document["id"] == document_id
        assert fetched_document["status"] in {"parsed", "partial"}
