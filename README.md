# Polio Admissions Intelligence Backend

Production-usable backend foundation for a Korean admissions copilot focused on:

- official admissions criteria ingestion
- source-tier-aware retrieval
- provenance-preserving claim extraction
- traceable student-file analysis
- policy-safe admissions guidance

## Canonical Runtime Path

The canonical admissions backend runtime path is the root application:

- API: `app/`
- models and migrations: `db/`, `alembic/`
- parsers: `parsers/`
- admissions services: `services/admissions/`
- workers: `workers/`

Historical scaffolds under `services/api`, `services/render`, `services/worker`, `services/ingest`, and `packages/*`
are quarantined references only. They are not the canonical runtime path for official corpus ingestion and analysis.

## What Works Now

- source registration and official-source seed registration
- bounded institutional crawling for trusted admissions domains
- discovered URL tracking with freshness metadata, etag, and last-modified hooks
- download dedupe by file hash and URL dedupe by canonical URL
- canonical ingestion path:
  - `source -> source seed -> crawl job -> discovered URL -> file object -> ingestion job -> document -> document version -> parsed blocks -> chunks`
- selective parser routing:
  - Docling preferred for supported PDFs and HTML when available
  - lightweight parsers fall back automatically with parser trace preserved
- claim extraction scaffold with claim/evidence persistence
- admissions-aware hybrid retrieval with:
  - PostgreSQL full-text lexical ranking when available
  - pgvector-compatible semantic ranking with deterministic local embedding fallback
  - source-tier, freshness, approval, and conflict-aware ranking policy
  - deterministic citation assembly from claim/chunk provenance
- rule-based chunk preselection for claim extraction with persisted selected/skipped reasons
- extraction batching, retry/backoff, timeout-aware failure capture, and prompt version capture
- LiteLLM gateway abstraction with Ollama-compatible local runtime path
- Langfuse-ready extraction tracing with local disablement by config
- human review workflow for pending, approved, rejected, needs_revision, and superseded claims
- eval dataset scaffolding for gold claims, bad claims, evidence spans, unsafe prompts, and weak-evidence examples
- basic retrieval over chunks and claims
- retrieval evaluation case scaffolding for citation-bearing ranking checks
- student file upload and parser-based artifact extraction
- account, tenant, role, and opaque bearer-session auth baseline
- tenant-scoped access control for student files, analysis runs, review tasks, policy flags, citations, and traces
- deletion requests, deletion events, and soft-delete-first cleanup hooks for sensitive student data
- privacy scan persistence with masking modes and admin inspection endpoints
- safer structured logging with secret and PII redaction
- admin inspection for source seeds, crawl jobs, discovered URLs, file objects, parser summaries, and review tasks

## Parser Policy

- `Docling` is in the runtime path and is tried first for supported PDF and HTML files when `DOCLING_ENABLED=true`.
- `pypdf`, lightweight HTML parsing, plain text parsing, and OCR fallback remain as lower-cost fallbacks.
- Every successful parse stores parser trace and fallback reason in the normalized document payload and document metadata.

## Quick Start

1. Create `.env` from `.env.example`
2. Start infrastructure
   - `docker compose up -d postgres redis minio`
3. Install the package
   - `python -m pip install -e .[dev]`
4. Run the canonical API
   - `python -m app.main`
5. Run the canonical worker
   - `python -m workers.runner`
6. Log in for protected routes
   - `POST /api/v1/auth/login`
   - default local admin: `admin@local.polio` / `ChangeMe123!`
   - default local member: `member@local.polio` / `ChangeMe123!`

## Primary Routes

