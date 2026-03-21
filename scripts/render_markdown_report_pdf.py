from __future__ import annotations

from pathlib import Path
import shutil

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_MD = PROJECT_ROOT / "docs" / "reports" / "polio_backend_cto_assessment_20260321.md"
OUTPUT_PDF = PROJECT_ROOT / "output" / "pdf" / "polio_backend_cto_assessment_20260321.pdf"
DOWNLOAD_PDF = Path.home() / "Downloads" / "polio-backend-cto-assessment-20260321.pdf"


def register_fonts() -> tuple[str, str]:
    regular = Path("C:/Windows/Fonts/malgun.ttf")
    bold = Path("C:/Windows/Fonts/malgunbd.ttf")
    pdfmetrics.registerFont(TTFont("MalgunGothic", str(regular)))
    pdfmetrics.registerFont(TTFont("MalgunGothic-Bold", str(bold)))
    return "MalgunGothic", "MalgunGothic-Bold"


BODY_FONT, BOLD_FONT = register_fonts()


def build_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=styles["Title"],
            fontName=BOLD_FONT,
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=styles["Heading1"],
            fontName=BOLD_FONT,
            fontSize=17,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=8,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            fontName=BOLD_FONT,
            fontSize=12.5,
            leading=17,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=7,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=styles["Heading3"],
            fontName=BOLD_FONT,
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=5,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontName=BODY_FONT,
            fontSize=9.4,
            leading=15,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=styles["BodyText"],
            fontName=BODY_FONT,
            fontSize=9.3,
            leading=14,
            leftIndent=14,
            firstLineIndent=-8,
            bulletIndent=0,
            spaceAfter=3,
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=styles["BodyText"],
            fontName=BODY_FONT,
            fontSize=9.2,
            leading=14,
            textColor=colors.HexColor("#102a43"),
            spaceAfter=4,
        ),
        "pre": ParagraphStyle(
            "Pre",
            fontName="Courier",
            fontSize=7.4,
            leading=9.2,
            textColor=colors.HexColor("#0f172a"),
        ),
    }


STYLES = build_styles()


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.setFont(BODY_FONT, 8)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(18 * mm, height - 11 * mm, "Polio CTO Backend Assessment")
    canvas.drawString(18 * mm, 10 * mm, "Source: current repository state")
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def quote_box(text: str) -> Table:
    table = Table([[Paragraph(text, STYLES["quote"])]], colWidths=[172 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e0f2fe")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#7dd3fc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def flush_paragraph(buffer: list[str], story: list) -> None:
    if not buffer:
        return
    text = " ".join(line.strip() for line in buffer if line.strip())
    story.append(Paragraph(text, STYLES["body"]))
    buffer.clear()


def render_markdown(markdown_text: str) -> list:
    story: list = []
    paragraph_buffer: list[str] = []
    code_buffer: list[str] = []
    quote_buffer: list[str] = []
    in_code = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()

        if line.strip() == "```":
            flush_paragraph(paragraph_buffer, story)
            if quote_buffer:
                story.append(quote_box("<br/>".join(quote_buffer)))
                quote_buffer.clear()
            in_code = not in_code
            if not in_code and code_buffer:
                story.append(Preformatted("\n".join(code_buffer), STYLES["pre"]))
                story.append(Spacer(1, 4))
                code_buffer.clear()
            continue

        if in_code:
            code_buffer.append(line)
            continue

        if not line.strip():
            flush_paragraph(paragraph_buffer, story)
            if quote_buffer:
                story.append(quote_box("<br/>".join(quote_buffer)))
                quote_buffer.clear()
            story.append(Spacer(1, 4))
            continue

        if line.strip() == "---":
            flush_paragraph(paragraph_buffer, story)
            if quote_buffer:
                story.append(quote_box("<br/>".join(quote_buffer)))
                quote_buffer.clear()
            story.append(PageBreak())
            continue

        if line.startswith("> "):
            flush_paragraph(paragraph_buffer, story)
            quote_buffer.append(line[2:].strip())
            continue

        if quote_buffer:
            story.append(quote_box("<br/>".join(quote_buffer)))
            quote_buffer.clear()

        if line.startswith("# "):
            flush_paragraph(paragraph_buffer, story)
            story.append(Paragraph(line[2:].strip(), STYLES["title"]))
            continue
        if line.startswith("## "):
            flush_paragraph(paragraph_buffer, story)
            story.append(Paragraph(line[3:].strip(), STYLES["h1"]))
            continue
        if line.startswith("### "):
            flush_paragraph(paragraph_buffer, story)
            story.append(Paragraph(line[4:].strip(), STYLES["h2"]))
            continue
        if line.startswith("#### "):
            flush_paragraph(paragraph_buffer, story)
            story.append(Paragraph(line[5:].strip(), STYLES["h3"]))
            continue
        if line.startswith("- "):
            flush_paragraph(paragraph_buffer, story)
            story.append(Paragraph(f"• {line[2:].strip()}", STYLES["bullet"]))
            continue

        paragraph_buffer.append(line)

    flush_paragraph(paragraph_buffer, story)
    if quote_buffer:
        story.append(quote_box("<br/>".join(quote_buffer)))
    if code_buffer:
        story.append(Preformatted("\n".join(code_buffer), STYLES["pre"]))
    return story


def main() -> None:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_PDF.parent.mkdir(parents=True, exist_ok=True)
    markdown_text = SOURCE_MD.read_text(encoding="utf-8")
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title="Polio CTO Backend Assessment",
        author="Codex",
    )
    story = render_markdown(markdown_text)
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    shutil.copy2(OUTPUT_PDF, DOWNLOAD_PDF)
    print(OUTPUT_PDF)
    print(DOWNLOAD_PDF)


if __name__ == "__main__":
    main()
