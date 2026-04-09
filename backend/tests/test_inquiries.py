from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from polio_api.core.database import SessionLocal
from polio_api.db.models.inquiry import Inquiry
from polio_api.main import app


def test_public_inquiry_submission_persists_record() -> None:
    payload = {
        "inquiry_type": "partnership",
        "institution_name": "예시고등학교",
        "name": "김담당",
        "phone": "010-1234-5678",
        "email": "school@example.com",
        "institution_type": "school",
        "message": "도입 방식과 운영 범위를 문의합니다.",
        "source_path": "/contact?type=partnership",
        "metadata": {"entry_point": "contact_hub", "tab": "partnership"},
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/inquiries", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["inquiry_type"] == "partnership"
    assert body["status"] in {"delivery_queued", "delivery_skipped", "delivery_sent", "delivery_failed"}
    assert body["delivery_status"] in {"queued", "sending", "sent", "failed", "retrying", "skipped"}
    assert isinstance(body.get("delivery_retry_needed"), bool)
    assert body["message"]

    with SessionLocal() as db:
        inquiry = db.scalar(select(Inquiry).where(Inquiry.id == body["id"]))
        assert inquiry is not None
        assert inquiry.institution_name == "예시고등학교"
        assert inquiry.email == "school@example.com"
        assert inquiry.inquiry_category == "partnership_request"
        assert inquiry.extra_fields["metadata"]["entry_point"] == "contact_hub"
        assert inquiry.extra_fields["triage"]["prompt_asset"]["name"] == "inquiry-support.contact-triage"
        assert inquiry.extra_fields["triage"]["category"] == "partnership_request"
        assert inquiry.extra_fields["triage"]["priority"] == "medium"
        assert inquiry.extra_fields["triage"]["follow_up_questions"]
        assert inquiry.extra_fields["delivery"]["status"] in {"queued", "sending", "sent", "failed", "skipped"}
        assert inquiry.extra_fields["delivery"].get("async_job_id")
        assert "history" in inquiry.extra_fields["delivery"]


def test_inquiry_validation_rejects_missing_fields() -> None:
    payload = {
        "inquiry_type": "bug_report",
        "name": "테스터",
        "email": "tester@example.com",
        "message": "로그인이 되지 않습니다.",
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/inquiries", json=payload)

    assert response.status_code == 422
