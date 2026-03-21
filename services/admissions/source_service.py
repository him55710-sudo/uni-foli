from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.admissions import Source
from domain.enums import LifecycleStatus
from services.admissions.utils import ensure_uuid, slugify


class SourceService:
    def list_sources(self, session: Session) -> list[Source]:
        return list(session.scalars(select(Source).order_by(Source.created_at.desc())))

    def get_source(self, session: Session, source_id: str) -> Source | None:
        return session.get(Source, ensure_uuid(source_id))

    def create_source(
        self,
        session: Session,
        *,
        name: str,
        base_url: str,
        source_tier: object,
        source_category: object,
        organization_name: str | None,
        is_official: bool,
        allow_crawl: bool,
        freshness_days: int,
        crawl_policy: dict[str, object],
    ) -> Source:
        slug = slugify(name)
        existing = session.scalar(select(Source).where(Source.slug == slug))
        if existing is not None:
            existing.name = name
            existing.base_url = base_url
            existing.source_tier = source_tier
            existing.source_category = source_category
            existing.organization_name = organization_name
            existing.is_official = is_official
            existing.allow_crawl = allow_crawl
            existing.freshness_days = freshness_days
            existing.crawl_policy = crawl_policy
            session.flush()
            session.refresh(existing)
            return existing

        source = Source(
            slug=slug,
            name=name,
            base_url=base_url,
            source_tier=source_tier,
            source_category=source_category,
            organization_name=organization_name,
            is_official=is_official,
            allow_crawl=allow_crawl,
            freshness_days=freshness_days,
            crawl_policy=crawl_policy,
            status=LifecycleStatus.ACTIVE,
        )
        session.add(source)
        session.flush()
        session.refresh(source)
        return source


source_service = SourceService()
