from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from mimetypes import guess_type
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from db.models.admissions import Source, SourceCrawlJob
from db.models.crawl import DiscoveredUrl, SourceSeed
from domain.enums import CrawlJobStatus, DiscoveredUrlStatus, IngestionJobStatus
from services.admissions.ingestion_pipeline_service import ingestion_pipeline_service
from services.admissions.source_ingestion_service import source_ingestion_service
from services.admissions.utils import ensure_uuid


DISCOVERABLE_FILE_EXTENSIONS = (".pdf", ".hwp", ".hwpx", ".txt", ".html", ".htm")


@dataclass(slots=True)
class DiscoveredLink:
    url: str
    label: str | None = None


class AnchorExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[DiscoveredLink] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if href:
            self._current_href = href.strip()
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None and data.strip():
            self._current_text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        text = " ".join(self._current_text).strip() or None
        self.links.append(DiscoveredLink(url=self._current_href, label=text))
        self._current_href = None
        self._current_text = []


class CrawlService:
    def __init__(self) -> None:
        self.robots_cache: dict[str, RobotFileParser | None] = {}

    def create_crawl_job(
        self,
        session: Session,
        *,
        source_id: str,
        source_seed_id: str,
        trigger_mode: str = "manual",
    ) -> SourceCrawlJob:
        source = session.get(Source, ensure_uuid(source_id))
        seed = session.get(SourceSeed, ensure_uuid(source_seed_id))
        if source is None or seed is None or seed.source_id != source.id:
            raise ValueError("Source or seed not found")

        job = SourceCrawlJob(
            source_id=source.id,
            source_seed_id=seed.id,
            seed_url=seed.seed_url,
            crawl_scope="seed",
            trigger_mode=trigger_mode,
            status=CrawlJobStatus.QUEUED,
            job_stats={},
        )
        session.add(job)
        session.flush()
        session.refresh(job)
        return job

    def list_crawl_jobs(self, session: Session, *, source_id: str | None = None) -> list[SourceCrawlJob]:
        stmt = select(SourceCrawlJob).order_by(SourceCrawlJob.created_at.desc())
        if source_id is not None:
            stmt = stmt.where(SourceCrawlJob.source_id == ensure_uuid(source_id))
        return list(session.scalars(stmt))

    def list_discovered_urls(self, session: Session, *, source_id: str | None = None) -> list[DiscoveredUrl]:
        stmt = select(DiscoveredUrl).order_by(DiscoveredUrl.updated_at.desc())
        if source_id is not None:
            stmt = stmt.where(DiscoveredUrl.source_id == ensure_uuid(source_id))
        return list(session.scalars(stmt))

    def run_crawl_job(
        self,
        session: Session,
        *,
        crawl_job_id: str,
        force_refresh: bool = False,
        auto_ingest: bool = True,
    ) -> SourceCrawlJob:
        job = session.get(SourceCrawlJob, ensure_uuid(crawl_job_id))
        if job is None:
            raise ValueError("Crawl job not found")

        source = session.get(Source, job.source_id)
        seed = session.get(SourceSeed, job.source_seed_id) if job.source_seed_id else None
        if source is None or seed is None:
            raise ValueError("Crawl job is missing source or seed")

        settings = get_settings()
        queue: list[tuple[str, int, str | None]] = [(seed.seed_url, 0, None)]
        visited: set[str] = set()
        job.status = CrawlJobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        session.flush()

        discovered_count = 0
        downloaded_count = 0

        with httpx.Client(
            follow_redirects=True,
            timeout=settings.crawler_timeout_seconds,
            headers={"User-Agent": settings.crawler_user_agent},
        ) as client:
            while queue and len(visited) < settings.crawler_max_pages_per_job:
                current_url, depth, parent_url = queue.pop(0)
                canonical_url = self._canonicalize_url(current_url)
                if canonical_url in visited:
                    continue
                visited.add(canonical_url)

                if not self._is_allowed_url(source, seed, canonical_url):
                    self._upsert_discovered_url(
                        session,
                        source=source,
                        seed=seed,
                        crawl_job=job,
                        canonical_url=canonical_url,
                        discovered_from_url=parent_url,
                        depth=depth,
                        status=DiscoveredUrlStatus.BLOCKED,
                        metadata_json={"blocked_reason": "allowlist"},
                    )
                    continue

                if seed.respect_robots_txt and not self._can_fetch(client, canonical_url, settings.crawler_user_agent):
                    self._upsert_discovered_url(
                        session,
                        source=source,
                        seed=seed,
                        crawl_job=job,
                        canonical_url=canonical_url,
                        discovered_from_url=parent_url,
                        depth=depth,
                        status=DiscoveredUrlStatus.BLOCKED,
                        metadata_json={"blocked_reason": "robots_txt"},
                    )
                    continue

                discovered = self._upsert_discovered_url(
                    session,
                    source=source,
                    seed=seed,
                    crawl_job=job,
                    canonical_url=canonical_url,
                    discovered_from_url=parent_url,
                    depth=depth,
                    status=DiscoveredUrlStatus.DISCOVERED,
                    metadata_json={},
                )
                discovered_count += 1

                now = datetime.now(UTC)
                if not force_refresh and discovered.next_refresh_at and discovered.next_refresh_at > now:
                    continue

                headers: dict[str, str] = {}
                if discovered.etag:
                    headers["If-None-Match"] = discovered.etag
                if discovered.last_modified_header:
                    headers["If-Modified-Since"] = discovered.last_modified_header

                try:
                    response = client.get(canonical_url, headers=headers)
                except httpx.HTTPError as exc:
                    discovered.status = DiscoveredUrlStatus.FAILED
                    discovered.metadata_json = {**(discovered.metadata_json or {}), "fetch_error": str(exc)}
                    continue

                discovered.http_status = response.status_code
                discovered.last_seen_at = now
                discovered.latest_crawl_job_id = job.id

                if response.status_code == 304:
                    discovered.status = DiscoveredUrlStatus.INGESTED if discovered.document_id else DiscoveredUrlStatus.FETCHED
                    discovered.next_refresh_at = self._next_refresh_time(source, discovered.is_current_cycle_relevant)
                    continue
                if response.status_code >= 400:
                    discovered.status = DiscoveredUrlStatus.FAILED
                    discovered.metadata_json = {**(discovered.metadata_json or {}), "http_status": response.status_code}
                    continue

                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                payload = response.content
                text_preview = response.text[:3000] if self._is_html_content(canonical_url, content_type) else ""
                relevance_score, is_current_cycle = self._score_relevance(seed, canonical_url, text_preview)

                discovered.content_type = content_type or None
                discovered.etag = response.headers.get("etag")
                discovered.last_modified_header = response.headers.get("last-modified")
                discovered.last_fetched_at = now
                discovered.is_html = self._is_html_content(canonical_url, content_type)
                discovered.is_downloadable_asset = self._is_downloadable_asset(canonical_url, content_type)
                discovered.is_current_cycle_relevant = is_current_cycle
                discovered.relevance_score = relevance_score
                discovered.next_refresh_at = self._next_refresh_time(source, is_current_cycle)

                if discovered.is_html or (seed.allow_binary_assets and discovered.is_downloadable_asset):
                    filename = self._infer_filename(canonical_url, content_type)
                    ingestion_job, _ = source_ingestion_service.register_downloaded_bytes(
                        session,
                        source=source,
                        payload=payload,
                        filename=filename,
                        mime_type=content_type or guess_type(filename)[0] or "application/octet-stream",
                        source_url=canonical_url,
                        namespace=f"sources/{source.slug}",
                        source_crawl_job_id=str(job.id),
                        source_document_key=canonical_url,
                        metadata_json={
                            "discovered_url_id": str(discovered.id),
                            "seed_url": seed.seed_url,
                            "parser_hints": {"prefer_docling": filename.lower().endswith(".pdf")},
                        },
                    )
                    downloaded_count += 1
                    discovered.file_object_id = ingestion_job.file_object_id
                    discovered.status = DiscoveredUrlStatus.FETCHED

                    if auto_ingest:
                        processed = ingestion_pipeline_service.process_ingestion_job(session, ingestion_job)
                        if processed.status == IngestionJobStatus.SUCCEEDED and processed.document_id is not None:
                            discovered.document_id = processed.document_id
                            discovered.status = DiscoveredUrlStatus.INGESTED

                if discovered.is_html and depth < seed.max_depth:
                    for link in self._extract_links(response.text, canonical_url):
                        candidate = self._canonicalize_url(link.url)
                        if not candidate or candidate in visited:
                            continue
                        self._upsert_discovered_url(
                            session,
                            source=source,
                            seed=seed,
                            crawl_job=job,
                            canonical_url=candidate,
                            discovered_from_url=canonical_url,
                            depth=depth + 1,
                            status=DiscoveredUrlStatus.DISCOVERED,
                            metadata_json={"anchor_text": link.label},
                        )
                        if self._is_allowed_url(source, seed, candidate):
                            queue.append((candidate, depth + 1, canonical_url))

                session.flush()

        seed.last_crawled_at = datetime.now(UTC)
        seed.last_succeeded_at = datetime.now(UTC)
        seed.last_error_message = None
        job.discovered_url_count = discovered_count
        job.downloaded_file_count = downloaded_count
        job.finished_at = datetime.now(UTC)
        job.status = CrawlJobStatus.SUCCEEDED
        job.job_stats = {
            "visited_count": len(visited),
            "auto_ingest": auto_ingest,
            "force_refresh": force_refresh,
        }
        session.flush()
        session.refresh(job)
        return job

    def _upsert_discovered_url(
        self,
        session: Session,
        *,
        source: Source,
        seed: SourceSeed,
        crawl_job: SourceCrawlJob,
        canonical_url: str,
        discovered_from_url: str | None,
        depth: int,
        status: DiscoveredUrlStatus,
        metadata_json: dict[str, object],
    ) -> DiscoveredUrl:
        record = session.scalar(
            select(DiscoveredUrl).where(
                DiscoveredUrl.source_id == source.id,
                DiscoveredUrl.canonical_url == canonical_url,
            )
        )
        now = datetime.now(UTC)
        if record is None:
            record = DiscoveredUrl(
                source_id=source.id,
                source_seed_id=seed.id,
                latest_crawl_job_id=crawl_job.id,
                canonical_url=canonical_url,
                url_hash=self._url_hash(canonical_url),
                discovered_from_url=discovered_from_url,
                depth=depth,
                first_seen_at=now,
                last_seen_at=now,
                status=status,
                metadata_json=metadata_json,
            )
            session.add(record)
        else:
            record.source_seed_id = seed.id
            record.latest_crawl_job_id = crawl_job.id
            record.discovered_from_url = discovered_from_url or record.discovered_from_url
            record.depth = min(record.depth, depth) if record.depth is not None else depth
            record.last_seen_at = now
            if status in {DiscoveredUrlStatus.BLOCKED, DiscoveredUrlStatus.FAILED} or record.status == DiscoveredUrlStatus.DISCOVERED:
                record.status = status
            record.metadata_json = {**(record.metadata_json or {}), **metadata_json}
        session.flush()
        return record

    def _extract_links(self, html: str, base_url: str) -> list[DiscoveredLink]:
        parser = AnchorExtractor()
        parser.feed(html)
        return [
            DiscoveredLink(url=urljoin(base_url, item.url), label=item.label)
            for item in parser.links
            if item.url and not item.url.lower().startswith(("javascript:", "mailto:", "tel:"))
        ]

    def _canonicalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme:
            return url
        normalized_query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
        normalized_path = parsed.path or "/"
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                normalized_path,
                "",
                normalized_query,
                "",
            )
        )

    def _is_allowed_url(self, source: Source, seed: SourceSeed, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.netloc.lower()
        if seed.allowed_domains and host not in {domain.lower() for domain in seed.allowed_domains}:
            return False
        if seed.allowed_path_prefixes and not any(parsed.path.startswith(prefix) for prefix in seed.allowed_path_prefixes):
            return False
        if any(parsed.path.startswith(prefix) for prefix in seed.denied_path_prefixes):
            return False
        if not source.allow_crawl:
            return False
        return True

    def _can_fetch(self, client: httpx.Client, url: str, user_agent: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = self.robots_cache.get(robots_url)
        if parser is None:
            robot_parser = RobotFileParser()
            try:
                response = client.get(robots_url)
                if response.status_code >= 400:
                    self.robots_cache[robots_url] = None
                    return True
                robot_parser.parse(response.text.splitlines())
                self.robots_cache[robots_url] = robot_parser
                parser = robot_parser
            except httpx.HTTPError:
                self.robots_cache[robots_url] = None
                return True
        if parser is None:
            return True
        return parser.can_fetch(user_agent, url)

    def _is_html_content(self, url: str, content_type: str) -> bool:
        lowered = url.lower()
        return lowered.endswith((".html", ".htm")) or content_type == "text/html"

    def _is_downloadable_asset(self, url: str, content_type: str) -> bool:
        lowered = url.lower()
        if lowered.endswith(DISCOVERABLE_FILE_EXTENSIONS):
            return True
        return content_type in {
            "application/pdf",
            "application/haansofthwp",
            "application/x-hwp",
            "application/octet-stream",
            "text/plain",
        }

    def _infer_filename(self, url: str, content_type: str) -> str:
        parsed = urlparse(url)
        tail = parsed.path.rstrip("/").split("/")[-1] or "index"
        if "." not in tail:
            if content_type == "text/html":
                tail = f"{tail}.html"
            elif content_type == "application/pdf":
                tail = f"{tail}.pdf"
            elif content_type == "text/plain":
                tail = f"{tail}.txt"
            else:
                tail = f"{tail}.bin"
        return tail

    def _score_relevance(self, seed: SourceSeed, url: str, text_preview: str) -> tuple[float, bool]:
        basis = f"{url} {text_preview}".lower()
        current_cycle_year = seed.current_cycle_year_hint or datetime.now(UTC).year
        score = 0.2
        if any(keyword in basis for keyword in ("모집요강", "전형", "입학", "학생부종합", "guidebook", "admission")):
            score += 0.35
        if str(current_cycle_year) in basis:
            score += 0.3
        if any(keyword in basis for keyword in ("faq", "공지", "설명회", "시행계획")):
            score += 0.15
        is_current_cycle = str(current_cycle_year) in basis
        return min(score, 1.0), is_current_cycle

    def _next_refresh_time(self, source: Source, is_current_cycle_relevant: bool) -> datetime:
        base_days = max(1, source.freshness_days)
        refresh_days = max(1, base_days // 2) if is_current_cycle_relevant else base_days
        return datetime.now(UTC) + timedelta(days=refresh_days)

    def _url_hash(self, url: str) -> str:
        import hashlib

        return hashlib.sha256(url.encode("utf-8")).hexdigest()


crawl_service = CrawlService()
