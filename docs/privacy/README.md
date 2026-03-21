# Privacy Baseline

This folder documents the internal-alpha privacy baseline for Polio student data.

Included docs:

- `retention-policy.md`
- `deletion-behavior.md`
- `masking-modes.md`
- `admin-access-rules.md`

Scope of this phase:

- account, role, and tenant baseline
- bearer-session auth for protected routes
- tenant-bound student file and analysis access
- deletion request and deletion event tracking
- ingestion-time PII masking hooks
- redacted structured logging

Known limitation:

- `scripts/presidio_masking_helper.py` is wired into the runtime path, but the helper should run in a compatible Python 3.12 or 3.13 environment if the local app environment cannot import Presidio cleanly.
