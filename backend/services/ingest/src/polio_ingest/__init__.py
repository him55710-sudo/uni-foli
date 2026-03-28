"""
Future home for parsing, OCR, chunking, and vector ingestion.

This package is intentionally light in the first skeleton so the backend stays beginner-friendly.
"""
from polio_ingest.pdf_parser import SUPPORTED_EXTENSIONS, can_ingest_file, parse_uploaded_document
from polio_ingest.research_pipeline import ResearchPipelineError, normalize_research_source

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "ResearchPipelineError",
    "can_ingest_file",
    "normalize_research_source",
    "parse_uploaded_document",
]
