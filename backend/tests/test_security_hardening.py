from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from reportlab.pdfgen import canvas

from backend.tests.auth_helpers import auth_headers
from polio_api.api.routes import projects as projects_route
from polio_api.api.deps import LOCAL_DEV_JWT_SECRET
from polio_api.core.config import Settings, get_settings
from polio_api.core.database import SessionLocal
from polio_api.core.oauth_state import build_client_binding, build_oauth_state, validate_oauth_state
from polio_api.db.models.render_job import RenderJob
from polio_api.db.models.workshop import WorkshopSession
from polio_api.main import app
from polio_ingest import ResearchPipelineError, normalize_research_source
from polio_ingest.models import ResearchSourceInput
from polio_shared.paths import find_project_root, get_export_root, get_runtime_root


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


def test_production_settings_reject_localhost_social_redirects() -> None:
    try:
        Settings(
            app_env="production",
            auth_social_login_enabled=True,
            auth_social_state_secret="state-secret",
            kakao_client_id="real-kakao-client-id",
            kakao_redirect_uri="http://localhost:3001/auth/callback/kakao",
        )
    except ValidationError:
        return
    raise AssertionError("Production settings unexpectedly allowed a localhost social redirect URI.")


def test_settings_default_to_production_without_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("API_DOCS_ENABLED", raising=False)
    settings = Settings(_env_file=None)
    assert settings.app_env == "production"
    assert settings.api_docs_enabled is False


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


def test_expired_token_is_rejected() -> None:
    settings = get_settings()
    original_secret = settings.auth_jwt_secret
    original_firebase_fallback = settings.auth_firebase_fallback_enabled
    settings.auth_jwt_secret = LOCAL_DEV_JWT_SECRET
    settings.auth_firebase_fallback_enabled = False

    token = jwt.encode(
        {
            "sub": f"expired-user-{uuid4().hex}",
            "email": "expired@example.com",
            "name": "Expired User",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
    finally:
        settings.auth_jwt_secret = original_secret
        settings.auth_firebase_fallback_enabled = original_firebase_fallback


def test_oauth_state_rejects_client_binding_mismatch() -> None:
    state = build_oauth_state(
        provider="kakao",
        secret="test-state-secret",
        client_binding=build_client_binding("browser-one", "203.0.113.10"),
    )

    with pytest.raises(ValueError):
        validate_oauth_state(
            state=state,
            provider="kakao",
            secret="test-state-secret",
            ttl_seconds=300,
            client_binding=build_client_binding("browser-two", "203.0.113.10"),
        )


def test_oauth_state_rejects_replay() -> None:
    client_binding = build_client_binding("replay-browser", "203.0.113.20")
    state = build_oauth_state(
        provider="naver",
        secret="test-state-secret",
        client_binding=client_binding,
    )

    validate_oauth_state(
        state=state,
        provider="naver",
        secret="test-state-secret",
        ttl_seconds=300,
        client_binding=client_binding,
    )

    with pytest.raises(ValueError):
        validate_oauth_state(
            state=state,
            provider="naver",
            secret="test-state-secret",
            ttl_seconds=300,
            client_binding=client_binding,
        )


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


def test_upload_and_document_routes_hide_internal_storage_details() -> None:
    headers = auth_headers(f"storage-hide-user-{uuid4().hex}")

    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"title": f"Storage hide {uuid4()}"},
            headers=headers,
        )
        assert project.status_code == 201
        project_id = project.json()["id"]

        upload = client.post(
            f"/api/v1/projects/{project_id}/uploads",
            files={"file": ("record.pdf", _build_sample_pdf_bytes(), "application/pdf")},
            headers=headers,
        )
        assert upload.status_code == 201
        upload_body = upload.json()
        assert "stored_path" not in upload_body
        assert "sha256" not in upload_body

        document_id = upload_body["parsed_document_id"]
        assert document_id
        document = client.get(
            f"/api/v1/projects/{project_id}/documents/{document_id}",
            headers=headers,
        )
        assert document.status_code == 200
        document_body = document.json()
        assert "stored_path" not in document_body
        assert "sha256" not in document_body
        assert "raw_artifact" not in document_body["parse_metadata"]
        assert "masked_artifact" not in document_body["parse_metadata"]
        assert "analysis_artifact" not in document_body["parse_metadata"]
        assert "chunk_evidence_map" not in document_body["parse_metadata"]


