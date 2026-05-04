from __future__ import annotations

from datetime import UTC, datetime
import html
from pathlib import Path
import re
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from unifoli_render.formats.base import BaseRenderer
from unifoli_render.markdown import markdown_lines_to_bullets, split_markdown_sections
from unifoli_render.models import RenderArtifact, RenderBuildContext
from unifoli_render.template_registry import build_provenance_appendix_lines, humanize_provenance_source
from unifoli_shared.paths import find_project_root, to_stored_path


class HwpxRenderer(BaseRenderer):
    extension = ".hwpx"
    implementation_level = "template"

    def render(self, context: RenderBuildContext, output_path: str | Path) -> RenderArtifact:
        message = self._render_hwpx(context, output_path)

        relative_path = to_stored_path(output_path)
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
        lines = [text for text, _ in self._build_paragraph_lines(context)]
        lines.extend(self._build_evidence_preview_lines(context))
        return "\n".join(lines)

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
        evidence_tables = self._build_evidence_table_fragments(context, base_id=3121205000 + len(lines) * 20)
        insert_at = xml.rfind("</hs:sec>")
        return xml[:insert_at] + additional_paragraphs + evidence_tables + xml[insert_at:]

    def _build_content_package(self, template_xml: str, context: RenderBuildContext) -> str:
        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        escaped_title = self._escape_xml(context.draft_title)
        escaped_creator = self._escape_xml(context.requested_by or "unifoli backend")

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
        template = context.resolve_template()
        lines: list[tuple[str, bool]] = [
            (context.project_title, False),
            (context.draft_title, False),
            (template.label, False),
            (f"Requested by: {context.requested_by or 'anonymous'}", False),
            ("", False),
        ]

        for section_title, section_lines in split_markdown_sections(context.content_markdown):
            if section_title:
                lines.append((section_title, False))
            # Removing max_items=5 limit to support up to 2000 chars
            bullets = markdown_lines_to_bullets(section_lines, max_items=100) or ["No content provided."]
            lines.extend((bullet, False) for bullet in bullets)
            lines.append(("", False))

        appendix_lines = self._build_authenticity_appendix(context)
        if appendix_lines:
            lines.extend(appendix_lines)

        normalized = [(line.strip(), page_break) for line, page_break in lines]
        trimmed = [(line, page_break) for line, page_break in normalized if line]
        # Increase limit from 100 to 500 for complex reports
        return trimmed[:500]

    def _build_authenticity_appendix(self, context: RenderBuildContext) -> list[tuple[str, bool]]:
        template = context.resolve_template()
        policy = context.export_policy
        if not policy.include_provenance_appendix or not template.supports_provenance_appendix:
            return []

        appendix_lines: list[tuple[str, bool]] = [
            ("Provenance Appendix", True),
            ("This appendix keeps the export submission-friendly while preserving the evidence basis.", False),
        ]
        appendix_lines.extend(
            (line, False)
            for line in build_provenance_appendix_lines(
                evidence_map=context.evidence_map,
                authenticity_log_lines=context.authenticity_log_lines,
                hide_internal=policy.hide_internal_provenance_on_final_export,
                max_evidence_items=10,
                max_authenticity_notes=5,
            )
        )
        return appendix_lines

    def _build_evidence_preview_lines(self, context: RenderBuildContext) -> list[str]:
        items = self._extract_evidence_items(context)
        if not items:
            return []
        lines = ["", "세특 원문 하이라이트"]
        for item in items[:5]:
            lines.append(f"[출처: {item['source']}] {item['evidence']}")
        return lines

    def _build_evidence_table_fragments(self, context: RenderBuildContext, *, base_id: int) -> str:
        items = self._extract_evidence_items(context)
        if not items:
            return ""

        fragments: list[str] = []
        fragments.append(self._build_additional_paragraph("입학사정관 코멘트 / 학생 탐구 내용", base_id, page_break=True))
        consultant_rows = [["입학사정관 코멘트", "학생 탐구 내용"]]
        for item in items[:5]:
            consultant_rows.append(
                [
                    f"{item['claim']}\n{item['comment']}",
                    f"{item['student_content']}\n[출처: {item['source']}]",
                ]
            )
        fragments.append(
            self._build_table_block(
                consultant_rows,
                paragraph_id=base_id + 1,
                table_id=base_id + 2,
                col_widths=[20400, 22120],
            )
        )

        fragments.append(self._build_additional_paragraph("세특 원문 하이라이트", base_id + 200, page_break=False))
        for index, item in enumerate(items[:8]):
            fragments.append(
                self._build_table_block(
                    [
                        [f"[출처: {item['source']}]"],
                        [item["evidence"]],
                    ],
                    paragraph_id=base_id + 201 + index * 20,
                    table_id=base_id + 202 + index * 20,
                    col_widths=[42520],
                )
            )
        return "".join(fragments)

    def _extract_evidence_items(self, context: RenderBuildContext) -> list[dict[str, str]]:
        evidence_map = context.evidence_map if isinstance(context.evidence_map, dict) else {}
        items: list[dict[str, str]] = []
        for claim, support in evidence_map.items():
            if not isinstance(support, dict):
                continue
            if str(claim).startswith("_") or str(claim) in {"coauthoring", "structured_draft"}:
                continue
            evidence = self._first_text(
                support,
                "원문",
                "원문텍스트",
                "student_record_text",
                "student_record_excerpt",
                "excerpt",
                "quote",
                "근거",
                "evidence",
                "text",
            )
            if not evidence:
                continue
            source = self._source_label(support)
            comment = self._first_text(
                support,
                "입학사정관 코멘트",
                "admissions_comment",
                "consultant_comment",
                "comment",
                "rationale",
            )
            if not comment:
                comment = "이 원문은 활동의 실제 과정, 본인 역할, 전공 연결성을 확인하는 핵심 근거입니다."
            student_content = self._first_text(
                support,
                "학생 탐구 내용",
                "student_content",
                "activity",
                "claim",
                "summary",
            ) or evidence
            items.append(
                {
                    "claim": self._clip_plain(str(claim), 90),
                    "source": self._clip_plain(source, 80),
                    "evidence": self._clip_plain(evidence, 360),
                    "comment": self._clip_plain(comment, 220),
                    "student_content": self._clip_plain(student_content, 260),
                }
            )
        return items

    @staticmethod
    def _first_text(payload: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())
        return ""

    def _source_label(self, support: dict[str, Any]) -> str:
        source = self._first_text(support, "출처", "source", "source_label", "document_source")
        page = support.get("page_number") or support.get("page") or support.get("page_no")
        page_text = ""
        if isinstance(page, (int, float)) and int(page) > 0:
            page_text = str(int(page))
        elif isinstance(page, str):
            match = re.search(r"\d+", page)
            page_text = match.group(0) if match else ""
        if not page_text and source:
            match = re.search(r"(?:p\.?|page|페이지)\s*(\d+)", source, flags=re.IGNORECASE)
            page_text = match.group(1) if match else ""
        if page_text:
            return f"생기부 p.{page_text}"
        if source:
            return humanize_provenance_source(source, hide_internal=True)
        return "생기부 원문 근거"

    @staticmethod
    def _clip_plain(text: str, limit: int) -> str:
        normalized = " ".join(str(text or "").split()).strip()
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3].rstrip()}..."

    def _build_table_block(
        self,
        rows: list[list[str]],
        *,
        paragraph_id: int,
        table_id: int,
        col_widths: list[int],
    ) -> str:
        row_xml = []
        for row_index, row in enumerate(rows):
            row_xml.append(
                self._build_table_row(
                    row,
                    row_index=row_index,
                    paragraph_id=paragraph_id,
                    col_widths=col_widths,
                )
            )
        total_width = sum(col_widths)
        return (
            f'<hp:p id="{paragraph_id}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            '<hp:run charPrIDRef="0"><hp:ctrl>'
            f'<hp:tbl id="{table_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
            f'lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" rowCnt="{len(rows)}" colCnt="{len(col_widths)}" '
            'cellSpacing="0" borderFillIDRef="1" noAdjust="0">'
            f'<hp:sz width="{total_width}" widthRelTo="ABSOLUTE" height="{max(1800, len(rows) * 1600)}" heightRelTo="ABSOLUTE" protect="0"/>'
            '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" '
            'vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="0" right="0" top="283" bottom="283"/><hp:inMargin left="283" right="283" top="170" bottom="170"/>'
            '<hp:cellzoneList/>'
            f'{"".join(row_xml)}'
            '</hp:tbl></hp:ctrl></hp:run>'
            '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" '
            'baseline="850" spacing="600" horzpos="0" horzsize="42520" flags="393216"/></hp:linesegarray>'
            '</hp:p>'
        )

    def _build_table_row(
        self,
        row: list[str],
        *,
        row_index: int,
        paragraph_id: int,
        col_widths: list[int],
    ) -> str:
        cells: list[str] = []
        height = 1400 if row_index == 0 else 2600
        for col_index, width in enumerate(col_widths):
            text = row[col_index] if col_index < len(row) else ""
            cells.append(
                self._build_table_cell(
                    text,
                    row_index=row_index,
                    col_index=col_index,
                    width=width,
                    height=height,
                    paragraph_id=paragraph_id + 100 + row_index * 20 + col_index,
                )
            )
        return f'<hp:tr>{"".join(cells)}</hp:tr>'

    def _build_table_cell(
        self,
        text: str,
        *,
        row_index: int,
        col_index: int,
        width: int,
        height: int,
        paragraph_id: int,
    ) -> str:
        paragraph = self._build_table_cell_paragraph(text, paragraph_id)
        return (
            '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="1">'
            f'<hp:cellAddr colAddr="{col_index}" rowAddr="{row_index}"/>'
            '<hp:cellSpan colSpan="1" rowSpan="1"/>'
            f'<hp:cellSz width="{width}" height="{height}"/>'
            '<hp:cellMargin left="283" right="283" top="170" bottom="170"/>'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
            f'linkListIDRef="0" linkListNextIDRef="0" textWidth="{max(1, width - 566)}" textHeight="0" hasTextRef="0" hasNumRef="0">'
            f'{paragraph}</hp:subList></hp:tc>'
        )

    def _build_table_cell_paragraph(self, text: str, paragraph_id: int) -> str:
        escaped = self._escape_xml(text)
        return (
            f'<hp:p id="{paragraph_id}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t>{escaped}</hp:t></hp:run>'
            '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" '
            'baseline="850" spacing="600" horzpos="0" horzsize="42520" flags="393216"/></hp:linesegarray>'
            '</hp:p>'
        )

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
