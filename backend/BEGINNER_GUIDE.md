# Beginner Guide

If you have never run a Python backend before, use this file first.

## 1. Install Python packages

```powershell
cd C:\Users\oupri\OneDrive\문서\Playground\polio-backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .[dev]
```

You can also run:

```powershell
.\scripts\setup-local.cmd
```

## 2. Choose your database mode

### Easiest: SQLite

`.\scripts\setup-local.cmd` uses SQLite by default, so you can skip extra env setup.

This stores everything in:

- `storage/runtime/polio.db`

### Recommended: PostgreSQL + pgvector

```powershell
.\scripts\setup-local.cmd postgres
.\scripts\start-infra.cmd
.\scripts\migrate.cmd
```

This path needs Docker installed on your computer.

## 3. Start the API

```powershell
.\scripts\start-api.cmd
```

Then open:

`http://127.0.0.1:8000/docs`

## 4. Create data in order

1. Create a project
2. Upload a file into that project
3. Let the backend auto-parse the uploaded `pdf`, `txt`, or `md`
4. Open the parsed document list
5. Create a draft from that parsed document
6. Create a render job and choose `pdf`, `pptx`, or `hwpx`
7. Process the render job either from the API dev endpoint or the worker

## 5. Start the worker

```powershell
.\scripts\start-worker.cmd
```

The worker processes queued render jobs and saves files into:

- `storage/exports/<project-id>/<job-id>/`

## 6. What gets saved where

- uploaded files: `storage/uploads/`
- generated exports: `storage/exports/`
- SQLite DB: `storage/runtime/`
- temp work files: `tmp/`

## 7. If something feels confusing

Use the routes in this order:

1. `POST /api/v1/projects`
2. `POST /api/v1/projects/{project_id}/uploads`
3. `GET /api/v1/projects/{project_id}/documents`
4. `POST /api/v1/projects/{project_id}/documents/{document_id}/drafts`
5. `POST /api/v1/render-jobs`
6. `POST /api/v1/render-jobs/{job_id}/process`