def test_logo_route_uses_repo_managed_directory_only() -> None:
    logo_dir = get_runtime_root() / "university-logos"
    logo_dir.mkdir(parents=True, exist_ok=True)
    logo_path = logo_dir / "seoul-national-university.png"
    logo_path.write_bytes(b"fake-logo")

    try:
        with TestClient(app) as client:
            ok = client.get("/api/v1/assets/univ-logo", params={"name": "Seoul National University"})
            assert ok.status_code == 200

            blocked = client.get("/api/v1/assets/univ-logo", params={"name": "../secret"})
            assert blocked.status_code == 400
    finally:
        if logo_path.exists():
            logo_path.unlink()


def test_research_paper_search_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/research/papers", params={"query": "biology"})
    assert response.status_code == 401


def test_kci_search_requires_configured_api_key() -> None:
    headers = auth_headers(f"kci-user-{uuid4().hex}")
    settings = get_settings()
    original_kci_api_key = settings.kci_api_key
    settings.kci_api_key = None

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/research/papers",
                params={"query": "biology", "source": "kci"},
                headers=headers,
            )
        assert response.status_code == 503
        assert response.json()["detail"] == "KCI search is not configured for this environment."
    finally:
        settings.kci_api_key = original_kci_api_key


def test_research_ingestion_rejects_private_network_urls() -> None:
    with pytest.raises(ResearchPipelineError):
        normalize_research_source(
            ResearchSourceInput(
                source_type="web_article",
                source_classification="OFFICIAL_SOURCE",
                canonical_url="http://127.0.0.1/private",
            )
        )


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


def test_render_job_route_hides_output_path_and_serves_owner_scoped_download() -> None:
    headers = auth_headers(f"render-download-{uuid4().hex}")
    export_file = None

    try:
        with TestClient(app) as client:
            project = client.post(
                "/api/v1/projects",
                json={"title": f"Render download {uuid4()}", "target_major": "Computer Science"},
                headers=headers,
            )
            assert project.status_code == 201
            project_id = project.json()["id"]

            upload = client.post(
                f"/api/v1/projects/{project_id}/uploads",
                files={"file": ("record.pdf", _build_sample_pdf_bytes(), "application/pdf")},
                headers=headers,
            )
            assert upload.status_code == 201
            document_id = upload.json()["parsed_document_id"]

            draft = client.post(
                f"/api/v1/projects/{project_id}/documents/{document_id}/drafts",
                json={"title": "Download draft", "include_excerpt_limit": 1000},
                headers=headers,
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
                headers=headers,
            )
            assert render_job.status_code == 201
            job_id = render_job.json()["id"]

            export_dir = get_export_root() / project_id / job_id
            export_dir.mkdir(parents=True, exist_ok=True)
            export_file = export_dir / "report.pdf"
            export_file.write_bytes(b"fake-pdf-bytes")
            relative_export_path = str(export_file.relative_to(find_project_root()))

            with SessionLocal() as db:
                job = db.get(RenderJob, job_id)
                assert job is not None
                job.output_path = relative_export_path
                db.add(job)
                db.commit()

            job_response = client.get(f"/api/v1/render-jobs/{job_id}", headers=headers)
            assert job_response.status_code == 200
            job_body = job_response.json()
            assert "output_path" not in job_body
            assert job_body["download_url"] == f"/api/v1/render-jobs/{job_id}/download"

            download = client.get(f"/api/v1/render-jobs/{job_id}/download", headers=headers)
            assert download.status_code == 200

            with SessionLocal() as db:
                job = db.get(RenderJob, job_id)
                assert job is not None
                job.output_path = "../../secrets/report.pdf"
                db.add(job)
                db.commit()

            blocked = client.get(f"/api/v1/render-jobs/{job_id}/download", headers=headers)
            assert blocked.status_code == 404
    finally:
        if export_file is not None and export_file.exists():
            export_file.unlink()
            export_file.parent.rmdir()


