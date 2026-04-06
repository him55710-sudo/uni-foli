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
PDF_ANALYSIS_LLM_ENABLED=true
PDF_ANALYSIS_LLM_PROVIDER=ollama
PDF_ANALYSIS_OLLAMA_MODEL=gemma4
PDF_ANALYSIS_TIMEOUT_SECONDS=60
```

Notes:
- In local mode, if `GEMINI_API_KEY` is empty, backend automatically falls back to Ollama.
- In production mode, missing Gemini key is still treated as an error unless provider is explicitly configured.

## 4. Recommended first workflow

1. Create a project.
2. Upload a real student-owned file.
3. Run diagnosis.
4. Review gaps and next actions.
5. Draft only from grounded evidence.
6. Export when the student has reviewed the result.

### Workshop guided-chat test flow

1. Open `/app/workshop` (or `/app/workshop/:projectId`).
2. First greeting must be exactly: `안녕하세요. 어떤 주제의 보고서를 써볼까요?`
3. Enter a broad subject (example: `수학`).
4. Verify exactly 3 topic suggestions are shown inside the same Foli chat.
5. Click one suggestion and confirm:
- page range options are shown
- recommended outline is shown
- right draft panel is filled with starter markdown

### PDF analysis model split

- Chatbot LLM uses `OLLAMA_MODEL`.
- PDF upload page/content analysis LLM uses `PDF_ANALYSIS_OLLAMA_MODEL`.
- You can set different model names for each role without changing route code.

If diagnosis/PDF evidence is missing, the flow should still work in limited mode and explicitly mention limited context.

## 5. Safety reminder

If the system lacks enough evidence, the correct behavior is to stop guessing and ask for
better input or suggest the next action.
