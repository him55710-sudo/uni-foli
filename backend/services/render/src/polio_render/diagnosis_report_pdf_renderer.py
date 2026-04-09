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

from polio_render.diagnosis_report_design_contract import get_diagnosis_report_design_contract


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

    render_hints = report_payload.get("render_hints") if isinstance(report_payload.get("render_hints"), dict) else {}
    design_contract = render_hints.get("design_contract") if isinstance(render_hints, dict) else None
    if not isinstance(design_contract, dict):
        design_contract = get_diagnosis_report_design_contract(
            report_mode=report_mode,
            template_id=template_id,
            template_section_schema=(),
        )

    margins = design_contract.get("canvas", {}).get("margins", {}) if isinstance(design_contract.get("canvas"), dict) else {}
    minimum_pages = int(
        report_payload.get("render_hints", {}).get("minimum_pages")
        or design_contract.get("canvas", {}).get("minimum_pages")
        or (10 if report_mode == "premium_10p" else 5)
    )

    sections = [item for item in report_payload.get("sections", []) if isinstance(item, dict)]
    sections = _order_sections(sections, design_contract=design_contract)
    score_blocks = [item for item in report_payload.get("score_blocks", []) if isinstance(item, dict)]
    roadmap = [item for item in report_payload.get("roadmap", []) if isinstance(item, dict)]
    citations = [item for item in report_payload.get("citations", []) if isinstance(item, dict)]
    uncertainty_notes = [str(item).strip() for item in report_payload.get("uncertainty_notes", []) if str(item).strip()]
    appendix_notes = [str(item).strip() for item in report_payload.get("appendix_notes", []) if str(item).strip()]

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=float(margins.get("left", 46)),
        rightMargin=float(margins.get("right", 46)),
        topMargin=float(margins.get("top", 44)),
        bottomMargin=float(margins.get("bottom", 50)),
        title=str(report_payload.get("title") or "Consultant Diagnosis Report"),
        author="uni-foli diagnosis",
    )

    color_tokens = design_contract.get("colors", {}) if isinstance(design_contract.get("colors"), dict) else {}
    style_tokens = _build_style_tokens(
        design_contract=design_contract,
        font_name=font_name,
        font_bold=font_bold,
        color_tokens=color_tokens,
    )

    story: list[Any] = []

    # Cover page
    story.extend(
        [
            Paragraph("UNI FOLI CONSULTANT DIAGNOSIS", style_tokens["cover_label"]),
            Paragraph(_escape(str(report_payload.get("title") or "전문 컨설턴트 진단서")), style_tokens["cover_title"]),
            Paragraph(_escape(str(report_payload.get("subtitle") or "")), style_tokens["cover_subtitle"]),
            Spacer(1, style_tokens["spacing"]["cover_block_gap"]),
        ]
    )

    cover_meta_rows = [
        ["대상 프로젝트", _escape(str(report_payload.get("student_target_context") or "-"))],
        ["리포트 모드", "Premium 10p" if report_mode == "premium_10p" else "Compact"],
        ["템플릿", _escape(template_id)],
        ["생성 시각", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
    ]
    cover_meta_table = Table(
        cover_meta_rows,
        colWidths=[doc.width * 0.22, doc.width * 0.78],
        hAlign="LEFT",
    )
    cover_meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _hex(color_tokens.get("surface_soft"), "#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.8, _hex(color_tokens.get("line_soft"), "#D7DEE8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, _hex(color_tokens.get("line_soft"), "#D7DEE8")),
                ("FONTNAME", (0, 0), (0, -1), font_bold),
                ("FONTNAME", (1, 0), (1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), style_tokens["typography"]["meta_size"]),
                ("LEFTPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["table_cell_padding"]),
                ("RIGHTPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["table_cell_padding"]),
                ("TOPPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["list_item_gap"] + 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["list_item_gap"] + 1),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(cover_meta_table)
    story.append(Spacer(1, style_tokens["spacing"]["cover_block_gap"]))

    story.append(
        _build_callout(
            text="본 진단서는 학생부 근거만 사용하며 합격 보장 또는 허위 성취 서술을 포함하지 않습니다. 불확실한 항목은 별도 표기합니다.",
            width=doc.width,
            style=style_tokens["callout"],
            border_color=_hex(color_tokens.get("line_evidence"), "#C7D2FE"),
            fill_color=_hex(color_tokens.get("surface_evidence"), "#EEF2FF"),
            padding=style_tokens["spacing"]["card_padding"],
        )
    )

    section_groups = _resolve_section_groups(design_contract=design_contract, section_ids=[str(item.get("id") or "") for item in sections])
    section_by_id = {str(item.get("id") or ""): item for item in sections}
    section_order = [str(item.get("id") or "") for item in sections]
    section_number = {section_id: idx + 1 for idx, section_id in enumerate(section_order)}

    for group in section_groups:
        available_ids = [section_id for section_id in group if section_id in section_by_id]
        if not available_ids:
            continue
        story.append(PageBreak())
        for section_id in available_ids:
            section = section_by_id[section_id]
            heading = f"{section_number.get(section_id, 0)}. {str(section.get('title') or '진단 섹션')}"
            story.append(Paragraph(_escape(heading), style_tokens["h2"]))
            subtitle = str(section.get("subtitle") or "").strip()
            if subtitle:
                story.append(Paragraph(_escape(subtitle), style_tokens["subtitle"]))

            story.extend(_render_section_body(section, style_tokens["body"], style_tokens["bullet"]))

            if section_id == "evaluation_axis" and score_blocks:
                story.append(Spacer(1, style_tokens["spacing"]["paragraph_gap"]))
                story.append(Paragraph("평가축 점수표", style_tokens["h3"]))
                story.append(_build_score_table(score_blocks=score_blocks, doc=doc, style_tokens=style_tokens, font_name=font_name, font_bold=font_bold, color_tokens=color_tokens))

            if section_id == "roadmap" and roadmap:
                story.append(Spacer(1, style_tokens["spacing"]["paragraph_gap"]))
                story.append(Paragraph("단계별 액션 플랜", style_tokens["h3"]))
                for roadmap_item in roadmap:
                    story.append(Paragraph(_escape(str(roadmap_item.get("title") or "-")), style_tokens["meta_strong"]))
                    for action in list(roadmap_item.get("actions") or [])[:4]:
                        story.append(Paragraph(f"&#8226; {_escape(str(action))}", style_tokens["bullet"]))

            evidence_items = [item for item in section.get("evidence_items", []) if isinstance(item, dict)]
            if evidence_items:
                story.append(Spacer(1, style_tokens["spacing"]["paragraph_gap"]))
                story.append(Paragraph("근거 앵커", style_tokens["h3"]))
                for evidence in evidence_items[:4]:
                    source_label = str(evidence.get("source_label") or "근거")
                    page = evidence.get("page_number")
                    excerpt = str(evidence.get("excerpt") or "").strip()
                    support_status = str(evidence.get("support_status") or "verified")
                    source_text = f"{source_label} p.{page}" if page else source_label
                    text = f"{source_text} ({support_status}): {excerpt}"
                    story.append(
                        _build_callout(
                            text=text,
                            width=doc.width,
                            style=style_tokens["meta"],
                            border_color=_hex(color_tokens.get("line_evidence"), "#C7D2FE"),
                            fill_color=_hex(color_tokens.get("surface_evidence"), "#EEF2FF"),
                            padding=style_tokens["spacing"]["card_padding"],
                        )
                    )
                    story.append(Spacer(1, style_tokens["spacing"]["list_item_gap"]))

            unsupported_claims = [str(item).strip() for item in section.get("unsupported_claims", []) if str(item).strip()]
            if unsupported_claims:
                story.append(
                    _build_callout(
                        text="검증 필요: " + " | ".join(unsupported_claims[:4]),
                        width=doc.width,
                        style=style_tokens["callout"],
                        border_color=_hex(color_tokens.get("line_warning"), "#FDBA74"),
                        fill_color=_hex(color_tokens.get("surface_warning"), "#FFF7ED"),
                        padding=style_tokens["spacing"]["card_padding"],
                    )
                )

            verification_needed = [str(item).strip() for item in section.get("additional_verification_needed", []) if str(item).strip()]
            if verification_needed:
                story.append(Spacer(1, style_tokens["spacing"]["list_item_gap"]))
                story.append(Paragraph("추가 확인 필요", style_tokens["meta_strong"]))
                for item in verification_needed[:3]:
                    story.append(Paragraph(f"&#8226; {_escape(item)}", style_tokens["bullet"]))

            story.append(Spacer(1, style_tokens["spacing"]["section_gap"]))

    appendix_layout = design_contract.get("appendix_layout", {}) if isinstance(design_contract.get("appendix_layout"), dict) else {}
    max_uncertainty_items = int(appendix_layout.get("max_uncertainty_items", 12))
    max_citation_items = int(appendix_layout.get("max_citation_items", 60))

    if uncertainty_notes or appendix_notes:
        story.append(PageBreak())
        story.append(Paragraph("Appendix / Uncertainty Notes", style_tokens["h2"]))
        if uncertainty_notes:
            story.append(Paragraph("불확실성 및 검증 경계", style_tokens["h3"]))
            for note in uncertainty_notes[:max_uncertainty_items]:
                story.append(Paragraph(f"&#8226; {_escape(note)}", style_tokens["bullet"]))
        if appendix_notes:
            story.append(Spacer(1, style_tokens["spacing"]["section_gap"]))
            story.append(Paragraph("운영/파싱 메모", style_tokens["h3"]))
            for note in appendix_notes[:max_uncertainty_items]:
                story.append(Paragraph(f"&#8226; {_escape(note)}", style_tokens["bullet"]))

    if include_citations and citations:
        story.append(PageBreak())
        story.append(Paragraph("Appendix / Citations", style_tokens["h2"]))
        for citation in citations[:max_citation_items]:
            source = str(citation.get("source_label") or "출처")
            page_number = citation.get("page_number")
            excerpt = str(citation.get("excerpt") or "").strip()
            score = citation.get("relevance_score")
            support_status = str(citation.get("support_status") or "verified")
            prefix = f"{source} (p.{page_number})" if page_number else source
            if score is not None:
                prefix = f"{prefix} | relevance={score} | {support_status}"
            story.append(Paragraph(f"&#8226; {_escape(prefix)}: {_escape(excerpt)}", style_tokens["bullet"]))

    estimated_pages = _estimate_pages(
        section_groups=section_groups,
        has_uncertainty=bool(uncertainty_notes or appendix_notes),
        has_citations=bool(include_citations and citations),
    )
    filler_pages = max(0, minimum_pages - estimated_pages)
    for idx in range(filler_pages):
        story.append(PageBreak())
        story.append(Paragraph(f"Quality Check Note {idx + 1}", style_tokens["h2"]))
        story.append(
            Paragraph(
                "이 페이지는 최종 제출 전 진단 문장-근거 정합성 검토를 위한 확인 영역입니다."
                " 불확실한 항목은 반드시 '추가 확인 필요' 표기를 유지합니다.",
                style_tokens["body"],
            )
        )
        story.append(Paragraph("&#8226; 핵심 주장마다 출처 라인 1개 이상 연결", style_tokens["bullet"]))
        story.append(Paragraph("&#8226; 검증 미완료 문장에 추가 확인 필요 표시", style_tokens["bullet"]))
        story.append(Paragraph("&#8226; 과장/합격 보장/허위 성취 문구 제거", style_tokens["bullet"]))

    doc.build(
        story,
        onFirstPage=lambda canvas, doc_obj: _draw_page_chrome(canvas, doc_obj, template_id, font_name, font_bold, color_tokens),
        onLaterPages=lambda canvas, doc_obj: _draw_page_chrome(canvas, doc_obj, template_id, font_name, font_bold, color_tokens),
    )


def _build_style_tokens(*, design_contract: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> dict[str, Any]:
    styles = getSampleStyleSheet()
    typography = design_contract.get("typography", {}) if isinstance(design_contract.get("typography"), dict) else {}
    spacing = design_contract.get("spacing", {}) if isinstance(design_contract.get("spacing"), dict) else {}

    body_font_size = float(typography.get("body", {}).get("font_size", 10.4) if isinstance(typography.get("body"), dict) else 10.4)
    body_leading = float(typography.get("body", {}).get("leading", 15.6) if isinstance(typography.get("body"), dict) else 15.6)

    title_style = ParagraphStyle(
        "DiagnosisCoverTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=float(typography.get("cover_title", {}).get("font_size", 26) if isinstance(typography.get("cover_title"), dict) else 26),
        leading=float(typography.get("cover_title", {}).get("leading", 32) if isinstance(typography.get("cover_title"), dict) else 32),
        textColor=_hex(color_tokens.get("brand_primary"), "#1E3A5F"),
        alignment=TA_LEFT,
        spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        "DiagnosisCoverSubtitle",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=float(typography.get("cover_subtitle", {}).get("font_size", 11) if isinstance(typography.get("cover_subtitle"), dict) else 11),
        leading=float(typography.get("cover_subtitle", {}).get("leading", 16) if isinstance(typography.get("cover_subtitle"), dict) else 16),
        textColor=_hex(color_tokens.get("text_secondary"), "#334155"),
        alignment=TA_LEFT,
        spaceAfter=8,
    )
    h2_style = ParagraphStyle(
        "DiagnosisHeading",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=float(typography.get("section_heading", {}).get("font_size", 17) if isinstance(typography.get("section_heading"), dict) else 17),
        leading=float(typography.get("section_heading", {}).get("leading", 22) if isinstance(typography.get("section_heading"), dict) else 22),
        textColor=_hex(color_tokens.get("brand_secondary"), "#2B4F7B"),
        spaceBefore=4,
        spaceAfter=6,
    )
    h3_style = ParagraphStyle(
        "DiagnosisHeading3",
        parent=styles["Heading3"],
        fontName=font_bold,
        fontSize=11.2,
        leading=15,
        textColor=_hex(color_tokens.get("text_primary"), "#0F172A"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "DiagnosisBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=body_font_size,
        leading=body_leading,
        textColor=_hex(color_tokens.get("text_primary"), "#0F172A"),
        spaceAfter=float(spacing.get("paragraph_gap", 5)),
    )
    bullet_style = ParagraphStyle(
        "DiagnosisBullet",
        parent=body_style,
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=float(spacing.get("list_item_gap", 3)),
    )
    meta_style = ParagraphStyle(
        "DiagnosisMeta",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=float(typography.get("meta", {}).get("font_size", 8.6) if isinstance(typography.get("meta"), dict) else 8.6),
        leading=float(typography.get("meta", {}).get("leading", 12) if isinstance(typography.get("meta"), dict) else 12),
        textColor=_hex(color_tokens.get("text_muted"), "#526173"),
        alignment=TA_LEFT,
    )
    meta_strong_style = ParagraphStyle(
        "DiagnosisMetaStrong",
        parent=meta_style,
        fontName=font_bold,
        textColor=_hex(color_tokens.get("text_secondary"), "#334155"),
    )
    callout_style = ParagraphStyle(
        "DiagnosisCallout",
        parent=styles["BodyText"],
        fontName=font_bold,
        fontSize=9.2,
        leading=13,
        textColor=_hex(color_tokens.get("text_primary"), "#0F172A"),
        alignment=TA_CENTER,
    )
    cover_label_style = ParagraphStyle(
        "DiagnosisCoverLabel",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=float(typography.get("cover_label", {}).get("font_size", 9) if isinstance(typography.get("cover_label"), dict) else 9),
        leading=float(typography.get("cover_label", {}).get("leading", 12) if isinstance(typography.get("cover_label"), dict) else 12),
        textColor=_hex(color_tokens.get("text_muted"), "#526173"),
        alignment=TA_LEFT,
        spaceAfter=3,
    )

    return {
        "cover_label": cover_label_style,
        "cover_title": title_style,
        "cover_subtitle": subtitle_style,
        "h2": h2_style,
        "h3": h3_style,
        "subtitle": meta_style,
        "body": body_style,
        "bullet": bullet_style,
        "meta": meta_style,
        "meta_strong": meta_strong_style,
        "callout": callout_style,
        "typography": {
            "meta_size": float(typography.get("meta", {}).get("font_size", 8.6) if isinstance(typography.get("meta"), dict) else 8.6),
        },
        "spacing": {
            "cover_block_gap": float(spacing.get("cover_block_gap", 10)),
            "section_gap": float(spacing.get("section_gap", 8)),
            "paragraph_gap": float(spacing.get("paragraph_gap", 5)),
            "list_item_gap": float(spacing.get("list_item_gap", 3)),
            "card_padding": float(spacing.get("card_padding", 9)),
            "table_cell_padding": float(spacing.get("table_cell_padding", 5)),
        },
    }


def _build_score_table(
    *,
    score_blocks: list[dict[str, Any]],
    doc: SimpleDocTemplate,
    style_tokens: dict[str, Any],
    font_name: str,
    font_bold: str,
    color_tokens: dict[str, Any],
) -> Table:
    rows = [["축", "점수", "해석", "불확실성"]]
    for block in score_blocks:
        rows.append(
            [
                _escape(str(block.get("label") or block.get("key") or "-")),
                str(block.get("score") or "-"),
                _escape(str(block.get("interpretation") or "-")),
                _escape(str(block.get("uncertainty_note") or "-")),
            ]
        )
    table = Table(
        rows,
        colWidths=[doc.width * 0.16, doc.width * 0.1, doc.width * 0.44, doc.width * 0.3],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _hex(color_tokens.get("surface_panel"), "#F1F5F9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), _hex(color_tokens.get("text_primary"), "#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.35, _hex(color_tokens.get("line_soft"), "#D7DEE8")),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTNAME", (0, 1), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), style_tokens["typography"]["meta_size"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["table_cell_padding"]),
                ("RIGHTPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["table_cell_padding"]),
                ("TOPPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["list_item_gap"] + 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["list_item_gap"] + 1),
            ]
        )
    )
    return table


def _order_sections(sections: list[dict[str, Any]], *, design_contract: dict[str, Any]) -> list[dict[str, Any]]:
    hierarchy = design_contract.get("section_hierarchy") if isinstance(design_contract.get("section_hierarchy"), dict) else {}
    required_order = hierarchy.get("required_order") if isinstance(hierarchy, dict) else []
    if not isinstance(required_order, list) or not required_order:
        return sections

    section_map = {str(section.get("id") or ""): section for section in sections}
    ordered: list[dict[str, Any]] = []
    for section_id in required_order:
        section = section_map.get(str(section_id))
        if section is not None:
            ordered.append(section)
    extras = [section for section in sections if str(section.get("id") or "") not in required_order]
    return [*ordered, *extras]


def _resolve_section_groups(*, design_contract: dict[str, Any], section_ids: list[str]) -> list[list[str]]:
    hierarchy = design_contract.get("section_hierarchy") if isinstance(design_contract.get("section_hierarchy"), dict) else {}
    groups = hierarchy.get("section_groups") if isinstance(hierarchy, dict) else None
    if not isinstance(groups, list) or not groups:
        return [[section_id] for section_id in section_ids if section_id]

    normalized: list[list[str]] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        clean = [str(section_id).strip() for section_id in group if str(section_id).strip()]
        if clean:
            normalized.append(clean)
    return normalized or [[section_id] for section_id in section_ids if section_id]


def _estimate_pages(*, section_groups: list[list[str]], has_uncertainty: bool, has_citations: bool) -> int:
    pages = 1  # cover
    pages += len([group for group in section_groups if group])
    if has_uncertainty:
        pages += 1
    if has_citations:
        pages += 1
    return pages


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
    padding: float,
) -> Table:
    table = Table([[Paragraph(_escape(text), style)]], colWidths=[width], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill_color),
                ("BOX", (0, 0), (-1, -1), 0.75, border_color),
                ("LEFTPADDING", (0, 0), (-1, -1), padding),
                ("RIGHTPADDING", (0, 0), (-1, -1), padding),
                ("TOPPADDING", (0, 0), (-1, -1), padding - 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), padding - 1),
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


def _draw_page_chrome(
    canvas: Any,
    doc: Any,
    template_id: str,
    font_name: str,
    font_bold: str,
    color_tokens: dict[str, Any],
) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(_hex(color_tokens.get("brand_primary"), "#1E3A5F"))
    canvas.rect(0, height - 16, width, 16, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont(font_bold, 7.4)
    canvas.drawString(doc.leftMargin, height - 11, f"UNI FOLI CONSULTANT DIAGNOSIS | {template_id.upper()}")

    canvas.setStrokeColor(_hex(color_tokens.get("line_soft"), "#D7DEE8"))
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, 32, width - doc.rightMargin, 32)
    canvas.setFont(font_name, 8.3)
    canvas.setFillColor(_hex(color_tokens.get("text_muted"), "#526173"))
    canvas.drawString(doc.leftMargin, 18, "Evidence-first consultant deliverable")
    canvas.drawRightString(width - doc.rightMargin, 18, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _hex(value: Any, fallback: str) -> colors.Color:
    candidate = str(value or "").strip() or fallback
    try:
        return colors.HexColor(candidate)
    except Exception:
        return colors.HexColor(fallback)


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
