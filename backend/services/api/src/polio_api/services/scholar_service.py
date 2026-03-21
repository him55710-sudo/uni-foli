from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field

from polio_api.core.config import get_settings


class ScholarPaper(BaseModel):
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    citationCount: int = 0
    url: str | None = None


class ScholarSearchResult(BaseModel):
    query: str
    total: int
    papers: list[ScholarPaper]


@dataclass(slots=True)
class ScholarServiceError(Exception):
    status_code: int
    detail: str
    retry_after: int | None = None


def _normalize_authors(raw_authors: Any) -> list[str]:
    if not isinstance(raw_authors, list):
        return []

    names: list[str] = []
    for author in raw_authors:
        if not isinstance(author, dict):
            continue
        name = str(author.get("name", "")).strip()
        if name:
            names.append(name)
    return names


async def search_semantic_scholar_papers(query: str, limit: int = 5) -> ScholarSearchResult:
    settings = get_settings()
    normalized_query = query.strip()
    if not normalized_query:
        raise ScholarServiceError(status_code=400, detail="Query must not be empty.")

    capped_limit = max(1, min(limit, settings.semantic_scholar_max_limit))
    timeout = httpx.Timeout(
        timeout=settings.semantic_scholar_timeout_seconds,
        connect=min(5.0, settings.semantic_scholar_timeout_seconds),
    )

    headers = {
        "Accept": "application/json",
        "User-Agent": "polio-research-copilot/1.0",
    }
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key

    params = {
        "query": normalized_query,
        "limit": capped_limit,
        "fields": "title,abstract,authors,year,citationCount,url",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                settings.semantic_scholar_search_url,
                params=params,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise ScholarServiceError(
            status_code=504,
            detail="Semantic Scholar request timed out. Please try again.",
        ) from exc
    except httpx.RequestError as exc:
        raise ScholarServiceError(
            status_code=503,
            detail="Semantic Scholar is temporarily unreachable. Please retry shortly.",
        ) from exc

    if response.status_code == 429:
        retry_after_raw = response.headers.get("Retry-After")
        retry_after = int(retry_after_raw) if retry_after_raw and retry_after_raw.isdigit() else None
        raise ScholarServiceError(
            status_code=429,
            detail="Semantic Scholar rate limit exceeded. Please retry later.",
            retry_after=retry_after,
        )
    if 500 <= response.status_code:
        raise ScholarServiceError(
            status_code=503,
            detail="Semantic Scholar service error. Please retry later.",
        )
    if response.status_code >= 400:
        raise ScholarServiceError(
            status_code=502,
            detail=f"Semantic Scholar returned an unexpected status ({response.status_code}).",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ScholarServiceError(
            status_code=502,
            detail="Semantic Scholar returned malformed JSON.",
        ) from exc

    data = payload.get("data")
    if not isinstance(data, list):
        raise ScholarServiceError(
            status_code=502,
            detail="Semantic Scholar response format is invalid.",
        )

    papers: list[ScholarPaper] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip()
        if not title:
            continue

        abstract_raw = item.get("abstract")
        abstract = str(abstract_raw).strip() if isinstance(abstract_raw, str) and abstract_raw.strip() else None

        year_raw = item.get("year")
        year = year_raw if isinstance(year_raw, int) else None

        citation_raw = item.get("citationCount")
        citation_count = citation_raw if isinstance(citation_raw, int) and citation_raw >= 0 else 0

        url_raw = item.get("url")
        url = str(url_raw).strip() if isinstance(url_raw, str) and url_raw.strip() else None

        papers.append(
            ScholarPaper(
                title=title,
                abstract=abstract,
                authors=_normalize_authors(item.get("authors")),
                year=year,
                citationCount=citation_count,
                url=url,
            )
        )

    total_raw = payload.get("total")
    total = total_raw if isinstance(total_raw, int) and total_raw >= 0 else len(papers)

    return ScholarSearchResult(
        query=normalized_query,
        total=total,
        papers=papers,
    )


async def search_kci_papers(query: str, limit: int = 5) -> ScholarSearchResult:
    import xml.etree.ElementTree as ET

    settings = get_settings()
    normalized_query = query.strip()
    if not normalized_query:
        raise ScholarServiceError(status_code=400, detail="Query must not be empty.")

    capped_limit = max(1, min(limit, settings.semantic_scholar_max_limit))
    timeout = httpx.Timeout(
        timeout=settings.semantic_scholar_timeout_seconds,
        connect=min(5.0, settings.semantic_scholar_timeout_seconds),
    )

    kci_api_key = getattr(settings, "kci_api_key", "16578589")
    params = {
        "apiCode": "articleSearch",
        "key": kci_api_key,
        "title": normalized_query,
        "displayCount": str(capped_limit),
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                "https://open.kci.go.kr/po/openapi/openApiSearch.kci",
                params=params,
            )
    except httpx.TimeoutException as exc:
        raise ScholarServiceError(
            status_code=504,
            detail="KCI API request timed out. Please try again.",
        ) from exc
    except httpx.RequestError as exc:
        raise ScholarServiceError(
            status_code=503,
            detail="KCI API is temporarily unreachable. Please retry shortly.",
        ) from exc

    if response.status_code >= 400:
        raise ScholarServiceError(
            status_code=502,
            detail=f"KCI returned an unexpected status ({response.status_code}).",
        )

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise ScholarServiceError(
            status_code=502,
            detail="KCI returned malformed XML.",
        ) from exc

    papers: list[ScholarPaper] = []
    
    records = root.findall(".//record")
    for record in records[:capped_limit]:
        article_info = record.find("articleInfo")
        if article_info is None:
            continue
            
        title_ko_elem = article_info.find("title-group/article-title[@lang='original']")
        title_en_elem = article_info.find("title-group/article-title[@lang='english']")
        
        title = ""
        if title_ko_elem is not None and title_ko_elem.text:
            title = title_ko_elem.text.strip()
        elif title_en_elem is not None and title_en_elem.text:
            title = title_en_elem.text.strip()
            
        if not title:
            continue
            
        abstract_ko_elem = article_info.find("abstract-group/abstract[@lang='original']")
        abstract_en_elem = article_info.find("abstract-group/abstract[@lang='english']")
        
        abstract = None
        if abstract_ko_elem is not None and abstract_ko_elem.text:
            abstract = abstract_ko_elem.text.strip()
        elif abstract_en_elem is not None and abstract_en_elem.text:
            abstract = abstract_en_elem.text.strip()
            
        year_elem = article_info.find("pub-year")
        year = None
        if year_elem is not None and year_elem.text and year_elem.text.isdigit():
            year = int(year_elem.text)
            
        url_elem = article_info.find("url")
        url = url_elem.text.strip() if url_elem is not None and url_elem.text else None
        
        authors = []
        author_group = article_info.find("author-group")
        if author_group is not None:
            for author_node in author_group.findall("author/name"):
                if author_node.text:
                    authors.append(author_node.text.strip())
                    
        citation_count = 0
        
        papers.append(
            ScholarPaper(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                citationCount=citation_count,
                url=url,
            )
        )

    return ScholarSearchResult(
        query=normalized_query,
        total=len(papers),
        papers=papers,
    )
