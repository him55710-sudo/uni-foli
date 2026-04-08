from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_consultant_diagnosis_pdf(
    *,
    report_payload: dict[str, Any],
    output_path: Path,
    report_mode: str,
    template_id: str,
    include_appendix: bool,
    include_citations: bool,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font_name, font_bold = _resolve_font_names()

    minimum_pages = 10 if report_mode == "premium_10p" else 5
    sections = [item for item in report_payload.get("sections", []) if isinstance(item, dict)]
    score_blocks = [item for item in report_payload.get("score_blocks", []) if isinstance(item, dict)]
    roadmap = [item for item in report_payload.get("roadmap", []) if isinstance(item, dict)]
    citations = [item for item in report_payload.get("citations", []) if isinstance(item, dict)]
    uncertainty_notes = [str(item).strip() for item in report_payload.get("uncertainty_notes", []) if str(item).strip()]
    appendix_notes = [str(item).strip() for item in report_payload.get("appendix_notes", []) if str(item).strip()]

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=42,
        bottomMargin=48,
        title=str(report_payload.get("title") or "Consultant Diagnosis Report"),
        author="uni-foli diagnosis",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DiagnosisCoverTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=27,
        leading=33,
        textColor=colors.HexColor("#0b1f3a"),
        alignment=TA_LEFT,
        spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        "DiagnosisCoverSubtitle",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=11,
        leading=16,
        textColor=colors.HexColor("#334155"),
        alignment=TA_LEFT,
        spaceAfter=8,
    )
    h2_style = ParagraphStyle(
        "DiagnosisHeading",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#1d4ed8"),
        spaceBefore=6,
        spaceAfter=8,
    )
    h3_style = ParagraphStyle(
        "DiagnosisHeading3",
        parent=styles["Heading3"],
        fontName=font_bold,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "DiagnosisBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=16,
        textColor=colors.HexColor("#111827"),
        spaceAfter=7,
    )
    bullet_style = ParagraphStyle(
        "DiagnosisBullet",
        parent=body_style,
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=5,
    )
    meta_style = ParagraphStyle(
        "DiagnosisMeta",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
        alignment=TA_LEFT,
    )
    callout_style = ParagraphStyle(
        "DiagnosisCallout",
        parent=styles["BodyText"],
        fontName=font_bold,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
    )

    story: list[Any] = []

    # Cover
    story.extend(
        [
            Paragraph("UNI FOLI CONSULTANT DIAGNOSIS", meta_style),
            Paragraph(_escape(str(report_payload.get("title") or "전문 컨설턴트 진단서")), title_style),
            Paragraph(_escape(str(report_payload.get("subtitle") or "")), subtitle_style),
            Spacer(1, 10),
        ]
    )

    cover_meta_table = Table(
        [
            ["대상 프로젝트", _escape(str(report_payload.get("student_target_context") or "-"))],
            ["리포트 모드", "Premium 10p" if report_mode == "premium_10p" else "Compact"],
            ["템플릿", _escape(template_id)],
            ["생성 시각", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
        ],
        colWidths=[doc.width * 0.23, doc.width * 0.77],
        hAlign="LEFT",
    )
    cover_meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.9, colors.HexColor("#bfdbfe")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbeafe")),
                ("FONTNAME", (0, 0), (0, -1), font_bold),
                ("FONTNAME", (1, 0), (1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(cover_meta_table)
    story.append(Spacer(1, 10))

    story.append(
        _build_callout(
            text="본 진단서는 학생부 기반 근거와 불확실성 표시를 포함하며, 합격 보장이나 과장된 성취를 제시하지 않습니다.",
            width=doc.width,
            style=callout_style,
            border_color=colors.HexColor("#93c5fd"),
            fill_color=colors.HexColor("#eff6ff"),
        )
    )
    story.append(PageBreak())

    # Executive snapshot + scores
    story.append(Paragraph("1. Executive Summary", h2_style))
    section_map = {str(item.get("id") or ""): item for item in sections}
    executive = section_map.get("executive_summary")
    if executive:
        story.extend(_render_section_body(executive, body_style, bullet_style))
    else:
        story.append(Paragraph("핵심 진단 개요를 준비 중입니다.", body_style))

    if score_blocks:
        story.append(Spacer(1, 8))
        story.append(Paragraph("핵심 평가 축", h3_style))
        score_rows = [["축", "점수", "해석", "불확실성"]]
        for block in score_blocks:
            score_rows.append(
                [
                    _escape(str(block.get("label") or block.get("key") or "-")),
                    str(block.get("score") or "-"),
                    _escape(str(block.get("interpretation") or "-")),
                    _escape(str(block.get("uncertainty_note") or "-")),
                ]
            )
        score_table = Table(
            score_rows,
            colWidths=[doc.width * 0.16, doc.width * 0.09, doc.width * 0.45, doc.width * 0.30],
            repeatRows=1,
            hAlign="LEFT",
        )
        score_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTNAME", (0, 1), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(score_table)

    if uncertainty_notes:
        story.append(Spacer(1, 8))
        story.append(Paragraph("불확실성 및 검증 필요 항목", h3_style))
        for line in uncertainty_notes:
            story.append(Paragraph(f"&#8226; {_escape(line)}", bullet_style))

    # Main sections
    for index, section in enumerate(sections):
        section_id = str(section.get("id") or "")
        if section_id == "executive_summary":
            continue
        if section_id == "roadmap":
            continue
        story.append(PageBreak())
        story.append(Paragraph(f"{index + 2}. {_escape(str(section.get('title') or '진단 섹션'))}", h2_style))
        subtitle = str(section.get("subtitle") or "").strip()
        if subtitle:
            story.append(Paragraph(_escape(subtitle), subtitle_style))
        story.extend(_render_section_body(section, body_style, bullet_style))

        evidence_items = [item for item in section.get("evidence_items", []) if isinstance(item, dict)]
        if evidence_items:
            story.append(Spacer(1, 6))
            story.append(Paragraph("근거 앵커", h3_style))
            for evidence in evidence_items[:5]:
                page = evidence.get("page_number")
                source = str(evidence.get("source_label") or "근거 출처")
                excerpt = str(evidence.get("excerpt") or "").strip()
                if page:
                    source = f"{source} (p.{page})"
                story.append(Paragraph(f"&#8226; {_escape(source)}: {_escape(excerpt)}", bullet_style))

        unsupported = [str(item).strip() for item in section.get("unsupported_claims", []) if str(item).strip()]
        if unsupported:
            story.append(Spacer(1, 4))
            story.append(
                _build_callout(
                    text="추가 확인 필요: " + " | ".join(unsupported[:4]),
                    width=doc.width,
                    style=callout_style,
                    border_color=colors.HexColor("#fdba74"),
                    fill_color=colors.HexColor("#fff7ed"),
                )
            )

    # Roadmap
    if roadmap:
        story.append(PageBreak())
        story.append(Paragraph("실행 로드맵 (1개월 / 3개월 / 6개월)", h2_style))
        for item in roadmap:
            story.append(Paragraph(_escape(str(item.get("title") or "-")), h3_style))
            for action in item.get("actions", [])[:6]:
                story.append(Paragraph(f"&#8226; {_escape(str(action))}", bullet_style))
            signals = [str(signal).strip() for signal in item.get("success_signals", []) if str(signal).strip()]
            if signals:
                story.append(Paragraph("성공 신호", meta_style))
                for signal in signals[:4]:
                    story.append(Paragraph(f"&#8226; {_escape(signal)}", bullet_style))
            cautions = [str(note).strip() for note in item.get("caution_notes", []) if str(note).strip()]
            if cautions:
                story.append(Paragraph("주의 포인트", meta_style))
                for note in cautions[:3]:
                    story.append(Paragraph(f"&#8226; {_escape(note)}", bullet_style))
            story.append(Spacer(1, 5))

    # Citations appendix
    if include_citations and citations:
        story.append(PageBreak())
        story.append(Paragraph("근거/인용 부록", h2_style))
        for citation in citations[:60]:
            source = str(citation.get("source_label") or "출처")
            page_number = citation.get("page_number")
            excerpt = str(citation.get("excerpt") or "").strip()
            score = citation.get("relevance_score")
            prefix = f"{source} (p.{page_number})" if page_number else source
            if score is not None:
                prefix = f"{prefix} | relevance={score}"
            story.append(Paragraph(f"&#8226; {_escape(prefix)}: {_escape(excerpt)}", bullet_style))

    if include_appendix and appendix_notes:
        story.append(PageBreak())
        story.append(Paragraph("부록: 진단 메모", h2_style))
        for note in appendix_notes:
            story.append(Paragraph(f"&#8226; {_escape(note)}", bullet_style))

    estimated_pages = 2 + len(sections) + (1 if roadmap else 0) + (1 if include_citations and citations else 0)
    if include_appendix and appendix_notes:
        estimated_pages += 1
    filler_pages = max(0, minimum_pages - estimated_pages)
    for idx in range(filler_pages):
        story.append(PageBreak())
        story.append(Paragraph(f"추가 분석 노트 {idx + 1}", h2_style))
        story.append(
            Paragraph(
                "이 페이지는 추가 근거 검증과 수정 이력 기록을 위한 공간입니다. "
                "최종 제출 전 핵심 주장과 출처 연결을 다시 확인하세요.",
                body_style,
            )
        )
        story.append(Paragraph("&#8226; 핵심 주장 1개마다 근거 출처를 1개 이상 연결", bullet_style))
        story.append(Paragraph("&#8226; 근거가 약한 문장은 '추가 확인 필요'로 유지", bullet_style))
        story.append(Paragraph("&#8226; 다음 리비전에서 보강할 실제 활동/증빙 항목 정리", bullet_style))

    doc.build(
        story,
        onFirstPage=lambda canvas, doc_obj: _draw_page_chrome(canvas, doc_obj, template_id, font_name, font_bold),
        onLaterPages=lambda canvas, doc_obj: _draw_page_chrome(canvas, doc_obj, template_id, font_name, font_bold),
    )


def _resolve_font_names() -> tuple[str, str]:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
        pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
        return "HYSMyeongJo-Medium", "HYGothic-Medium"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _build_callout(
    *,
    text: str,
    width: float,
    style: ParagraphStyle,
    border_color: colors.Color,
    fill_color: colors.Color,
) -> Table:
    table = Table([[Paragraph(_escape(text), style)]], colWidths=[width], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill_color),
                ("BOX", (0, 0), (-1, -1), 0.8, border_color),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _render_section_body(section: dict[str, Any], body_style: ParagraphStyle, bullet_style: ParagraphStyle) -> list[Any]:
    lines = _markdown_to_lines(str(section.get("body_markdown") or ""))
    if not lines:
        return [Paragraph("내용이 준비되지 않았습니다.", body_style)]
    rendered: list[Any] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            rendered.append(Paragraph(f"&#8226; {_escape(stripped[2:].strip())}", bullet_style))
            continue
        rendered.append(Paragraph(_escape(stripped), body_style))
    return rendered


def _markdown_to_lines(markdown: str) -> list[str]:
    if not markdown:
        return []
    lines = [line.rstrip() for line in markdown.replace("\r\n", "\n").split("\n")]
    normalized: list[str] = []
    for line in lines:
        if line.startswith("### "):
            normalized.append(line[4:])
            continue
        if line.startswith("## "):
            normalized.append(line[3:])
            continue
        if line.startswith("# "):
            normalized.append(line[2:])
            continue
        normalized.append(line)
    return normalized


def _draw_page_chrome(canvas: Any, doc: Any, template_id: str, font_name: str, font_bold: str) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0b1f3a"))
    canvas.rect(0, height - 16, width, 16, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont(font_bold, 7.5)
    canvas.drawString(doc.leftMargin, height - 11, f"UNI FOLI CONSULTANT DIAGNOSIS | {template_id.upper()}")

    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, 32, width - doc.rightMargin, 32)
    canvas.setFont(font_name, 8.5)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(doc.leftMargin, 18, "Evidence-first consultant report")
    canvas.drawRightString(width - doc.rightMargin, 18, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
