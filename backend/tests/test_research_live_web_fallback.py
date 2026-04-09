from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.auth_helpers import auth_headers
from polio_api.core.config import get_settings
from polio_api.main import app
from polio_api.services.scholar_service import ScholarPaper, ScholarSearchResult


def test_live_web_source_falls_back_to_semantic_when_provider_disabled(monkeypatch) -> None:
    settings = get_settings()
    original = (
        settings.live_web_search_enabled,
        settings.live_web_search_provider,
        settings.live_web_search_api_key,
    )
    settings.live_web_search_enabled = False
    settings.live_web_search_provider = "none"
    settings.live_web_search_api_key = None

    async def fake_provider_search(*, query: str, limit: int = 5, source: str | None = None) -> ScholarSearchResult:
        del source
        return ScholarSearchResult(
            query=query,
            total=1,
            papers=[
                ScholarPaper(
                    title="Fallback semantic result",
                    abstract="Indexed fallback path",
                    authors=["Fallback Author"],
                    year=2025,
                    citationCount=3,
                    url="https://example.org/paper",
                )
            ],
            source="semantic",
            requested_source="live_web",
            fallback_applied=True,
            limitation_note="Live web search is disabled in server config. Returned Semantic Scholar fallback results.",
            providers_used=["semantic_scholar"],
            source_type_counts={"academic_source": 1},
        )

    monkeypatch.setattr(
        "polio_api.api.routes.research.search_research_sources",
        fake_provider_search,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/research/papers",
                params={"query": "biology", "source": "live_web"},
                headers=auth_headers("live-web-fallback-user"),
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["requested_source"] == "live_web"
        assert payload["source"] == "semantic"
        assert payload["fallback_applied"] is True
        assert "fallback" in payload["limitation_note"].lower()
        assert payload["source_type_counts"]["academic_source"] == 1
    finally:
        (
            settings.live_web_search_enabled,
            settings.live_web_search_provider,
            settings.live_web_search_api_key,
        ) = original


def test_research_route_supports_both_source(monkeypatch) -> None:
    async def fake_provider_search(*, query: str, limit: int = 5, source: str | None = None) -> ScholarSearchResult:
        assert source == "both"
        return ScholarSearchResult(
            query=query,
            total=1,
            papers=[
                ScholarPaper(
                    title="Merged academic result",
                    abstract="semantic + kci",
                    authors=["Academic Author"],
                    year=2024,
                    citationCount=4,
                    url="https://example.org/merged",
                )
            ],
            source="both",
            requested_source="both",
            fallback_applied=False,
            limitation_note=None,
            providers_used=["semantic_scholar", "kci"],
            source_type_counts={"academic_source": 1},
        )

    monkeypatch.setattr("polio_api.api.routes.research.search_research_sources", fake_provider_search)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/research/papers",
            params={"query": "biology", "source": "both"},
            headers=auth_headers("research-both-user"),
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_source"] == "both"
    assert payload["source"] == "both"
    assert payload["providers_used"] == ["semantic_scholar", "kci"]
