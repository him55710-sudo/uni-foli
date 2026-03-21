from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.admissions import Source
from db.models.crawl import SourceSeed
from domain.enums import LifecycleStatus, SourceSeedType
from services.admissions.utils import ensure_uuid


class SourceSeedService:
    def create_seed(
        self,
        session: Session,
        *,
        source_id: str,
        seed_type: SourceSeedType,
        label: str,
        seed_url: str,
        allowed_domains: list[str] | None = None,
        allowed_path_prefixes: list[str] | None = None,
        denied_path_prefixes: list[str] | None = None,
        max_depth: int = 2,
        current_cycle_year_hint: int | None = None,
        allow_binary_assets: bool = True,
        respect_robots_txt: bool = True,
        metadata_json: dict[str, object] | None = None,
    ) -> SourceSeed:
        source = session.get(Source, ensure_uuid(source_id))
        if source is None:
            raise ValueError("Source not found")

        existing = session.scalar(
            select(SourceSeed).where(
                SourceSeed.source_id == source.id,
                SourceSeed.seed_url == seed_url,
            )
        )
        inferred_domain = urlparse(seed_url).netloc.lower()
        if existing is not None:
            existing.seed_type = seed_type
            existing.label = label
            existing.allowed_domains = allowed_domains or [inferred_domain]
            existing.allowed_path_prefixes = allowed_path_prefixes or source.crawl_policy.get("allowed_paths", [])
            existing.denied_path_prefixes = denied_path_prefixes or source.crawl_policy.get("denied_paths", [])
            existing.max_depth = max_depth
            existing.current_cycle_year_hint = current_cycle_year_hint
            existing.allow_binary_assets = allow_binary_assets
            existing.respect_robots_txt = respect_robots_txt
            existing.status = LifecycleStatus.ACTIVE
            existing.metadata_json = metadata_json or existing.metadata_json
            session.flush()
            session.refresh(existing)
            return existing

        seed = SourceSeed(
            source_id=source.id,
            seed_type=seed_type,
            label=label,
            seed_url=seed_url,
            allowed_domains=allowed_domains or [inferred_domain],
            allowed_path_prefixes=allowed_path_prefixes or source.crawl_policy.get("allowed_paths", []),
            denied_path_prefixes=denied_path_prefixes or source.crawl_policy.get("denied_paths", []),
            max_depth=max_depth,
            current_cycle_year_hint=current_cycle_year_hint,
            allow_binary_assets=allow_binary_assets,
            respect_robots_txt=respect_robots_txt,
            status=LifecycleStatus.ACTIVE,
            metadata_json=metadata_json or {},
        )
        session.add(seed)
        session.flush()
        session.refresh(seed)
        return seed

    def list_seeds(self, session: Session, *, source_id: str | None = None) -> list[SourceSeed]:
        stmt = select(SourceSeed).order_by(SourceSeed.created_at.desc())
        if source_id is not None:
            stmt = stmt.where(SourceSeed.source_id == ensure_uuid(source_id))
        return list(session.scalars(stmt))

    def get_seed(self, session: Session, seed_id: str) -> SourceSeed | None:
        return session.get(SourceSeed, ensure_uuid(seed_id))


source_seed_service = SourceSeedService()
