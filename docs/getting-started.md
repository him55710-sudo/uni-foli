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
