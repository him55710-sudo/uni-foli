from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import html
import re
from zipfile import ZIP_DEFLATED, ZipFile

from polio_render.formats.base import BaseRenderer
from polio_render.markdown import markdown_lines_to_bullets, split_markdown_sections
from polio_render.models import RenderArtifact, RenderBuildContext
from polio_shared.paths import find_project_root


class HwpxRenderer(BaseRenderer):
    extension = ".hwpx"
    implementation_level = "template"

    def render(self, context: RenderBuildContext) -> RenderArtifact:
        output_path = self.prepare_output_path(context)
        message = self._render_hwpx(context, output_path)

        relative_path = str(output_path.relative_to(find_project_root()))
        return RenderArtifact(
            absolute_path=str(output_path),
            relative_path=relative_path,
            message=message,
        )

    def _render_hwpx(self, context: RenderBuildContext, output_path) -> str:
        template_path = self._get_template_path()
        preview_text = self._build_preview_text(context)

        with ZipFile(template_path, "r") as source_archive, ZipFile(
            output_path,
            "w",
            compression=ZIP_DEFLATED,
        ) as target_archive:
            for entry in source_archive.infolist():
                payload = source_archive.read(entry.filename)

                if entry.filename == "Contents/section0.xml":
                    payload = self._build_section_xml(payload.decode("utf-8"), context).encode("utf-8")
                elif entry.filename == "Contents/content.hpf":
                    payload = self._build_content_package(payload.decode("utf-8"), context).encode("utf-8")
                elif entry.filename == "Preview/PrvText.txt":
                    payload = preview_text.encode("utf-8")

                target_archive.writestr(entry, payload)

        return "HWPX document created from the bundled skeleton template."

    @staticmethod
    def _get_template_path() -> Path:
        return find_project_root() / "services" / "render" / "templates" / "hwpx-skeleton.hwpx"

    def _build_preview_text(self, context: RenderBuildContext) -> str:
        return "\n".join(text for text, _ in self._build_paragraph_lines(context))

    def _build_section_xml(self, template_xml: str, context: RenderBuildContext) -> str:
        lines = self._build_paragraph_lines(context)
        if not lines:
            lines = [("Empty draft.", False)]

        first_line = self._escape_xml(lines[0][0])
        xml = template_xml.replace(
            '<hp:run charPrIDRef="0"><hp:t/></hp:run><hp:linesegarray>',
            f'<hp:run charPrIDRef="0"><hp:t>{first_line}</hp:t></hp:run><hp:linesegarray>',
            1,
        )

        additional_paragraphs = "".join(
            self._build_additional_paragraph(line, 3121190100 + index, page_break=page_break)
            for index, (line, page_break) in enumerate(lines[1:], start=1)
        )
        insert_at = xml.rfind("</hs:sec>")
        return xml[:insert_at] + additional_paragraphs + xml[insert_at:]

    def _build_content_package(self, template_xml: str, context: RenderBuildContext) -> str:
        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        escaped_title = self._escape_xml(context.draft_title)
        escaped_creator = self._escape_xml(context.requested_by or "polio backend")

        xml = template_xml.replace("<opf:title/>", f"<opf:title>{escaped_title}</opf:title>", 1)
        xml = re.sub(
            r'(<opf:meta name="creator" content="text">)(.*?)(</opf:meta>)',
            rf"\1{escaped_creator}\3",
            xml,
            count=1,
        )
        xml = re.sub(
            r'(<opf:meta name="lastsaveby" content="text">)(.*?)(</opf:meta>)',
            rf"\1{escaped_creator}\3",
            xml,
            count=1,
        )
        xml = re.sub(
            r'(<opf:meta name="CreatedDate" content="text">)(.*?)(</opf:meta>)',
            rf"\1{now}\3",
            xml,
            count=1,
        )
        xml = re.sub(
            r'(<opf:meta name="ModifiedDate" content="text">)(.*?)(</opf:meta>)',
            rf"\1{now}\3",
            xml,
            count=1,
        )
        return xml

    def _build_paragraph_lines(self, context: RenderBuildContext) -> list[tuple[str, bool]]:
        lines: list[tuple[str, bool]] = [
            (context.project_title, False),
            (context.draft_title, False),
            (f"Requested by: {context.requested_by or 'anonymous'}", False),
            ("", False),
        ]

        for section_title, section_lines in split_markdown_sections(context.content_markdown):
            if section_title:
                lines.append((section_title, False))
            bullets = markdown_lines_to_bullets(section_lines, max_items=5) or ["No content provided."]
            lines.extend((bullet, False) for bullet in bullets)
            lines.append(("", False))

        appendix_lines = self._build_authenticity_appendix(context)
        if appendix_lines:
            lines.extend(appendix_lines)

        normalized = [(line.strip(), page_break) for line, page_break in lines]
        trimmed = [(line, page_break) for line, page_break in normalized if line]
        return trimmed[:40]

    def _build_authenticity_appendix(self, context: RenderBuildContext) -> list[tuple[str, bool]]:
        log_lines = [line.strip() for line in context.authenticity_log_lines if line.strip()]
        appendix_lines: list[tuple[str, bool]] = [
            ("부록: Poli Research Log", True),
            (
                "본 문서는 AI의 단순 생성이 아닌, 학생이 직접 KCI 논문을 탐색하고 시뮬레이션을 수행한 결과물임을 증명합니다.",
                False,
            ),
        ]

        if not log_lines:
            appendix_lines.append(("아직 저장된 핵심 디스커션 프롬프트가 없습니다. 워크숍 대화를 2~3회 이상 진행하면 이 영역이 채워집니다.", False))
            return appendix_lines

        for index, prompt in enumerate(log_lines[-3:], start=1):
            appendix_lines.append((f"핵심 디스커션 {index}: {prompt}", False))

        return appendix_lines

    def _build_additional_paragraph(self, text: str, paragraph_id: int, *, page_break: bool = False) -> str:
        escaped = self._escape_xml(text)
        return (
            f'<hp:p id="{paragraph_id}" paraPrIDRef="0" styleIDRef="0" pageBreak="{"1" if page_break else "0"}" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t>{escaped}</hp:t></hp:run>'
            '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" '
            'baseline="850" spacing="600" horzpos="0" horzsize="42520" flags="393216"/></hp:linesegarray>'
            "</hp:p>"
        )

    @staticmethod
    def _escape_xml(value: str) -> str:
        return html.escape(value, quote=False)
