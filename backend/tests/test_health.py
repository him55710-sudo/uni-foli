from fastapi.testclient import TestClient

from polio_api.api.routes import health as health_route
from polio_api.core.config import get_settings
from polio_api.main import app, create_app


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert "llm_provider" in payload


def test_health_check_llm_probe_uses_ttl_cache(monkeypatch) -> None:
    settings = get_settings()
    original_provider = settings.llm_provider
    settings.llm_provider = "ollama"

    call_count = 0

    async def fake_probe(*, profile: str = "fast"):
        nonlocal call_count
        call_count += 1
        return True, None

    monkeypatch.setattr(health_route, "probe_ollama_connectivity", fake_probe)
    health_route._ollama_health_cache["checked_at"] = 0.0
    health_route._ollama_health_cache["ok"] = True
    health_route._ollama_health_cache["reason"] = None

    try:
        with TestClient(app) as client:
            first = client.get("/api/v1/health?check_llm=true")
            second = client.get("/api/v1/health?check_llm=true")
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["ollama_reachable"] is True
        assert second.json()["ollama_reachable"] is True
        assert second.json()["ollama_cached"] is True
        assert call_count == 1
    finally:
        settings.llm_provider = original_provider


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
