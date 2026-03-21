# Ingest Service

Normalization pipeline for user uploads and source materials.

## Owns

- parser selection
- upload normalization
- metadata extraction
- chunking
- document-to-draft handoff
- future embedding requests
- future source indexing

## Current supported uploads

- `.pdf`
- `.txt`
- `.md`

## Current output tables

- `parsed_documents`
- `document_chunks`

## Special concern

Everything here must preserve provenance and parser confidence.
