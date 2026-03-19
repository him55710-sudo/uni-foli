"""
Future home for parsing, OCR, chunking, and vector ingestion.

This package is intentionally light in the first skeleton so the backend stays beginner-friendly.
"""
from polio_ingest.pdf_parser import SUPPORTED_EXTENSIONS, can_ingest_file, parse_uploaded_document

__all__ = ["SUPPORTED_EXTENSIONS", "can_ingest_file", "parse_uploaded_document"]
