# Beginner Guide

This guide is for the current monorepo layout.

## 1. Backend setup

SQLite mode:

```powershell
.\scripts\setup-local.ps1 sqlite
```

PostgreSQL mode:

```powershell
.\scripts\setup-local.ps1 postgres
.\scripts\start-infra.ps1
.\scripts\migrate.ps1
```

## 2. Start the backend

```powershell
.\scripts\start-api.ps1
```

Then open `http://127.0.0.1:8000/docs`.

## 3. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

## 4. Recommended first workflow

1. Create a project.
2. Upload a real student-owned file.
3. Run diagnosis.
4. Review gaps and next actions.
5. Draft only from grounded evidence.
6. Export when the student has reviewed the result.

## 5. Safety reminder

If the system lacks enough evidence, the correct behavior is to stop guessing and ask for
better input or suggest the next action.
