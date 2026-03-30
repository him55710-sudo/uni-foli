# Polio Monorepo

Polio is an execution-oriented AI platform for students.

It should reduce anxiety, show the next safe action, and connect real student records
to grounded drafting. It should not invent activity, promise admission, or polish fiction
into something that looks true.

## Product Guardrails

- Do not fabricate activities or experiences.
- Do not exaggerate what the student did not actually do.
- Do not imply guaranteed admission outcomes.
- Do not generate outputs that clearly exceed the student's evidenced level.
- Ground all generation in actual records, conversation context, and explicit goals.
- When evidence is missing, stop guessing and suggest the next action.

## Source Of Truth

The current monorepo must be read from these paths first:

- `frontend/`: source of truth for the web app
- `backend/`: source of truth for the Python backend and runtime services
- `packages/shared-contracts/`: future home for shared request and response contracts
- `docs/`: source of truth for product, architecture, and safety documentation
- `scripts/`: root entrypoints that forward to backend workflows

Do not treat the old root `app/`, `db/`, `services/`, `pipelines/`, or `workers/` layout as real.
Those paths are not present in this checkout.

## Requested Axes Status

- `ai studio ui,ux design/`: not present in this checkout
- `codex-backend/polio-codex-polio-backend-bootstrap/`: not present in this checkout
- root `app/`, `db/`, `services/`, `pipelines/`: not present in this checkout

## Repository Map

- `frontend/`: current React and Vite application
- `backend/`: FastAPI API, worker, ingest, render, shared backend packages
- `packages/shared-contracts/`: reserved contract package for frontend and backend wiring
- `docs/`: canonical docs, getting-started notes, architecture, privacy, and reports
- `scripts/`: root wrappers for setup, migrations, infra, and API startup
- `tests/smoke/`: root smoke tests against the real backend runtime
- `archive/legacy/`: quarantined duplicate docs, old tests, deprecated scripts, and unused assets
- `references/`: open-source reference index, not runtime code
- `prompts/`: temporary root prompt assets awaiting explicit backend loader wiring

## Run Locally

### Backend

SQLite mode:

```powershell
.\scripts\setup-local.cmd sqlite
.\scripts\start-api.cmd
```

PostgreSQL mode:

```powershell
.\scripts\setup-local.cmd postgres
.\scripts\start-infra.cmd
.\scripts\migrate.cmd
.\scripts\start-api.cmd
```

Swagger UI: `http://127.0.0.1:8000/docs` when `APP_ENV=local` or `API_DOCS_ENABLED=true`

If your Windows PowerShell execution policy blocks `.ps1` files, use the `.cmd` wrappers in
`scripts/` instead of calling the PowerShell files directly.

Security note:
`APP_ENV` defaults to `production` in the backend config. If you want the local auth bypass for development, set both `APP_ENV=local` and `AUTH_ALLOW_LOCAL_DEV_BYPASS=true` explicitly in your local `.env`. Production must not enable that bypass.
`/docs` is also hidden by default outside local development unless `API_DOCS_ENABLED=true` is set explicitly.
If social login is enabled, production redirect URIs must not point at localhost. KCI-backed research search also now requires an explicit `KCI_API_KEY`.

### Frontend

```powershell
.\scripts\start-frontend.cmd
```

The frontend defaults to `http://localhost:8000`.
Guest mode is intended for local development and only stays enabled automatically in `npm run dev`.
To force guest mode in a non-dev environment, set `VITE_ALLOW_GUEST_MODE=true` explicitly.

If you prefer to run it manually:

```powershell
cd frontend
npm install
npm run dev
```

## Test

Use the real-runtime smoke suite at the repo root:

```powershell
python -m pytest tests/smoke -q
```

Security regression suite:

```powershell
.\scripts\security-regression.cmd
```

Frontend build check:

```powershell
cd frontend
npm run build
```

## Development Rules

- Add new backend code only under `backend/`.
- Add new frontend code only under `frontend/`.
- Put shared API contracts in `packages/shared-contracts/` instead of duplicating DTOs later.
- Treat `archive/legacy/` as read-only history, not a development surface.
- Keep docs in `docs/`, not duplicated inside `backend/`.
- Preserve Polio safety rules over output polish.

## Key Docs

- `docs/getting-started.md`
- `docs/monorepo-structure.md`
- `docs/00-principles/README.md`
- `docs/07-diagnosis-engine/README.md`
- `docs/08-chat-orchestration/README.md`
- `docs/09-drafting-provenance/README.md`
