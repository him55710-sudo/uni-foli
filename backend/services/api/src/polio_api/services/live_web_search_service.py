from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

import httpx

from polio_api.core.config import get_settings
from polio_api.services.scholar_service import ScholarPaper, ScholarSearchResult

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_CITATION_RE = re.compile(r"cited by\s+(\d+)", re.IGNORECASE)


@dataclass(slots=True)
class LiveWebSearchUnavailable(Exception):
    reason: str


@dataclass(slots=True)
class LiveWebSearchError(Exception):
    reason: str
    retry_after: int | None = None


def _live_web_provider_name() -> str:
    settings = get_settings()
    return (settings.live_web_search_provider or "").strip().lower() or "none"


def _live_web_unavailable_reason() -> str | None:
    settings = get_settings()
    if not settings.live_web_search_enabled:
        return "Live web search is disabled in server config."

    provider = _live_web_provider_name()
    if not provider or provider == "none":
        return "Live web search provider is not configured."
    if provider != "serpapi":
        return f"Live web provider '{provider}' is not supported."
    if not (settings.live_web_search_api_key or "").strip():
        return "Live web search provider key is missing."
    return None


async def search_live_web_papers(query: str, limit: int = 5) -> ScholarSearchResult:
    unavailable_reason = _live_web_unavailable_reason()
    if unavailable_reason is not None:
        raise LiveWebSearchUnavailable(unavailable_reason)

    settings = get_settings()
    provider = _live_web_provider_name()
    normalized_query = query.strip()
    if not normalized_query:
        raise LiveWebSearchError("Query must not be empty.")

    capped_limit = max(1, min(limit, 20))
    timeout = httpx.Timeout(
        timeout=settings.live_web_search_timeout_seconds,
        connect=min(5.0, settings.live_web_search_timeout_seconds),
    )

    params = {
        # Use general web search instead of scholar-only index so live_web can
        # retrieve official notices and current web pages.
        "engine": "google",
        "q": normalized_query,
        "num": capped_limit,
        "api_key": settings.live_web_search_api_key,
        "hl": "ko",
        "gl": "kr",
        "safe": "active",
    }

    headers = {
        "Accept": "application/json",
        "User-Agent": "polio-live-web-search/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                settings.live_web_search_endpoint,
                params=params,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise LiveWebSearchError("Live web provider timed out. Falling back to indexed sources.") from exc
    except httpx.RequestError as exc:
        raise LiveWebSearchError("Live web provider is unreachable. Falling back to indexed sources.") from exc

    if response.status_code in {401, 403}:
        raise LiveWebSearchUnavailable("Live web provider key is invalid.")
    if response.status_code == 429:
        retry_after_raw = response.headers.get("Retry-After")
        retry_after = int(retry_after_raw) if retry_after_raw and retry_after_raw.isdigit() else None
        raise LiveWebSearchError(
            "Live web provider rate limit exceeded. Falling back to indexed sources.",
            retry_after=retry_after,
        )
    if response.status_code >= 500:
        raise LiveWebSearchError("Live web provider service error. Falling back to indexed sources.")
    if response.status_code >= 400:
        raise LiveWebSearchError(
            f"Live web provider returned status {response.status_code}. Falling back to indexed sources."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise LiveWebSearchError("Live web provider returned malformed JSON. Falling back to indexed sources.") from exc

    papers = _parse_serpapi_papers(payload, limit=capped_limit)
    return ScholarSearchResult(
        query=normalized_query,
        total=len(papers),
        papers=papers,
        source="live_web",
        requested_source="live_web",
        fallback_applied=False,
        limitation_note=None,
        providers_used=[f"live_web:{provider}"],
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        source_type_counts={},
    )


def _parse_serpapi_papers(payload: Any, *, limit: int) -> list[ScholarPaper]:
    if not isinstance(payload, dict):
        return []

    raw_results: list[dict[str, Any]] = []
    for key in ("organic_results", "news_results", "results", "scholar_results"):
        value = payload.get(key)
        if isinstance(value, list):
            raw_results.extend([item for item in value if isinstance(item, dict)])

    papers: list[ScholarPaper] = []
    for item in raw_results:
        title = _first_non_empty(item.get("title"), item.get("headline"), item.get("name"))
        if not title:
            continue

        snippet = _first_non_empty(
            item.get("snippet"),
            item.get("summary"),
            item.get("description"),
            item.get("snippet_highlighted_words"),
        )

        publication_info = item.get("publication_info")
        publication_summary = ""
        authors: list[str] = []
        if isinstance(publication_info, dict):
            publication_summary = str(publication_info.get("summary") or "").strip()
            author_rows = publication_info.get("authors")
            if isinstance(author_rows, list):
                for author in author_rows:
                    if isinstance(author, dict):
                        name = str(author.get("name") or "").strip()
                        if name:
                            authors.append(name)
        if not authors and publication_summary:
            authors = _extract_authors_from_summary(publication_summary)
        if not authors:
            source_name = _first_non_empty(item.get("source"), item.get("displayed_link"))
            if source_name:
                authors = [source_name]

        url = _first_non_empty(item.get("link"), item.get("url"))
        year = _extract_year(
            " ".join(
                part
                for part in [
                    str(item.get("year") or "").strip(),
                    str(item.get("date") or "").strip(),
                    publication_summary,
                    snippet,
                ]
                if part
            )
        )
        citation_count = _extract_citation_count(item, publication_summary, snippet)

        papers.append(
            ScholarPaper(
                title=title,
                abstract=snippet or None,
                authors=authors[:5],
                year=year,
                citationCount=citation_count,
                url=url or None,
            )
        )
        if len(papers) >= limit:
            break
    return papers


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item.strip()
    return ""


def _extract_authors_from_summary(summary: str) -> list[str]:
    left = summary.split(" - ", 1)[0].strip()
    if not left:
        return []
    rows = [item.strip() for item in left.split(",")]
    return [item for item in rows if len(item) > 1][:5]


def _extract_year(text: str) -> int | None:
    if not text:
        return None
    if not _YEAR_RE.search(text):
        return None
    # Regex includes a capture group; rebuild full year safely.
    year_candidates = re.findall(r"\b(?:19|20)\d{2}\b", text)
    if not year_candidates:
        return None
    try:
        return int(year_candidates[-1])
    except ValueError:
        return None


def _extract_citation_count(item: dict[str, Any], publication_summary: str, snippet: str) -> int:
    citation_raw = item.get("cited_by")
    if isinstance(citation_raw, dict):
        value = citation_raw.get("value")
        if isinstance(value, int) and value >= 0:
            return value

    citation_text = " ".join(
        part
        for part in [
            publication_summary,
            snippet,
            str(item.get("inline_links") or ""),
        ]
        if part
    )
    match = _CITATION_RE.search(citation_text)
    if match:
        try:
            return max(0, int(match.group(1)))
        except ValueError:
            return 0
    return 0
