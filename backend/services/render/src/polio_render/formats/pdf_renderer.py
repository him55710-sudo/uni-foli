from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from polio_render.formats.base import BaseRenderer
from polio_render.markdown import split_markdown_sections
from polio_render.models import RenderArtifact, RenderBuildContext
from polio_shared.paths import find_project_root


class PdfRenderer(BaseRenderer):
    extension = ".pdf"
    implementation_level = "reportlab"

    def render(self, context: RenderBuildContext) -> RenderArtifact:
        output_path = self.prepare_output_path(context)
        self._build_pdf(context, output_path)

        relative_path = str(output_path.relative_to(find_project_root()))
        message = "PDF renderer completed with ReportLab."
        return RenderArtifact(
            absolute_path=str(output_path),
            relative_path=relative_path,
            message=message,
        )

    def _build_pdf(self, context: RenderBuildContext, output_path) -> None:
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=50,
            rightMargin=50,
            topMargin=54,
            bottomMargin=54,
            title=context.draft_title,
            author=context.requested_by or "polio backend",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "PolioTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_LEFT,
            spaceAfter=10,
        )
        meta_style = ParagraphStyle(
            "PolioMeta",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            spaceAfter=6,
        )
        heading_style = ParagraphStyle(
            "PolioHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1d4ed8"),
            spaceBefore=10,
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "PolioBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=colors.black,
            spaceAfter=6,
        )

        story = [
            Paragraph(context.project_title, title_style),
            Paragraph(f"Draft: {context.draft_title}", meta_style),
            Paragraph(f"Requested by: {context.requested_by or 'anonymous'}", meta_style),
            Spacer(1, 12),
        ]

        for section_title, lines in split_markdown_sections(context.content_markdown):
            if section_title:
                story.append(Paragraph(section_title, heading_style))
            if not lines:
                story.append(Paragraph("No content provided.", body_style))
            else:
                for line in lines:
                    text = self._escape_text(line)
                    if line.startswith("- ") or line.startswith("* "):
                        story.append(Paragraph(f"&#8226; {self._escape_text(line[2:].strip())}", body_style))
                    else:
                        story.append(Paragraph(text, body_style))
            story.append(Spacer(1, 6))

        doc.build(story, onFirstPage=self._draw_footer, onLaterPages=self._draw_footer)

    @staticmethod
    def _draw_footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(doc.leftMargin, 20, f"polio export • page {canvas.getPageNumber()}")
        canvas.restoreState()

    @staticmethod
    def _escape_text(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
