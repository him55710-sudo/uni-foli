# API Service

Public HTTP entrypoint.

## Owns

- auth-facing routes
- upload session creation
- diagnosis request submission
- chat session APIs
- draft CRUD
- export request APIs

## Should stay thin

This service should validate requests, enforce authorization, and orchestrate calls.
Heavy parsing, retrieval indexing, and rendering should run in background workers.
