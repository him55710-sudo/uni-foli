from __future__ import annotations

import xml.etree.ElementTree as ET
from zipfile import ZipFile

from unifoli_domain.enums import RenderFormat
from unifoli_render.formats.hwpx_renderer import HwpxRenderer
from unifoli_render.models import RenderBuildContext
from unifoli_render.template_registry import RenderExportPolicy


def test_hwpx_renderer_builds_evidence_highlight_tables(tmp_path) -> None:
    output_path = tmp_path / "evidence-highlight.hwpx"
    context = RenderBuildContext(
        project_id="project-1",
        project_title="생기부 진단",
        draft_id="draft-1",
        draft_title="HWPX 하이라이트",
        render_format=RenderFormat.HWPX,
        content_markdown="## 요약\n\n학생 탐구 내용을 정리합니다.",
        requested_by="tester",
        job_id="job-1",
        evidence_map={
            "센서 오차 비교": {
                "원문": "로봇 센서 오차를 비교하고 보정 방법의 한계를 기록함",
                "입학사정관 코멘트": "과정에서 본인 역할과 한계 인식이 확인되는 근거입니다.",
                "학생 탐구 내용": "센서 조건을 바꿔 오차를 비교함",
                "source_label": "학생부",
                "page_number": 2,
            }
        },
        export_policy=RenderExportPolicy(include_provenance_appendix=True),
    )

    artifact = HwpxRenderer().render(context, output_path)

    assert artifact.absolute_path == str(output_path)
    with ZipFile(output_path) as archive:
        section_xml = archive.read("Contents/section0.xml").decode("utf-8")
        preview_text = archive.read("Preview/PrvText.txt").decode("utf-8")

    ET.fromstring(section_xml)
    assert "<hp:tbl" in section_xml
    assert "입학사정관 코멘트" in section_xml
    assert "학생 탐구 내용" in section_xml
    assert "[출처: 생기부 p.2]" in section_xml
    assert "로봇 센서 오차를 비교하고" in section_xml
    assert "[출처: 생기부 p.2]" in preview_text
