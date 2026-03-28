# Worker Service

Async execution layer.

## Owns

- diagnosis jobs
- retrieval enrichment
- scheduled source refresh
- reminder dispatch
- cleanup and retention jobs
- render jobs
- global document parse jobs
- external research ingestion jobs

## Design note

If a task can take seconds to minutes, it belongs here, not in the API service.

## Runtime model

- Jobs are persisted in `async_jobs`.
- Statuses are `queued`, `running`, `retrying`, `succeeded`, and `failed`.
- When retries are exhausted, the job remains visible with `dead_lettered_at` populated.
- The API exposes job state at `/api/v1/jobs/{job_id}` and allows safe manual retry or inline processing when enabled in local settings.
