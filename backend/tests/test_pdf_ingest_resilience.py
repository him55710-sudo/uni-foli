from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from pypdf import PdfWriter

from unifoli_ingest.neis_pipeline import ParserProviderResult, extract_raw_pdf_artifact, inspect_pdf_route
from unifoli_ingest.pdf_parser import PDFParseFailure, parse_pdf_document


def _write_encrypted_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    with path.open("wb") as fh:
        writer.write(fh)


def _route(**overrides: object) -> dict[str, object]:
    route = {
        "document_kind": "scanned_or_image_heavy",
        "selected_strategy": "odl_hybrid",
        "parse_mode": "hybrid",
        "ocr_enabled": True,
        "confidence": 0.78,
        "reasons": ["image-heavy scan"],
        "metrics": {"page_count": 2, "image_heavy_pages": 2},
        "neis_extractpdf4j_enabled": True,
        "neis_extractpdf4j_base_url": "http://extractpdf4j.example.local",
        "neis_extractpdf4j_timeout_seconds": 1.5,
        "neis_dedoc_enabled": True,
        "neis_provider_min_quality_score": 0.58,
        "neis_merge_policy": "conservative_table",
    }
    route.update(overrides)
    return route


def _usable_provider_result(
    provider_name: str,
    *,
    confidence: float = 0.74,
    parse_mode: str = "fallback",
) -> ParserProviderResult:
    raw_artifact = {
        "schema_version": "unifoli.raw_pdf.v1",
        "source": provider_name,
        "parse_mode": parse_mode,
        "ocr_enabled": provider_name in {"opendataloader", "extractpdf4j"},
        "trace": {},
        "payload": {
            "pages": [
                {
                    "page_number": 1,
                    "elements": [
                        {
                            "element_id": "page-1-text-0",
                            "type": "text",
                            "text": "학년 1 학기 1 과목 수학 세부능력 및 특기사항 탐구 활동",
                        }
                    ],
                }
            ]
        },
    }
    return ParserProviderResult(
        provider_name=provider_name,
        provider_trace={},
        provider_confidence=confidence,
        normalized_pages=[{"page_number": 1, "element_ids": ["page-1-text-0"]}],
        normalized_elements=[
            {
                "element_id": "page-1-text-0",
                "page_number": 1,
                "element_index": 0,
                "element_type": "text",
                "bbox": None,
                "raw_text": "학년 1 학기 1 과목 수학 세부능력 및 특기사항 탐구 활동",
                "previous_table_id": None,
                "next_table_id": None,
                "table_id": None,
                "table_rows": [],
            }
        ],
        normalized_tables=[],
        warnings=[],
        needs_review=False,
        parse_mode=parse_mode,
        raw_artifact=raw_artifact,
    )


def _failed_provider_result(provider_name: str, warning: str, *, parse_mode: str = "hybrid") -> ParserProviderResult:
    return ParserProviderResult(
        provider_name=provider_name,
        provider_trace={},
        provider_confidence=0.0,
        normalized_pages=[],
        normalized_elements=[],
        normalized_tables=[],
        warnings=[warning],
        needs_review=True,
        parse_mode=parse_mode,
        raw_artifact={},
    )


def test_parse_pdf_document_rejects_malformed_pdf(tmp_path: Path) -> None:
    path = tmp_path / "malformed.pdf"
    path.write_bytes(b"not-a-real-pdf")

    with pytest.raises(PDFParseFailure) as excinfo:
        parse_pdf_document(
            path,
            chunk_size_chars=600,
            overlap_chars=80,
            neis_ensemble_enabled=False,
        )

    assert excinfo.value.code == "pdf_malformed"


def test_parse_pdf_document_rejects_encrypted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    _write_encrypted_pdf(path)

    with pytest.raises(PDFParseFailure) as excinfo:
        parse_pdf_document(
            path,
            chunk_size_chars=600,
            overlap_chars=80,
            neis_ensemble_enabled=False,
        )

    assert excinfo.value.code == "pdf_encrypted"


def test_parse_pdf_document_keeps_layout_blocks_without_extra_pipeline(tmp_path: Path) -> None:
    path = tmp_path / "layout.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((60, 80), "학생명 홍길동")
    page.insert_text((60, 120), "세부능력 및 특기사항 탐구 활동")
    doc.save(path)
    doc.close()

    parsed = parse_pdf_document(
        path,
        chunk_size_chars=600,
        overlap_chars=80,
        neis_ensemble_enabled=False,
    )

    raw_page = parsed.raw_artifact["pages"][0]
    assert raw_page["blocks"]
    assert raw_page["layout_profile"]["extraction_strategy"] == "blocks"
    assert parsed.analysis_artifact["layout_mode"] == "pymupdf_text_blocks"
    assert parsed.masked_artifact["pages"][0]["layout_profile"]["text_block_count"] >= 1


