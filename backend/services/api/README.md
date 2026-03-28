# API Service

Public HTTP entrypoint.

## Owns

- auth-facing routes
- upload session creation
- diagnosis request submission
- grounded-answer request handling
- chat session APIs
- draft CRUD
- export request APIs

## Should stay thin

This service should validate requests, enforce authorization, and orchestrate calls.
Heavy parsing, retrieval indexing, and rendering should run in background workers.

## Grounded-answer MVP

The current MVP exposes a project-level grounded-answer route that returns evidence-backed excerpts,
provenance, and a refusal plus next safe action when the record is too weak to support the claim.