- `GET /api/v1/health`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/sources`
- `POST /api/v1/crawl/seeds`
- `POST /api/v1/crawl/jobs`
- `POST /api/v1/crawl/jobs/{id}/run`
- `GET /api/v1/crawl/discovered-urls`
- `GET /api/v1/documents`
- `POST /api/v1/claims/extract`
- `POST /api/v1/retrieval/search`
- `GET /api/v1/admin/extraction/jobs`
- `GET /api/v1/admin/extraction/failures`
- `GET /api/v1/admin/extraction/stats`
- `GET /api/v1/admin/claims/pending`
- `PATCH /api/v1/admin/claims/{id}/review`
- `POST /api/v1/admin/claims/bulk-low-confidence`
- `GET /api/v1/admin/eval/examples`
- `POST /api/v1/admin/eval/examples`
- `GET /api/v1/admin/retrieval/eval-cases`
- `POST /api/v1/admin/retrieval/eval-cases`
- `POST /api/v1/admin/retrieval/eval-cases/{id}/run`
- `POST /api/v1/student-files`
- `POST /api/v1/student-files/{id}/deletion-requests`
- `POST /api/v1/analysis/runs`
- `POST /api/v1/analysis/runs/{id}/deletion-requests`
- `GET /api/v1/admin/source-seeds`
- `GET /api/v1/admin/crawl-jobs`
- `GET /api/v1/admin/discovered-urls`
- `GET /api/v1/admin/file-objects`
- `GET /api/v1/admin/documents/{id}/parser-summary`
- `GET /api/v1/admin/privacy-scans`
- `GET /api/v1/admin/deletion-requests`
- `POST /api/v1/admin/deletion-requests/{id}/execute`

## Auth And Privacy Baseline

- Student-data endpoints require bearer auth.
- Admin endpoints require an admin role.
- Tenant admins are tenant-scoped. `super_admin` can inspect all tenants.
- Student uploads do not reuse `FileObject` records across tenants.
- Masking happens at ingestion time and is configurable per tenant:
  - `off`
  - `detect_only`
  - `mask_for_index`
  - `mask_all`
- Privacy scans are stored in `privacy_scans` for admin inspection.
- Presidio is wired through `scripts/presidio_masking_helper.py` and can be enabled with a compatible helper Python. Regex fallback stays active for local alpha environments.

## Privacy Docs

- [docs/privacy/README.md](docs/privacy/README.md)
- [docs/privacy/retention-policy.md](docs/privacy/retention-policy.md)
- [docs/privacy/deletion-behavior.md](docs/privacy/deletion-behavior.md)
- [docs/privacy/masking-modes.md](docs/privacy/masking-modes.md)
- [docs/privacy/admin-access-rules.md](docs/privacy/admin-access-rules.md)

## Product Boundary

This backend is designed to:

- interpret official criteria
- map authentic student evidence to evaluation dimensions
- preserve citations and provenance
- warn on stale, low-trust, or conflicting evidence

This backend is intentionally not designed to:

- fabricate activities
- manufacture false records
- promise admission outcomes
- generate deceptive narratives detached from evidence

## Corpus Growth Workflow

1. register a trusted source
2. register one or more source seeds
3. run a crawl job
4. inspect discovered URLs and downloaded file objects
5. inspect parser summaries and fallback traces
6. run claim extraction for selected documents
7. review claims and conflicts

## Claim Extraction Governance

- Chunk selection is rule-based first. The system prefers official, current-cycle, evaluation-heavy sections and skips boilerplate where possible.
- Every extraction job stores:
  - prompt template key and version
  - model provider and model name
  - batch-level request/response payloads
  - retry count and failure reason
  - selected/skipped chunk decisions
- Claims are reviewable by default and support:
  - `pending_review`
  - `approved`
  - `rejected`
  - `needs_revision`
  - `superseded`
- Reviewers can attach evidence-quality scores, notes, exception notes, and overclaim flags.

## Retrieval Policy

- Tier 4 sources are excluded by default.
- Ranking combines lexical, vector, trust, quality, freshness, and policy-aware boosts.
- Approved claims are preferred over unreviewed claims when the evidence otherwise overlaps.
- Open conflicts are surfaced in the response and penalized in ranking instead of silently hidden.
- Current-cycle official guidance receives an explicit boost over older conflicting material.
- Every retrieval hit includes a deterministic citation assembled from source, document, version, claim or chunk, and page context.

## Langfuse And LiteLLM

- `LiteLLM` is the gateway abstraction for extraction calls.
- `Ollama` remains the default local provider via `EXTRACTION_MODEL_PROVIDER=ollama`.
- `Langfuse` tracing is optional. Keep `LANGFUSE_ENABLED=false` for local development unless keys are configured.

## Example Seed Dataset

- [docs/examples/source-seed.sample.json](docs/examples/source-seed.sample.json)

## Current TODOs

- richer university/campus/unit alias seed datasets
- HWP parser path beyond discovery and storage
- retrieval trace persistence, rate limits, and query analytics
- stronger model-based reranker plugged into the current reranking hook
- masked student-text retrieval controls for tenant-scoped analysis retrieval
- reviewer dashboard UI on top of the review APIs
- dedicated privacy helper environment bootstrap for Presidio on Python 3.12/3.13

## More Reading

- [docs/architecture/admissions-backend-foundation.md](docs/architecture/admissions-backend-foundation.md)