def test_inspect_pdf_route_marks_image_heavy_scans_for_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakePage:
        def __init__(self, text: str, *, image_count: int, line_count: int = 0) -> None:
            self._text = text
            self.images = [{} for _ in range(image_count)]
            self.lines = [{} for _ in range(line_count)]
            self.rects = []

        def extract_text(self, layout: bool = False) -> str:  # noqa: FBT001, ARG002
            return self._text

    class _FakePdf:
        def __init__(self) -> None:
            self.pages = [
                _FakePage("학년", image_count=1),
                _FakePage("세특", image_count=1),
            ]

        def __enter__(self) -> "_FakePdf":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

    monkeypatch.setattr("unifoli_ingest.neis_pipeline.pdfplumber.open", lambda _path: _FakePdf())

    route = inspect_pdf_route(Path("scan-heavy.pdf"))

    assert route["document_kind"] == "scanned_or_image_heavy"
    assert route["requested_strategy"] == "odl_hybrid"
    assert route["actual_strategy"] == "odl_hybrid"
    assert route["ocr_requested"] is True
    assert route["ocr_executed"] is False
    assert route["provider_attempts"] == []


def test_extract_raw_pdf_artifact_keeps_analysis_when_ocr_capable_providers_are_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%stub\n")

    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._provider_priority",
        lambda _route: ["opendataloader", "extractpdf4j", "dedoc", "pdfplumber"],
    )
    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._extract_odl_provider",
        lambda *args, **kwargs: _failed_provider_result("opendataloader", "OpenDataLoader is not installed."),
    )
    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._extract_extractpdf4j_provider",
        lambda *args, **kwargs: _failed_provider_result(
            "extractpdf4j",
            "ExtractPDF4J provider endpoint is not configured.",
        ),
    )
    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._extract_dedoc_provider",
        lambda *args, **kwargs: _failed_provider_result("dedoc", "Dedoc is not installed."),
    )
    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._extract_pdfplumber_provider",
        lambda *args, **kwargs: _usable_provider_result("pdfplumber", confidence=0.72),
    )

    raw_artifact, warnings, resolved_route = extract_raw_pdf_artifact(
        dummy_pdf,
        route=_route(),
        odl_enabled=False,
    )

    assert raw_artifact["source"] == "pdfplumber"
    assert resolved_route["provider_selected"] == "pdfplumber"
    assert resolved_route["ocr_requested"] is True
    assert resolved_route["ocr_executed"] is False
    assert resolved_route["degraded_reason"] is not None
    assert any("OpenDataLoader is not installed." in warning for warning in warnings)


def test_extract_raw_pdf_artifact_records_extractpdf4j_timeout_and_falls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy_pdf = tmp_path / "timeout.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%timeout\n")

    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._provider_priority",
        lambda _route: ["extractpdf4j", "pdfplumber"],
    )
    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._extract_extractpdf4j_provider",
        lambda *args, **kwargs: _failed_provider_result(
            "extractpdf4j",
            "ExtractPDF4J sidecar unavailable: ReadTimeout",
        ),
    )
    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._extract_pdfplumber_provider",
        lambda *args, **kwargs: _usable_provider_result("pdfplumber", confidence=0.76),
    )

    raw_artifact, _warnings, resolved_route = extract_raw_pdf_artifact(
        dummy_pdf,
        route=_route(),
        odl_enabled=False,
    )

    attempts = raw_artifact["trace"]["provider_selection"]["provider_attempts"]
    assert resolved_route["provider_selected"] == "pdfplumber"
    assert attempts[0]["provider"] == "extractpdf4j"
    assert any("ReadTimeout" in warning for warning in attempts[0]["warnings"])
    assert resolved_route["degraded_reason"] == "preferred_provider_failed:extractpdf4j"


def test_extract_raw_pdf_artifact_records_dedoc_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy_pdf = tmp_path / "dedoc.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%dedoc\n")

    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._provider_priority",
        lambda _route: ["dedoc", "pdfplumber"],
    )
    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._extract_dedoc_provider",
        lambda *args, **kwargs: _failed_provider_result("dedoc", "Dedoc is not installed."),
    )
    monkeypatch.setattr(
        "unifoli_ingest.neis_pipeline._extract_pdfplumber_provider",
        lambda *args, **kwargs: _usable_provider_result("pdfplumber", confidence=0.79),
    )

    raw_artifact, _warnings, resolved_route = extract_raw_pdf_artifact(
        dummy_pdf,
        route=_route(),
        odl_enabled=False,
    )

    attempts = raw_artifact["trace"]["provider_selection"]["provider_attempts"]
    assert resolved_route["provider_selected"] == "pdfplumber"
    assert attempts[0]["provider"] == "dedoc"
    assert attempts[0]["success"] is False
    assert attempts[0]["warnings"] == ["Dedoc is not installed."]
