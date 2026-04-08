# diagnosis.student-record-structure-extraction

- Version: `1.0.0`
- Category: `diagnosis`
- Status: `registered`

## Purpose

Define the structure-extraction contract for Korean student-record PDFs so
diagnosis/report services can consume a stable evidence map.

## Input Contract

- Parsed page text snippets
- PDF analysis summary/key points/evidence gaps
- Optional advanced semantic parsing artifact

## Output Contract

A structure object with fields:

- `major_sections`
- `section_density`
- `timeline_signals`
- `activity_clusters`
- `subject_major_alignment_signals`
- `weak_sections`
- `continuity_signals`
- `process_reflection_signals`
- `uncertain_items`

## Prompt Body

Extract structure conservatively from student-record evidence.

Rules:

- Use only observable text signals.
- If confidence is low, add it to `uncertain_items` instead of asserting facts.
- Prefer section labels used in Korean student records.
- Keep each list concise and deduplicated.
- Do not infer admissions outcomes.
