# Masking Modes Draft

## Modes

- `off`
  - no detection
  - no masking
- `detect_only`
  - detect and record scan metadata
  - keep stored analysis/index text unchanged
- `mask_for_index`
  - detect and mask text that is stored for search and analysis paths
  - preserve masked preview and scan metadata for admin inspection
- `mask_all`
  - detect and mask all stored downstream text views intended for product runtime

## Runtime Path

1. Student upload is parsed into blocks.
2. Each block passes through privacy scan.
3. Scan writes a `privacy_scans` row.
4. Student artifact stores masked or unmasked `cleaned_text` depending on tenant mode.

## Engines

- preferred: Presidio helper subprocess
- fallback: regex masking for phone, email, and Korean resident registration number

## Important Limitation

- raw block text is still stored internally in `student_artifacts.raw_text` for controlled internal alpha use.
- broader rollout should add stronger encryption or separated secure storage for raw payloads.
