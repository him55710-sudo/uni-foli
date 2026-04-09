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

Swagger UI: `http://127.0.0.1:8000/docs` when `APP_ENV=local` or `API_DOCS_ENABLED=true`

If Windows PowerShell blocks `.ps1` execution, use the `.cmd` wrappers under `scripts/`.

Background worker:

```powershell
.\scripts\start-worker.cmd
```

## Vercel

Use a separate Vercel project whose Root Directory is `backend/`.

- `main.py` now exposes the FastAPI `app` from the backend root so Vercel can detect the ASGI entrypoint.
- Use a real managed database in `DATABASE_URL`. SQLite on Vercel is ephemeral and should only be used for throwaway testing.
- Uploads and rendered files should be treated as temporary. On Vercel, `POLIO_STORAGE_ROOT` can point to `/tmp/polio` and the backend will also auto-detect the Vercel runtime.
- Background thread dispatch is intentionally skipped on Vercel. If you deploy without a separate worker, use the synchronous request paths from the frontend by setting `VITE_SYNC_API_JOBS=true` there.
- Large ML packages are optional now. Install `.[ml]` and/or `.[privacy]` only when you need the sentence-transformers or Presidio-backed paths.

## Security Defaults

- `APP_ENV` now defaults to `production` and `APP_DEBUG` defaults to `false`.
- Interactive API docs are hidden by default outside local development unless `API_DOCS_ENABLED=true` is set explicitly.
- Local auth bypass is still available for local development, but only when `APP_ENV=local` and `AUTH_ALLOW_LOCAL_DEV_BYPASS=true` are both set explicitly.
- Production must use real JWT verification settings and must not rely on dummy OAuth provider credentials.
- Social login must remain disabled unless `AUTH_SOCIAL_LOGIN_ENABLED=true`, `AUTH_SOCIAL_STATE_SECRET` is set, the provider credentials are real, and non-local redirect URIs do not point at localhost.
- OAuth state is signed, TTL-bound, client-bound, and rejected on replay within the current API process.
- Uploads are restricted to `.pdf`, `.txt`, and `.md` by default, with extension, MIME, and size validation enforced by `UPLOAD_ALLOWED_EXTENSIONS` and `UPLOAD_MAX_BYTES`.
- Remote research URL fetches are limited to public `http`/`https` hosts and capped by `RESEARCH_FETCH_MAX_BYTES`.
- `KCI_API_KEY` must be set explicitly before KCI search is enabled.
- Live web search is optional and disabled by default (`LIVE_WEB_SEARCH_ENABLED=false`, `LIVE_WEB_SEARCH_PROVIDER=none`).
- When live web is requested but unavailable, the API falls back to Semantic Scholar and returns a limitation note.
- Render job responses expose an authenticated `download_url`, not internal filesystem paths.
- Workshop render stream tokens expire server-side after five minutes and are cleared after use.
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
- Search responses now preserve canonical source typing:
  - `uploaded_student_record`
  - `academic_source`
  - `official_guideline`
  - `live_web_source`
- External research must never be used as proof that a student did something.
- Paid LLM selection and paid live web provider selection are separate architecture decisions.

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
- `../docs/12-security-compliance/README.md`
- `../docs/reports/polio_security_hardening_20260330.md`
- `../docs/research-search-architecture.md`

Duplicated backend docs and old root-level backend notes were moved to `../archive/legacy/backend/`.
