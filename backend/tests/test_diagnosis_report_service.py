from __future__ import annotations

from pathlib import Path


REPORT_SERVICE_PATH = Path("backend/services/api/src/unifoli_api/services/diagnosis_report_service.py")
PDF_RENDERER_PATH = Path("backend/services/render/src/unifoli_render/diagnosis_report_pdf_renderer.py")


def test_section_title_map_is_korean_first() -> None:
    source = REPORT_SERVICE_PATH.read_text(encoding="utf-8")
    assert '"executive_summary": "핵심 요약"' in source
    assert '"record_baseline_dashboard": "학업·기록 베이스라인 대시보드"' in source
    assert '"interview_questions": "면접 예상 질문"' in source
    assert "Executive Summary" not in source


def test_report_fallback_copy_is_korean() -> None:
    source = REPORT_SERVICE_PATH.read_text(encoding="utf-8")
    assert "진단 보고서 생성에 실패했습니다." in source
    assert "추가 확인 필요" in source
    assert "합격 보장" in source


def test_pdf_renderer_has_no_padding_page_logic() -> None:
    source = PDF_RENDERER_PATH.read_text(encoding="utf-8")
    assert "filler_pages" not in source
    assert "품질 메모" not in source
    assert "내부 고정 템플릿" in source

