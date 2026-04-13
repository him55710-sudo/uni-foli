# Beginner Guide

This guide is for the current monorepo layout.

## 1. Backend setup

SQLite mode:

```powershell
.\scripts\setup-local.cmd sqlite
```

PostgreSQL mode:

```powershell
.\scripts\setup-local.cmd postgres
.\scripts\start-infra.cmd
.\scripts\migrate.cmd
```

## 2. Start the backend

```powershell
.\scripts\start-api.cmd
```

Then open `http://127.0.0.1:8000/docs`.

If PowerShell blocks `.ps1` execution on Windows, use the `.cmd` wrappers in `scripts/`.

## 3. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

## 3.1 Local Ollama/Gemma setup (guided chat test)

```powershell
ollama serve
ollama pull gemma4
ollama list
```

Set backend envs in `.env`:

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

Notes:
- In local mode, if `GEMINI_API_KEY` is empty, backend automatically falls back to Ollama.
- In production mode, missing Gemini key is still treated as an error unless provider is explicitly configured.
- In production with `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL` must be a remote reachable endpoint (not localhost).

## 3.2 Gemini free-tier deployment setup

Backend env:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=<SET_IN_BACKEND_ENV_ONLY>
```

Frontend env:

```dotenv
VITE_API_URL=<YOUR_BACKEND_URL>
```

- Keep `GEMINI_API_KEY` backend-only.
- Do not put Gemini keys into `frontend/.env`.
- `VITE_API_URL` must point to backend origin so chat stream gets `text/event-stream` responses.

## 4. Recommended first workflow

1. Create a project.
2. Upload a real student-owned file.
3. Run diagnosis.
4. Review gaps and next actions.
5. Draft only from grounded evidence.
6. Export when the student has reviewed the result.

### Workshop guided-chat test flow

1. Open `/app/workshop` (or `/app/workshop/:projectId`).
2. First guided prompt should ask for the subject (for example: `어떤 과목의 탐구보고서를 준비하고 계신가요?`).
3. Enter a broad subject (example: `수학`).
4. Verify the specific-topic check appears (`주제가 있어요` / `추천 3개 받아보기`).
5. Request recommendations and confirm exactly 3 topic suggestion cards are shown.
6. Click topic -> page range -> structure and confirm next-action chips appear.
- right draft panel is filled with starter markdown

### PDF analysis model split

- Chatbot LLM uses `OLLAMA_MODEL`.
- PDF upload page/content analysis LLM uses `PDF_ANALYSIS_OLLAMA_MODEL`.
- You can set different model names for each role without changing route code.

If diagnosis/PDF evidence is missing, the flow should still work in limited mode and explicitly mention limited context.

## 5. Safety reminder

If the system lacks enough evidence, the correct behavior is to stop guessing and ask for
better input or suggest the next action.
