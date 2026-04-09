from __future__ import annotations

import asyncio

from polio_api.services.live_web_search_service import LiveWebSearchUnavailable
from polio_api.services.scholar_service import ScholarPaper, ScholarSearchResult
from polio_api.services.search_provider_service import search_research_sources


def test_search_provider_both_merges_and_annotates(monkeypatch) -> None:
    async def fake_semantic(query: str, limit: int = 5) -> ScholarSearchResult:
        del query, limit
        return ScholarSearchResult(
            query="admissions",
            total=2,
            papers=[
                ScholarPaper(title="Shared Title", authors=["A"], year=2025, citationCount=3, url="https://paper-a.org"),
                ScholarPaper(title="Semantic Unique", authors=["B"], year=2024, citationCount=1, url="https://paper-b.org"),
            ],
            source="semantic",
            requested_source="semantic",
        )

    async def fake_kci(query: str, limit: int = 5) -> ScholarSearchResult:
        del query, limit
        return ScholarSearchResult(
            query="admissions",
            total=2,
            papers=[
                ScholarPaper(title="Shared Title", authors=["C"], year=2022, citationCount=0, url="https://paper-c.org"),
                ScholarPaper(title="KCI Unique", authors=["D"], year=2023, citationCount=0, url="https://paper-d.org"),
            ],
            source="kci",
            requested_source="kci",
        )

    monkeypatch.setattr("polio_api.services.search_provider_service.search_semantic_scholar_papers", fake_semantic)
    monkeypatch.setattr("polio_api.services.search_provider_service.search_kci_papers", fake_kci)

    result = asyncio.run(search_research_sources(query="admissions", source="both", limit=5))

    assert result.requested_source == "both"
    assert result.source == "both"
    assert result.fallback_applied is False
    assert result.providers_used == ["semantic_scholar", "kci"]
    assert len(result.papers) == 3
    assert all(paper.source_type == "academic_source" for paper in result.papers)
    assert result.source_type_counts.get("academic_source") == 3


def test_search_provider_live_web_fallback_to_semantic(monkeypatch) -> None:
    async def fake_live_web(query: str, limit: int = 5) -> ScholarSearchResult:
        del query, limit
        raise LiveWebSearchUnavailable("Live web provider is not configured.")

    async def fake_semantic(query: str, limit: int = 5) -> ScholarSearchResult:
        del query, limit
        return ScholarSearchResult(
            query="biology",
            total=1,
            papers=[
                ScholarPaper(
                    title="Semantic fallback paper",
                    authors=["Fallback Author"],
                    year=2025,
                    citationCount=0,
                    url="https://example.org/semantic-fallback",
                )
            ],
            source="semantic",
            requested_source="semantic",
        )

    monkeypatch.setattr("polio_api.services.search_provider_service.search_live_web_papers", fake_live_web)
    monkeypatch.setattr("polio_api.services.search_provider_service.search_semantic_scholar_papers", fake_semantic)

    result = asyncio.run(search_research_sources(query="biology", source="live_web", limit=5))

    assert result.requested_source == "live_web"
    assert result.source == "semantic"
    assert result.fallback_applied is True
    assert result.providers_used == ["semantic_scholar"]
    assert result.limitation_note is not None
    assert "fallback" in result.limitation_note.lower()
    assert result.papers[0].source_type == "academic_source"


def test_search_provider_live_web_marks_official_guideline(monkeypatch) -> None:
    async def fake_live_web(query: str, limit: int = 5) -> ScholarSearchResult:
        del query, limit
        return ScholarSearchResult(
            query="학생부 가이드",
            total=1,
            papers=[
                ScholarPaper(
                    title="고교 학생부 기재 요령",
                    abstract="교육부 공식 안내",
                    authors=["교육부"],
                    year=2026,
                    citationCount=0,
                    url="https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294",
                )
            ],
            source="live_web",
            requested_source="live_web",
            providers_used=["live_web:serpapi"],
        )

    monkeypatch.setattr("polio_api.services.search_provider_service.search_live_web_papers", fake_live_web)

    result = asyncio.run(search_research_sources(query="학생부 가이드", source="live_web", limit=5))

    assert result.source == "live_web"
    assert result.fallback_applied is False
    assert result.providers_used == ["live_web:serpapi"]
    assert result.source_type_counts.get("official_guideline") == 1
    assert result.papers[0].source_type == "official_guideline"
    assert result.papers[0].source_label == "Official Guideline"
