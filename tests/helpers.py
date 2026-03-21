from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from db.models.security import Tenant
from db.session import reset_session_state, session_scope
from domain.enums import LifecycleStatus, PrivacyMaskingMode
from services.admissions.auth_service import auth_service
from services.admissions.utils import slugify


DEFAULT_PASSWORD = "ChangeMe123!"


def make_client(tmp_path: Path, *, database_name: str = "test.db", extra_env: dict[str, str] | None = None) -> TestClient:
    db_path = tmp_path / database_name
    object_store = tmp_path / "object-store"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["LOCAL_OBJECT_STORE_PATH"] = object_store.as_posix()
    os.environ["LANGFUSE_ENABLED"] = "false"
    os.environ["PRESIDIO_ENABLED"] = "false"
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["AUTH_BOOTSTRAP_DEFAULT_ACCOUNTS"] = "true"
    if extra_env:
        for key, value in extra_env.items():
            os.environ[key] = value
    get_settings.cache_clear()
    reset_session_state()
    return TestClient(create_app())


def login_headers(
    client: TestClient,
    *,
    email: str = "member@local.polio",
    password: str = DEFAULT_PASSWORD,
) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_tenant_and_account(
    *,
    slug: str,
    name: str,
    email: str,
    role_slug: str = "member",
    password: str = DEFAULT_PASSWORD,
    masking_mode: PrivacyMaskingMode = PrivacyMaskingMode.MASK_FOR_INDEX,
    retention_days: int = 365,
) -> None:
    with session_scope() as session:
        tenant = Tenant(
            slug=slugify(slug),
            name=name,
            status=LifecycleStatus.ACTIVE,
            default_retention_days=retention_days,
            masking_mode=masking_mode,
            pii_detection_enabled=True,
            metadata_json={},
        )
        session.add(tenant)
        session.flush()
        auth_service.create_account(
            session,
            tenant_id=tenant.id,
            role_slug=role_slug,
            email=email,
            full_name=name,
            password=password,
        )
