# Open Source Catalog

This file lists the open-source components that fit the backend plan.

## Selection rules

- Prefer components that reduce ops burden for a one-developer team.
- Prefer tools with strong official docs and active maintenance.
- Avoid introducing a separate infrastructure category unless it removes major complexity.

## Core components to use now

| Name | Role in polio | Why it fits | Status | Local path |
| --- | --- | --- | --- | --- |
| FastAPI | HTTP API and internal services | Fast to build, Python-native, strong typing | downloaded | `references/open-source/fastapi` |
| PostgreSQL | primary relational store | one database for users, jobs, reports, audit logs | recommended | external dependency |
| pgvector | embeddings inside PostgreSQL | keeps retrieval in the same operational boundary for MVP | downloaded | `references/open-source/pgvector` |
| Alembic | database migrations | beginner-friendly schema history and rollback path | downloaded | `references/open-source/alembic` |
| pypdf | PDF text extraction | lightweight first parser for uploaded student PDFs | downloaded | `references/open-source/pypdf` |
| ReportLab | PDF export | stable Python PDF generation for backend workers | installed package | PyPI package |
| python-pptx | PPTX export | reliable PowerPoint generation directly from Python | downloaded | `references/open-source/python-pptx` |
| Valkey | cache, rate-limit state, async broker | open-source key-value store for realtime workloads | downloaded | `references/open-source/valkey` |
| Docling | advanced document parsing | strong document understanding and local execution for later upgrades | downloaded | `references/open-source/docling` |
| Presidio | PII detection and masking | critical for student-record privacy | downloaded | `references/open-source/presidio` |
| LiteLLM | model gateway and provider abstraction | lets the backend swap models without rewriting app code | downloaded | `references/open-source/litellm` |
| Langfuse | traces, prompts, evals, quality review | required for debugging hallucinations and regressions | downloaded | `references/open-source/langfuse` |

## Core components to use slightly later

| Name | Role in polio | Why it fits | Status | Local path |
| --- | --- | --- | --- | --- |
| PptxGenJS | alternate PPTX rendering path | useful if the render service later moves to Node.js | downloaded | `references/open-source/pptxgenjs` |
| python-hwpx | HWPX ecosystem reference | useful for future full-fidelity HWPX support, but not runtime-critical today | downloaded | `references/open-source/python-hwpx` |
| pgvector-python | Python-side pgvector helpers | useful when vector search code expands beyond SQLAlchemy basics | downloaded | `references/open-source/pgvector-python` |
| Citation.js | reference formatting | helps with bibliography and reference normalization | downloaded | `references/open-source/citation-js` |
| SeaweedFS or managed S3 | object storage | use managed S3 first; self-host SeaweedFS only when needed | recommended | not downloaded |
| Haystack or LlamaIndex | retrieval orchestration | useful if custom retrieval code becomes too costly | recommended | not downloaded |

## Components intentionally not chosen for MVP

### Separate vector database

Do not start with Qdrant, Weaviate, or Milvus unless retrieval scale clearly forces a split.
For MVP, PostgreSQL + pgvector keeps the architecture smaller.

### Self-hosted identity suite

Do not start with a heavy self-hosted IAM stack.
If you need open-source auth later, evaluate Ory or Keycloak, but keep MVP auth simple.

### Custom model training

Do not pretrain or fine-tune an admissions model before the retrieval and evaluation loop is proven.

## Section-by-section recommendations

### Student ingestion

- pypdf
- Presidio
- PostgreSQL

### Knowledge base

- PostgreSQL
- pgvector
- Alembic
- optional Haystack or LlamaIndex

### Diagnosis engine

- FastAPI
- LiteLLM
- PostgreSQL

### Chat orchestration

- LiteLLM
- Langfuse
- Valkey

### Drafting and provenance

- PostgreSQL
- Citation.js

### Render and export

- ReportLab
- python-pptx
- template-based HWPX renderer
- PptxGenJS later if the render service becomes Node-based

### Security and compliance

- Presidio
- Valkey for short-lived secrets and replay protection
- OpenTelemetry + Langfuse for audits

## Download policy in this workspace

Common repositories that are broadly useful across the whole backend are stored in:

- `references/open-source/<repo-name>`

Optional repositories are only listed unless they are needed repeatedly.

## Current runtime note

On this machine, Python is `3.14`, so `python-hwpx` is kept as a downloaded reference rather than a required runtime dependency.
The current HWPX renderer therefore uses a bundled skeleton template instead of that library.
