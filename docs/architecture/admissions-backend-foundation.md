# Admissions Backend Foundation

## Design Intent

This backend is built around one rule:

`teach interpretation of authentic admissions evidence, not fabrication of desirable records`

## Major Domains

- source ingestion
- document parsing
- normalization
- claim extraction
- provenance and citations
- hybrid retrieval
- student-file analysis
- safety and auditability

## Storage Pattern

- PostgreSQL for operational records
- pgvector for embedding storage
- Redis for queue coordination
- S3-compatible object storage for files
- local filesystem fallback for dev uploads

## Traceability Contract

Every meaningful record should preserve:

- timestamps
- status
- source tier
- file hash
- parser metadata
- evidence pointer
- model or prompt metadata when AI is used
