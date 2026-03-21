# Deletion Behavior Draft

## Model

- `deletion_requests`
- `deletion_events`

## Supported Targets

- `student_file`
- `analysis_run`

## Current Behavior

### Soft delete

- Marks target `deleted_at`
- Marks related artifacts `deleted_at`
- Marks tenant-bound citations and policy flags `deleted_at`
- Marks related response traces `deleted_at` when tied to an analysis run
- Marks privacy scans `deleted_at` for student file deletion

### Hard delete

- Performs all soft-delete behavior first
- Attempts local object removal only when the file object has no active references
- Falls back to soft delete for the file object if references still exist

## Audit Rule

- deletion requests and deletion events are preserved
- audit records must not contain raw student text

## TODO

- scheduled purge queue
- MinIO/S3 object deletion path
- reviewer approval requirement for hard delete in shared environments
