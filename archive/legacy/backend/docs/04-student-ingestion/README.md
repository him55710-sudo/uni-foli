# 04 Student Ingestion

This is the pipeline for student-owned uploads such as records, report drafts, and supporting files.

## Pipeline

1. upload asset
2. malware and MIME validation
3. parser selection
4. text and structure extraction
5. PII scan and masking index
6. human-verification surface for low-confidence fields
7. attach normalized output to student workspace

## Design rules

- keep the original file immutable
- create a normalized representation for all downstream features
- keep parser confidence and extraction warnings
- never trust OCR silently

## Parser strategy

- use Docling as the default parser
- extract text, headings, tables, lists, and image blocks
- store page or block coordinates when available for later review UX

## PII strategy

- run Presidio after extraction
- separate raw text from masked text
- use masked text for retrieval by default
- require privileged scope to access raw text

## Required outputs

- extracted plain text
- block-structured JSON
- parser confidence summary
- PII entity map
- verification checklist

## Failure handling

- if parser confidence is low, queue review instead of fake certainty
- if OCR fails, degrade to manual guidance mode
- if document format is unsupported, preserve the upload and explain next steps
