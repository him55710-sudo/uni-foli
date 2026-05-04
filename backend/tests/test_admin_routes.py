from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from unifoli_api.api.deps import LOCAL_DEV_JWT_SECRET
from unifoli_api.core.config import get_settings
from unifoli_api.main import app


def _auth_headers(subject: str, email: str, extra_claims: dict[str, object] | None = None) -> dict[str, str]:
    settings = get_settings()
    if not settings.auth_jwt_secret:
        settings.auth_jwt_secret = LOCAL_DEV_JWT_SECRET

    payload: dict[str, object] = {
        "sub": subject,
        "email": email,
        "name": subject.replace("-", " ").title(),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.auth_jwt_secret, algorithm=settings.auth_jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}


def _with_admin_settings() -> tuple[object, tuple[object, ...]]:
    settings = get_settings()
    original = (
        settings.auth_jwt_secret,
        settings.auth_firebase_fallback_enabled,
        list(settings.admin_emails),
    )
    settings.auth_jwt_secret = LOCAL_DEV_JWT_SECRET
    settings.auth_firebase_fallback_enabled = False
    settings.admin_emails = ["admin@example.com"]
    return settings, original


def _restore_admin_settings(settings: object, original: tuple[object, ...]) -> None:
    (
        settings.auth_jwt_secret,
        settings.auth_firebase_fallback_enabled,
        settings.admin_emails,
    ) = original


def test_admin_stats_rejects_non_admin_user() -> None:
    settings, original = _with_admin_settings()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/admin/stats",
                headers=_auth_headers(f"normal-{uuid4().hex}", "student@example.com"),
            )

        assert response.status_code == 403
        assert "관리자" in response.json()["detail"]
    finally:
        _restore_admin_settings(settings, original)


def test_admin_can_view_project_assets_stats_and_logs() -> None:
    settings, original = _with_admin_settings()
    project_title = f"Admin visibility {uuid4().hex}"
    user_headers = _auth_headers(f"student-{uuid4().hex}", "student@example.com")
    admin_headers = _auth_headers(f"admin-{uuid4().hex}", "admin@example.com")

    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/projects",
                json={
                    "title": project_title,
                    "target_university": "서울대학교",
                    "target_major": "컴퓨터공학부",
                },
                headers=user_headers,
            )
            assert created.status_code == 201
            project_id = created.json()["id"]

            stats = client.get("/api/v1/admin/stats", headers=admin_headers)
            assert stats.status_code == 200
            assert stats.json()["summary"]["total_projects"] >= 1
            assert "diagnosis_status" in stats.json()["breakdowns"]

            projects = client.get("/api/v1/admin/projects", headers=admin_headers)
            assert projects.status_code == 200
            assert any(project["id"] == project_id for project in projects.json())

            assets = client.get(f"/api/v1/admin/projects/{project_id}/assets", headers=admin_headers)
            assert assets.status_code == 200
            assert assets.json()["project"]["id"] == project_id
            assert assets.json()["uploads"] == []

            logs = client.get(f"/api/v1/admin/projects/{project_id}/logs", headers=admin_headers)
            assert logs.status_code == 200
            assert any(event["category"] == "project" for event in logs.json()["logs"])
    finally:
        _restore_admin_settings(settings, original)


def test_admin_claim_can_access_admin_me_without_allowlisted_email() -> None:
    settings, original = _with_admin_settings()
    role_headers = _auth_headers(
        f"claim-admin-{uuid4().hex}",
        "role-admin@example.com",
        {"roles": ["admin"]},
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/admin/me", headers=role_headers)

        assert response.status_code == 200
        assert response.json()["is_admin"] is True
        assert response.json()["email"] == "role-admin@example.com"
    finally:
        _restore_admin_settings(settings, original)
