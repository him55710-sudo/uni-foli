# Uni Foli Monorepo

Uni Foli is an execution-oriented AI platform for students.

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
- `codex-backend/uni-foli-codex-uni-foli-backend-bootstrap/`: not present in this checkout
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
- `prompts/`: managed root prompt asset registry consumed through backend loader scaffolding

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

### Inquiry Email Setup (Naver)

臾몄쓽 ?묒꽦 ???댁쁺??硫붿씪濡??뚮┝??諛쏆쑝?ㅻ㈃ ?꾨옒 ?섍꼍 蹂?섎? 諛섎뱶???ㅼ젙?섏꽭??

```dotenv
SMTP_ENABLED=true
SMTP_SERVER=smtp.naver.com
SMTP_PORT=587
SMTP_USERNAME=<諛쒖떊 Naver 硫붿씪 二쇱냼>
SMTP_PASSWORD=<??鍮꾨?踰덊샇 ?먮뒗 SMTP 鍮꾨?踰덊샇>
SMTP_RECEIVER_EMAIL=mongben@naver.com
```

?숈옉 泥댄겕:
- 臾몄쓽 API??DB ?????鍮꾨룞湲곕줈 硫붿씪???꾩넚?⑸땲??
- SMTP ?ㅼ젙??鍮꾩뼱 ?덉쑝硫?硫붿씪 ?꾩넚??嫄대꼫?곌퀬 ?쒕쾭 濡쒓렇???댁쑀瑜??④퉩?덈떎.
- ?섏떊??`SMTP_RECEIVER_EMAIL`)媛 鍮꾩뼱 ?덉쑝硫?`SMTP_USERNAME`???섏떊?먮줈 fallback ?⑸땲??

### Local Ollama/Gemma Guided-Chat Test

1. Start Ollama locally:

```powershell
ollama serve
```

2. Ensure the local model exists:

```powershell
ollama pull gemma4
ollama list
```

3. Set local backend envs (`.env` from `.env.example`):

```dotenv
APP_ENV=local
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=gemma4
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_PREDICT=768
OLLAMA_TIMEOUT_SECONDS=120
OLLAMA_FAST_MODEL=
OLLAMA_STANDARD_MODEL=
OLLAMA_RENDER_MODEL=
OLLAMA_FAST_TIMEOUT_SECONDS=45
OLLAMA_STANDARD_TIMEOUT_SECONDS=120
OLLAMA_RENDER_TIMEOUT_SECONDS=180
PDF_ANALYSIS_LLM_ENABLED=true
PDF_ANALYSIS_LLM_PROVIDER=ollama
PDF_ANALYSIS_OLLAMA_MODEL=gemma4
PDF_ANALYSIS_TIMEOUT_SECONDS=60
```

4. Local fallback rule:
- If `APP_ENV=local` and `GEMINI_API_KEY` is not configured, backend automatically falls back to Ollama.
- Production does not auto-force Ollama.
- In production with `LLM_PROVIDER=ollama`, set `OLLAMA_BASE_URL` to a remote reachable endpoint (not localhost).

### Gemini Free-Tier Deployment Env

Backend env (`.env` or deployment secret manager):

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=<SET_IN_BACKEND_ENV_ONLY>
```

Frontend env (`frontend/.env`):

```dotenv
VITE_API_URL=<YOUR_BACKEND_URL>
```

- Keep `GEMINI_API_KEY` backend-only. Never expose it in frontend env or browser code.
- `VITE_API_URL` must be the backend origin. If it points to the frontend origin, workshop chat stream returns HTML instead of SSE.

5. Guided chat API flow:
- `POST /api/v1/guided-chat/start`
- `POST /api/v1/guided-chat/topic-suggestions`
- `POST /api/v1/guided-chat/topic-selection`
- `POST /api/v1/guided-chat/page-range-selection`
- `POST /api/v1/guided-chat/structure-selection`

6. Workshop integrated flow:
- `/app/workshop` or `/app/workshop/:projectId`
- First guided message should ask for the subject in Korean (for example, `어떤 과목의 탐구보고서를 준비하고 계신가요?`).
- Enter a broad subject (for example, `수2`) and verify the specific-topic check appears.
- Request recommendations and verify 3 topic cards appear in the same Foli chat.
- Select topic -> page range -> structure through cards/chips, then continue freeform coauthoring.
If Ollama is unavailable, the guided chat route returns conservative fallback suggestions with a limited-context note instead of crashing.
If PDF analysis Ollama is unavailable, upload parsing still succeeds and falls back to a conservative local summary.

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
- Preserve Uni Foli safety rules over output polish.

## Key Docs

- `docs/getting-started.md`
- `docs/monorepo-structure.md`
- `docs/00-principles/README.md`
- `docs/07-diagnosis-engine/README.md`
- `docs/08-chat-orchestration/README.md`
- `docs/09-drafting-provenance/README.md`
- `docs/shared-contracts-v1.md`
- `docs/prompt-registry-v1.md`

