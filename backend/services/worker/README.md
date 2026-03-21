# Worker Service

Async execution layer.

## Owns

- diagnosis jobs
- retrieval enrichment
- scheduled source refresh
- reminder dispatch
- cleanup and retention jobs

## Design note

If a task can take seconds to minutes, it belongs here, not in the API service.
