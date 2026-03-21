# Retention Policy Draft

## Current Baseline

- Tenant has `default_retention_days`.
- Student files inherit tenant retention on upload.
- Analysis runs inherit tenant retention when created.
- File objects linked to student uploads store `retention_expires_at` and `purge_after_at`.
- Response traces can store `retention_expires_at` when tenant-bound.

## Data Classes

- Student uploads:
  - `student_files`
  - `student_artifacts`
  - `privacy_scans`
  - `student_analysis_runs`
  - tenant-bound `citations`, `policy_flags`, `response_traces`
- Official corpus:
  - not covered by the same retention schedule
  - governed separately by source freshness and crawl policy

## Operational Rule

- Soft delete first.
- Hard delete is explicit and request-based.
- Deletion events remain for audit even after target records are removed.

## TODO

- legal-review-backed retention schedule by customer type
- scheduled purge worker
- archive tier for expired traces
