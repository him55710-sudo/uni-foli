from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SourceIngestionStage:
    name: str
    runner_kind: str
    description: str


SOURCE_INGESTION_STAGES = [
    SourceIngestionStage("register_sources", "sync_api", "Register source metadata and crawl policy."),
    SourceIngestionStage("discover_urls", "cron_or_batch", "Discover candidate URLs or official files."),
    SourceIngestionStage("download_assets", "async_worker", "Download remote files into object storage."),
    SourceIngestionStage("hash_and_dedupe", "async_worker", "Compute file hash and skip previously seen content."),
    SourceIngestionStage("parse_content", "async_worker", "Parse into canonical blocks and normalized content."),
    SourceIngestionStage("normalize_metadata", "async_worker", "Extract cycle, university, track, and document type."),
    SourceIngestionStage("chunk_blocks", "async_worker", "Store parsed blocks for retrieval and evidence."),
    SourceIngestionStage("extract_claims", "async_worker", "Run rules-first claim extraction and validation."),
    SourceIngestionStage("detect_conflicts", "batch_worker", "Compare claims across cycles and sources."),
    SourceIngestionStage("index_retrieval", "async_worker", "Embed and lexical-index blocks and claims."),
]