def test_social_login_prepare_and_invalid_state_handling() -> None:
    settings = get_settings()
    original_enabled = settings.auth_social_login_enabled
    original_secret = settings.auth_social_state_secret
    original_ttl = settings.auth_social_state_ttl_seconds
    original_kakao_client_id = settings.kakao_client_id
    original_google_client_id = settings.google_client_id
    settings.auth_social_login_enabled = True
    settings.auth_social_state_secret = "test-social-state-secret"
    settings.auth_social_state_ttl_seconds = 300
    settings.kakao_client_id = "test-kakao-client-id"
    settings.google_client_id = "test-google-client-id"

    try:
        with TestClient(app) as client:
            prepare = client.post("/api/v1/auth/social/prepare", json={"provider": "kakao"})
            assert prepare.status_code == 200
            issued_state = prepare.json()["state"]
            assert issued_state

            google_prepare = client.post("/api/v1/auth/social/prepare", json={"provider": "google"})
            assert google_prepare.status_code == 200
            assert "accounts.google.com" in google_prepare.json()["authorize_url"]

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
        settings.google_client_id = original_google_client_id


def test_expired_workshop_stream_token_is_rejected() -> None:
    headers = auth_headers(f"workshop-stream-{uuid4().hex}")

    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"title": f"Workshop stream {uuid4()}", "target_major": "Education"},
            headers=headers,
        )
        assert project.status_code == 201
        project_id = project.json()["id"]

        workshop = client.post(
            "/api/v1/workshops",
            json={"project_id": project_id, "quality_level": "mid"},
            headers=headers,
        )
        assert workshop.status_code == 201
        workshop_id = workshop.json()["session"]["id"]

        token_response = client.post(f"/api/v1/workshops/{workshop_id}/stream-token", headers=headers)
        assert token_response.status_code == 200
        stream_token = token_response.json()["stream_token"]

        with SessionLocal() as db:
            session = db.get(WorkshopSession, workshop_id)
            assert session is not None
            session.stream_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
            db.add(session)
            db.commit()

        response = client.get(
            f"/api/v1/workshops/{workshop_id}/events",
            params={"stream_token": stream_token, "artifact_id": "missing-artifact"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired stream token."

        with SessionLocal() as db:
            session = db.get(WorkshopSession, workshop_id)
            assert session is not None
            assert session.stream_token is None
            assert session.stream_token_expires_at is None


def test_export_route_hides_internal_render_errors() -> None:
    headers = auth_headers(f"export-user-{uuid4().hex}")

    class FailingRenderer:
        def render(self, context):  # noqa: ANN001
            raise RuntimeError(r"C:\secret\render\failure.log")

    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"title": f"Export test {uuid4()}"},
            headers=headers,
        )
        assert project.status_code == 201
        project_id = project.json()["id"]

        original_renderer = projects_route.HwpxRenderer
        projects_route.HwpxRenderer = FailingRenderer
        try:
            response = client.post(
                f"/api/v1/projects/{project_id}/export",
                json={"content_markdown": "# Draft"},
                headers=headers,
            )
        finally:
            projects_route.HwpxRenderer = original_renderer

    assert response.status_code == 500
    assert response.json()["detail"] == "Export failed. Review the draft content and retry."


def test_export_route_rejects_oversized_payload() -> None:
    headers = auth_headers(f"export-size-{uuid4().hex}")

    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"title": f"Export size {uuid4()}"},
            headers=headers,
        )
        assert project.status_code == 201
        project_id = project.json()["id"]

        response = client.post(
            f"/api/v1/projects/{project_id}/export",
            json={"content_markdown": "a" * 100001},
            headers=headers,
        )

    assert response.status_code == 422
