from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
from reportlab.pdfgen import canvas

from backend.tests.auth_helpers import auth_headers
from polio_api.api.deps import LOCAL_DEV_JWT_SECRET
from polio_api.core.config import Settings, get_settings
from polio_api.main import app


def _build_sample_pdf_bytes() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 780, "Security hardening sample")
    pdf.drawString(72, 760, "Student measured robotics sensor drift.")
    pdf.save()
    return buffer.getvalue()


def test_production_settings_reject_local_dev_bypass() -> None:
    try:
        Settings(
            app_env="production",
            auth_allow_local_dev_bypass=True,
            auth_social_state_secret="state-secret",
        )
    except ValidationError:
        return
    raise AssertionError("Production settings unexpectedly allowed the local dev auth bypass.")


def test_production_settings_reject_wildcard_cors_with_credentials() -> None:
    try:
        Settings(
            app_env="production",
            cors_origins=["*"],
            cors_allow_credentials=True,
            auth_social_state_secret="state-secret",
        )
    except ValidationError:
        return
    raise AssertionError("Production settings unexpectedly allowed wildcard credentialed CORS.")


def test_invalid_token_does_not_fall_back_to_local_dev_user() -> None:
    settings = get_settings()
    original = (
        settings.app_env,
        settings.auth_allow_local_dev_bypass,
        settings.auth_jwt_secret,
        settings.auth_firebase_fallback_enabled,
    )

    settings.app_env = "local"
    settings.auth_allow_local_dev_bypass = True
    settings.auth_jwt_secret = LOCAL_DEV_JWT_SECRET
    settings.auth_firebase_fallback_enabled = False

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer not-a-valid-token"},
            )
        assert response.status_code == 401
    finally:
        (
            settings.app_env,
            settings.auth_allow_local_dev_bypass,
            settings.auth_jwt_secret,
            settings.auth_firebase_fallback_enabled,
        ) = original


def test_upload_rejects_invalid_file_type() -> None:
    headers = auth_headers(f"upload-type-user-{uuid4().hex}")

    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"title": f"Upload type {uuid4()}"},
            headers=headers,
        )
        assert project.status_code == 201
        project_id = project.json()["id"]

        response = client.post(
            f"/api/v1/projects/{project_id}/uploads",
            files={"file": ("diagram.png", b"\x89PNG\r\n\x1a\n", "image/png")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Unsupported upload type" in response.json()["detail"]


def test_upload_rejects_oversized_file() -> None:
    headers = auth_headers(f"upload-size-user-{uuid4().hex}")
    settings = get_settings()
    original_max_bytes = settings.upload_max_bytes
    settings.upload_max_bytes = 128

    try:
        with TestClient(app) as client:
            project = client.post(
                "/api/v1/projects",
                json={"title": f"Upload size {uuid4()}"},
                headers=headers,
            )
            assert project.status_code == 201
            project_id = project.json()["id"]

            response = client.post(
                f"/api/v1/projects/{project_id}/uploads",
                files={"file": ("student-record.txt", ("a" * 1024).encode("utf-8"), "text/plain")},
                headers=headers,
            )
            assert response.status_code == 413
    finally:
        settings.upload_max_bytes = original_max_bytes


def test_workshop_routes_are_owner_scoped() -> None:
    owner_headers = auth_headers(f"workshop-owner-{uuid4().hex}")
    other_headers = auth_headers(f"workshop-other-{uuid4().hex}")

    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"title": f"Workshop scope {uuid4()}", "target_major": "Education"},
            headers=owner_headers,
        )
        assert project.status_code == 201
        project_id = project.json()["id"]

        workshop = client.post(
            "/api/v1/workshops",
            json={"project_id": project_id, "quality_level": "mid"},
            headers=owner_headers,
        )
        assert workshop.status_code == 201
        workshop_id = workshop.json()["session"]["id"]

        assert client.get(f"/api/v1/workshops/{workshop_id}", headers=other_headers).status_code == 404
        assert client.post(f"/api/v1/workshops/{workshop_id}/stream-token", headers=other_headers).status_code == 404


def test_render_jobs_are_owner_scoped() -> None:
    owner_headers = auth_headers(f"render-owner-{uuid4().hex}")
    other_headers = auth_headers(f"render-other-{uuid4().hex}")

    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"title": f"Render scope {uuid4()}", "target_major": "Computer Science"},
            headers=owner_headers,
        )
        assert project.status_code == 201
        project_id = project.json()["id"]

        upload = client.post(
            f"/api/v1/projects/{project_id}/uploads",
            files={"file": ("record.pdf", _build_sample_pdf_bytes(), "application/pdf")},
            headers=owner_headers,
        )
        assert upload.status_code == 201

        documents = client.get(f"/api/v1/projects/{project_id}/documents", headers=owner_headers)
        assert documents.status_code == 200
        document_id = documents.json()[0]["id"]

        draft = client.post(
            f"/api/v1/projects/{project_id}/documents/{document_id}/drafts",
            json={"title": "Scoped draft", "include_excerpt_limit": 1000},
            headers=owner_headers,
        )
        assert draft.status_code == 201
        draft_id = draft.json()["id"]

        render_job = client.post(
            "/api/v1/render-jobs",
            json={
                "project_id": project_id,
                "draft_id": draft_id,
                "render_format": "pdf",
                "requested_by": "security-test",
            },
            headers=owner_headers,
        )
        assert render_job.status_code == 201
        job_id = render_job.json()["id"]

        assert client.get(f"/api/v1/render-jobs/{job_id}", headers=other_headers).status_code == 404
        assert client.post(f"/api/v1/render-jobs/{job_id}/process", headers=other_headers).status_code == 404


def test_social_login_prepare_and_invalid_state_handling() -> None:
    settings = get_settings()
    original_enabled = settings.auth_social_login_enabled
    original_secret = settings.auth_social_state_secret
    original_ttl = settings.auth_social_state_ttl_seconds
    original_kakao_client_id = settings.kakao_client_id
    settings.auth_social_login_enabled = True
    settings.auth_social_state_secret = "test-social-state-secret"
    settings.auth_social_state_ttl_seconds = 300
    settings.kakao_client_id = "test-kakao-client-id"

    try:
        with TestClient(app) as client:
            prepare = client.post("/api/v1/auth/social/prepare", json={"provider": "kakao"})
            assert prepare.status_code == 200
            issued_state = prepare.json()["state"]
            assert issued_state

            invalid = client.post(
                "/api/v1/auth/social",
                json={"provider": "kakao", "code": "fake-code", "state": f"{issued_state}tampered"},
            )
            assert invalid.status_code == 400
            assert invalid.json()["detail"] == "Invalid OAuth state."
    finally:
        settings.auth_social_login_enabled = original_enabled
        settings.auth_social_state_secret = original_secret
        settings.auth_social_state_ttl_seconds = original_ttl
        settings.kakao_client_id = original_kakao_client_id
