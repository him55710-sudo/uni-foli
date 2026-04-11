from __future__ import annotations

from pathlib import Path


WORKSHOP_ROUTE_PATH = Path("backend/services/api/src/unifoli_api/api/routes/workshops.py")
RUNTIME_SERVICE_PATH = Path("backend/services/api/src/unifoli_api/services/diagnosis_runtime_service.py")
PDF_RENDERER_PATH = Path("backend/services/render/src/unifoli_render/diagnosis_report_pdf_renderer.py")


def test_workshop_route_korean_messages_and_no_mojibake() -> None:
    source = WORKSHOP_ROUTE_PATH.read_text(encoding="utf-8")
    assert "어떤 방식으로 시작할지 고르면, 상황에 맞는 안전한 워크숍 흐름으로 이어집니다." in source
    assert "워크숍 레벨 설정을 반영했습니다." in source
    assert "현재 맥락 점수 기준으로는 아직 초안 생성에 필요한 정보가 부족합니다." in source
    assert "?대뼡" not in source
    assert "?쒓컖" not in source


def test_diagnosis_runtime_korean_messages_and_no_legacy_english() -> None:
    source = RUNTIME_SERVICE_PATH.read_text(encoding="utf-8")
    assert "진단 실행 전에 파싱이 완료된 문서를 먼저 업로드해 주세요." in source
    assert "파싱된 문서 내용이 비어 있습니다." in source
    assert "업로드한 문서 근거를 점검하고 있습니다..." in source
    assert "진단이 완료되었습니다." in source
    assert "진단 실행이 실패했습니다." in source
    assert "General Studies" not in source
    assert "Diagnosis storage is temporarily busy." not in source


def test_pdf_renderer_uses_korean_verification_label() -> None:
    source = PDF_RENDERER_PATH.read_text(encoding="utf-8")
    assert "추가 확인 필요" in source
    assert "異붽" not in source

