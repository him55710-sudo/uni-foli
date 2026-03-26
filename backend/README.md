# Polio Backend

`backend/` is the only backend source of truth in this repository.

Do not add new backend code to archived root-level scaffolds or duplicated legacy folders.

## Run

From the repo root:

```powershell
.\scripts\setup-local.cmd sqlite
.\scripts\start-api.cmd
```

Or from `backend/` directly:

```powershell
.\scripts\setup-local.cmd sqlite
.\scripts\start-api.cmd
```

Swagger UI: `http://127.0.0.1:8000/docs`

If Windows PowerShell blocks `.ps1` execution, use the `.cmd` wrappers under `scripts/`.

## Backend Map

- `services/api/src/polio_api`: FastAPI app, routes, services, persistence wiring
- `services/worker/src/polio_worker`: worker entrypoint
- `services/ingest/src/polio_ingest`: ingest flow
- `services/render/src/polio_render`: export renderers
- `services/render/templates`: render templates such as HWPX skeleton assets
- `packages/domain/src/polio_domain`: backend domain enums and constants
- `packages/shared/src/polio_shared`: shared backend helpers and path utilities
- `packages/parsers`: document parsing helpers
- `packages/pipelines`: ingestion and analysis pipelines
- `packages/prompts`: backend prompt package area
- `alembic`: database migrations
- `infra`: local infrastructure notes
- `tests`: backend-local tests

## Product Boundary

This backend exists for:

- evidence-grounded diagnosis
- source-safe drafting support
- student-owned document parsing
- selected-format export

This backend does not exist for:

- guaranteed admission prediction
- invented achievements
- unsupported scraping or copyrighted source misuse

## Documentation

Canonical docs now live at the repo root under `../docs/`.

- `../docs/getting-started.md`
- `../docs/monorepo-structure.md`
- `../docs/00-principles/README.md`
- `../docs/07-diagnosis-engine/README.md`
- `../docs/08-chat-orchestration/README.md`
- `../docs/09-drafting-provenance/README.md`

Duplicated backend docs and old root-level backend notes were moved to `../archive/legacy/backend/`.
