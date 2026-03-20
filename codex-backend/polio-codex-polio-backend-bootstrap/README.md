# polio Backend Blueprint

This workspace turns the Gemini planning thread into a backend that a beginner can actually run and extend.

## Start Here

1. Read `BEGINNER_GUIDE.md`
2. Run `.\scripts\setup-local.cmd`
3. Run `.\scripts\start-api.cmd`
4. Open `http://127.0.0.1:8000/docs`

## What Works Now

- FastAPI backend with Swagger docs
- project creation and listing
- file upload storage under `storage/uploads/`
- automatic ingest for `pdf`, `txt`, `md`
- parsed document and chunk storage
- document-based draft starter generation
- render job queue with one selected output format
- real file generation for `pdf`, `pptx`, `hwpx`
- worker CLI for queued render jobs
- Alembic migration structure
- PostgreSQL + pgvector local recipe

## One Important Rule

The backend never renders every format automatically.

The user chooses exactly one of:

- `pdf`
- `pptx`
- `hwpx`

That format choice is stored in the render job and processed later.

## Renderers Included

- `pdf`: ReportLab-based styled document export
- `pptx`: `python-pptx` slide deck export
- `hwpx`: template-based HWPX package export built from a bundled skeleton

## Ingest Flow Included

1. User uploads a file
2. Backend stores it in `storage/uploads/<project-id>/`
3. If the file is `pdf`, `txt`, or `md`, the ingest service parses it immediately
4. Parsed results are stored in `parsed_documents` and `document_chunks`
5. The user can create a starter draft from that parsed document

## Database Modes

You have two practical ways to run this project.

### Easy local mode

- run `.\scripts\setup-local.cmd` (defaults to SQLite)
- run the API
- use SQLite in `storage/runtime/polio.db`

### Recommended dev mode

- run `.\scripts\setup-local.cmd postgres`
- start Postgres + Valkey
- run Alembic migrations
- use PostgreSQL + pgvector

## Code Map

- `services/api/src/polio_api`: main API app, routes, DB services
- `services/worker/src/polio_worker`: worker CLI for queued jobs
- `services/ingest/src/polio_ingest`: parser and chunking logic
- `services/render/src/polio_render`: PDF, PPTX, HWPX renderers
- `services/render/templates`: bundled render templates like HWPX skeletons
- `packages/domain/src/polio_domain`: enums and domain constants
- `packages/shared/src/polio_shared`: path helpers and shared utilities
- `alembic`: database migration files
- `infra/postgres`: Postgres init scripts and notes
- `references/open-source`: downloaded upstream open-source snapshots

## Current Product Boundary

`polio` is not an admission predictor.

This backend is designed for:

- evidence-grounded fit diagnosis
- student record parsing and organization
- source-based drafting support
- selected-format export

This backend is intentionally not designed for:

- exact admission probability
- private accepted-student dataset benchmarking
- copyrighted source scraping without permission
- day-1 binary `.hwp` output

## Folder Guide

- `docs/00-principles`: product and risk rules
- `docs/01-product-boundary`: scope and non-goals
- `docs/02-domain-model`: entities and state transitions
- `docs/03-identity-consent`: consent and minors
- `docs/04-student-ingestion`: upload and parsing design
- `docs/05-source-ingestion`: admissions source collection
- `docs/06-knowledge-base`: chunking and retrieval
- `docs/07-diagnosis-engine`: scoring and recommendation logic
- `docs/08-chat-orchestration`: model routing and tools
- `docs/09-drafting-provenance`: source-safe writing workflow
- `docs/10-render-export`: export design
- `docs/11-notifications-workflow`: reminders and workflow
- `docs/12-security-compliance`: privacy and security
- `docs/13-observability-eval`: tracing and quality review
- `docs/14-delivery-roadmap`: phased build order

## More Reading

- `GEMINI_REVIEW.md`: what was changed from the original Gemini plan
- `ARCHITECTURE_OVERVIEW.md`: high-level service boundaries
- `OPEN_SOURCE_CATALOG.md`: open-source choices and rationale
