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

Background worker:

```powershell
.\scripts\start-worker.cmd
```

## Security Defaults

- `APP_ENV` now defaults to `production` and `APP_DEBUG` defaults to `false`.
- Local auth bypass is still available for local development, but only when `APP_ENV=local` and `AUTH_ALLOW_LOCAL_DEV_BYPASS=true` are both set explicitly.
- Production must use real JWT verification settings and must not rely on dummy OAuth provider credentials.
- Social login must remain disabled unless `AUTH_SOCIAL_LOGIN_ENABLED=true`, `AUTH_SOCIAL_STATE_SECRET` is set, and the provider credentials are real.
- Uploads are restricted to `.pdf`, `.txt`, and `.md` by default, with extension, MIME, and size validation enforced by `UPLOAD_ALLOWED_EXTENSIONS` and `UPLOAD_MAX_BYTES`.
- Credentialed wildcard CORS is rejected outside local development.

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

## Research And Provenance

- `STUDENT_RECORD` evidence comes from uploaded student documents and can support claims about student actions.
- `EXTERNAL_RESEARCH` evidence comes from separately ingested research sources and can only support context, comparisons, or recommendations.
- External research must never be used as proof that a student did something.

## Cache And Jobs

- Repeated diagnosis, grounded-answer, and workshop generation calls now use a deterministic cache keyed by scope, model, normalized request payload, evidence keys, and cache version.
- Safe cache targets: repeat diagnosis prompts, extractive grounded answers, and repeated workshop generation prompts with the same evidence set.
- Do not cache: raw uploads, masked source text blobs outside project scope, or outputs whose meaning changes when project evidence changes but the cache key does not.
- Stale-cache risk is highest when project evidence changes, prompt guardrails change, or retrieved research freshness changes without a cache-version bump.
- Long-running diagnosis, research ingestion, render, and async document-parse work now produce persisted job records under `/api/v1/jobs`.
- Failed jobs retain failure history, retry counts, and dead-letter timestamps after retry exhaustion.

## Documentation

Canonical docs now live at the repo root under `../docs/`.

- `../docs/getting-started.md`
- `../docs/monorepo-structure.md`
- `../docs/00-principles/README.md`
- `../docs/07-diagnosis-engine/README.md`
- `../docs/08-chat-orchestration/README.md`
- `../docs/09-drafting-provenance/README.md`

Duplicated backend docs and old root-level backend notes were moved to `../archive/legacy/backend/`.
