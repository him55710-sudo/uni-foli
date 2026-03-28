# Ingest Service

Normalization pipeline for user uploads and source materials.

## Owns

- parser selection
- upload normalization
- metadata extraction
- chunking
- document-to-draft handoff
- chunk embedding generation
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

## Current PDF path

The grounded-answer MVP currently uses a PyMuPDF-backed PDF path for project uploads.
It stores page-backed extraction metadata, chunk evidence maps, and masked artifacts for retrieval.

## NEIS PDF reference path

See `NEIS_PDF_PIPELINE.md` for the OpenDataLoader routing policy, normalized JSON artifact, page-stitching trace, and known limitations.
