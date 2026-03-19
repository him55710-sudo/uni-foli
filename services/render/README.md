# Render Service

Dedicated export runtime.

## Owns

- PDF generation
- PPTX generation
- HWPX generation from a bundled skeleton template
- artifact storage handoff

## Reason to separate

Rendering has different dependencies and failure modes than the core API.

## Current implementations

- `pdf`: ReportLab
- `pptx`: python-pptx
- `hwpx`: template fill over `services/render/templates/hwpx-skeleton.hwpx`
