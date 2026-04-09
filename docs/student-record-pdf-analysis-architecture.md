# Student-Record PDF Analysis Architecture

This document defines the backbone extraction model for Korean student-record PDFs used by diagnosis, workshop copilot, and premium report generation.

## Pipeline Stages
1. `file_validation` (deterministic): confirm PDF shape and base metadata.
2. `raw_text_ocr_extraction` (deterministic): collect page text from parser artifacts.
3. `masking_privacy_pass` (deterministic): verify masked artifacts/status before downstream use.
4. `page_normalization` (deterministic): normalize whitespace and page snippets.
5. `section_classification` (heuristic): classify pages into core student-record sections using keyword/coverage rules.
6. `entity_extraction` (heuristic): extract timeline, subject, activity, and alignment signals.
7. `canonical_student_record_schema_generation` (deterministic): emit stable `student_record_canonical` payload.
8. `evidence_span_linking` (deterministic): attach page-level evidence spans to each extracted item.
9. `uncertainty_confidence_scoring` (heuristic): compute `document_confidence` and explicit uncertainty notes.

## Deterministic vs Heuristic
- Deterministic extraction means directly observable facts from parsed pages (page numbers, exact keyword spans, parser/masking status).
- Heuristic inference means bounded interpretation from observed text patterns (section density, major-alignment hints, confidence aggregation).
- Heuristic outputs must never invent activities, awards, or achievements.

## Uncertainty Contract
- If confidence is low or coverage is weak, the system records uncertainty instead of guessing.
- Missing or weak sections are represented explicitly in `weak_or_missing_sections`.
- Every extracted item must include page-level evidence; if evidence cannot be linked, the item is downgraded to an uncertainty note.

## Compatibility
- `student_record_canonical` is the new source of truth.
- `student_record_structure` is still produced for backward compatibility and is now bridged from canonical data when available.
