from fastapi.testclient import TestClient

from polio_api.core.config import get_settings
from polio_api.main import app, create_app


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_root_page_hides_docs_when_disabled_in_production() -> None:
    settings = get_settings()
    original = (settings.app_env, settings.api_docs_enabled)
    settings.app_env = "production"
    settings.api_docs_enabled = False

    try:
        with TestClient(create_app()) as client:
            response = client.get("/")
            assert response.status_code == 200
            assert "API Docs Hidden" in response.text
            assert client.get("/docs").status_code == 404
    finally:
        settings.app_env, settings.api_docs_enabled = original
