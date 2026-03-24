# Architecture Overview

## Deployment stance

Start as a modular monolith:

- one repository
- one primary database
- one queue/cache layer
- multiple runtime processes only where dependencies differ

This gives enough separation without forcing distributed-systems complexity too early.

## Runtime components

### Client apps

- web app
- future mobile app

### API service

- authentication-aware request handling
- thin orchestration
- draft and diagnosis APIs

### Worker service

- async analysis
- scheduled refresh jobs
- reminder jobs

### Ingest service

- document parsing
- source normalization
- chunking and embeddings

### Render service

- PDF generation
- PPTX generation
- future HWPX projection

## Shared state

### PostgreSQL

- users
- consents
- target plans
- drafts
- revisions
- source documents
- source chunks
- diagnosis reports
- audit events

### Object storage

- raw uploads
- parsed artifacts
- export artifacts

### Valkey

- queue broker
- transient runtime state
- rate limits

## Request flows

### Student upload flow

1. client requests upload session from API
2. file stored in object storage
3. worker triggers ingest service
4. ingest parses file, masks PII, stores normalized outputs
5. API exposes verification-ready document state

### Diagnosis flow

1. student submits target plan and document set
2. worker retrieves ranked evidence
3. diagnosis engine computes fit, gaps, and next actions
4. result stored as `DiagnosisReport`
5. API returns explanation with citations

### Chat flow

1. chat request enters API
2. API resolves user and workspace context
3. orchestration fetches evidence, draft state, and diagnosis state
4. LiteLLM routes to chosen model
5. answer and tool traces are logged
6. optional draft changes are stored with provenance

### Export flow

1. client requests export
2. API creates `ExportJob`
3. render service pulls canonical draft
4. artifact rendered and stored
5. signed download delivered back to client

## Data ownership rules

- raw student files belong to object storage, never to prompt logs
- normalized text belongs to PostgreSQL, with raw/masked separation
- embeddings belong to PostgreSQL through pgvector
- prompts and traces belong to observability tooling, but sensitive payloads must be redacted

## The most important architectural decision

The canonical source of truth is the structured draft model in the database.
Not the chat transcript.
Not the PDF.
Not the PPTX.

That decision keeps editing, diagnosis, provenance, and export aligned.
