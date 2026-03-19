from fastapi.testclient import TestClient

from polio_api.main import app


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_root_page_contains_docs_link() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Open API Docs" in response.text
        assert "/docs" in response.text
