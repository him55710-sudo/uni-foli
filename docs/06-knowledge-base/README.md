# 06 Knowledge Base

The knowledge base is not just a vector store.
It is a retrieval layer with provenance, ranking, and freshness.

## MVP storage choice

Use PostgreSQL plus pgvector.
This keeps transactional records and embeddings in one system.

## Tables

- `source_documents`
- `source_chunks`
- `embeddings`
- `evidence_cards`
- `retrieval_runs`

## Chunking rules

- chunk by semantic section, not fixed length only
- keep titles and heading paths
- store page or paragraph pointers
- keep parent document metadata attached to each chunk

## Retrieval design

- filter by source rank first
- filter by freshness when the topic is time-sensitive
- run hybrid retrieval: metadata filtering + semantic search
- rerank for citation usefulness, not only similarity

## Output shape for downstream services

Each retrieved item should provide:

- quoted text span
- chunk summary
- why it matched
- source metadata
- citation-ready pointer

## Why not a separate vector DB yet

MVP complexity is lower with PostgreSQL plus pgvector.
Move to a dedicated vector database only if retrieval latency, scale, or operational isolation demands it.
