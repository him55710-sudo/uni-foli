# NEIS PDF Pipeline

## Flow

1. Parse router inspects the input PDF for embedded-text density, image-heavy pages, and table-heavy signals.
2. Raw extraction runs through OpenDataLoader when available.
3. If OpenDataLoader is unavailable, fails, or returns an empty payload, the pipeline falls back to `pdfplumber`.
4. The normalizer converts raw extraction output into a JSON-first internal artifact with pages, elements, tables, cells, bounding boxes, and table links.
5. The NEIS context stitcher merges table continuations across page breaks using:
   - `previous_table_id` / `next_table_id`
   - repeated headers and year/semester/subject heuristics
   - row span / column span structure correction
6. The semantic mapper converts stitched tables into:
   - `NeisDocument`
   - `NeisSection`
   - `NeisCourseRecord`
   - `NeisActivityRecord`
   - `NeisParseTrace`
7. Downstream artifacts are stored separately:
   - `raw_parse_artifact`: local raw extraction with original text
   - `student_artifact_parse`: masked analysis-ready artifact for diagnosis, blueprint, and workshop
   - `chunk_evidence_map`: evidence references for retrieval and citations

## Routing Policy

`heuristic`:
- default for digital-born PDFs with high embedded-text density
- preferred when the document is not image-heavy and table complexity is moderate

`hybrid`:
- used for scanned/image-heavy PDFs
- used for mixed PDFs where tables and OCR signals are both present
- safer for Korean/English mixed pages and page-spanning NEIS tables

Fallback:
- used when OpenDataLoader is not installed
- used when OpenDataLoader raises an error
- used when OpenDataLoader returns no parseable pages

## Stored Trace

The pipeline persists:

- parser route decision and inspection metrics
- raw extraction trace and fallback reason
- normalized element/table counts
- `table_chain_id`, `continuation_flag`, `page_span`
- parse, stitch, and semantic mapping confidence
- `needs_review`
- chunk-level evidence references

## Known Limitations

- OpenDataLoader integration is optional and best-effort because the dependency is not bundled in this repository.
- `pdfplumber` fallback cannot infer cross-page table links as reliably as OpenDataLoader.
- Header aliasing for NEIS tables is heuristic and may need expansion for school-specific templates.
- Text-only sections without stable tables are mapped conservatively and can still require manual review.
