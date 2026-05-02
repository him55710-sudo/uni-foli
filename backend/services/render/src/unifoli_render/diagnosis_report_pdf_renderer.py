from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from unifoli_render.diagnosis_report_design_contract import get_diagnosis_report_design_contract


_PUBLIC_INTERNAL_TOKEN_RE = re.compile(
    r"\[?\b(?:student_record|parsed_document|document_chunk|p\d+-e\d+|evidence[_-]?\d+|anchor[_-]?\d+|citation[_-]?\d+|A\d{1,4})\b\]?",
    re.IGNORECASE,
)


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
    sections = [item for item in report_payload.get("sections", []) if isinstance(item, dict)]
    sections = _order_sections(sections, design_contract=design_contract)
    score_blocks = [item for item in report_payload.get("score_blocks", []) if isinstance(item, dict)]
    score_groups = [item for item in report_payload.get("score_groups", []) if isinstance(item, dict)]
    roadmap = [item for item in report_payload.get("roadmap", []) if isinstance(item, dict)]
    citations = [item for item in report_payload.get("citations", []) if isinstance(item, dict)]
    uncertainty_notes = [str(item).strip() for item in report_payload.get("uncertainty_notes", []) if str(item).strip()]
    appendix_notes = [str(item).strip() for item in report_payload.get("appendix_notes", []) if str(item).strip()]
    public_appendix_enabled = bool(render_hints.get("public_appendix_enabled", include_appendix))
    public_citations_enabled = bool(render_hints.get("public_citations_enabled", include_citations))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=float(margins.get("left", 46)),
        rightMargin=float(margins.get("right", 46)),
        topMargin=float(margins.get("top", 44)),
        bottomMargin=float(margins.get("bottom", 50)),
        title=str(report_payload.get("title") or "유니폴리 진단 보고서"),
        author="유니폴리 진단",
    )

    color_tokens = design_contract.get("colors", {}) if isinstance(design_contract.get("colors"), dict) else {}
    style_tokens = _build_style_tokens(
        design_contract=design_contract,
        font_name=font_name,
        font_bold=font_bold,
        color_tokens=color_tokens,
    )

    if bool(render_hints.get("structured_premium_renderer")):
        story = _build_structured_report_story(
            report_payload=report_payload,
            doc=doc,
            style_tokens=style_tokens,
            font_name=font_name,
            font_bold=font_bold,
            color_tokens=color_tokens,
            report_mode=report_mode,
            render_hints=render_hints,
        )
        doc.build(
            story,
            onFirstPage=lambda canvas, doc_obj: _draw_page_chrome(canvas, doc_obj, template_id, font_name, font_bold, color_tokens),
            onLaterPages=lambda canvas, doc_obj: _draw_page_chrome(canvas, doc_obj, template_id, font_name, font_bold, color_tokens),
        )
        return

    story: list[Any] = []

    # Cover page
    story.extend(
        [
            Paragraph("유니폴리 컨설턴트 진단 리포트", style_tokens["cover_label"]),
            Paragraph(_escape(str(report_payload.get("title") or "유니폴리 진단 보고서")), style_tokens["cover_title"]),
            Paragraph(_escape(str(report_payload.get("subtitle") or "근거 중심 진단 결과")), style_tokens["cover_subtitle"]),
            Spacer(1, style_tokens["spacing"]["cover_block_gap"]),
        ]
    )

    cover_meta_rows = [
        ["대상 프로젝트", _escape(str(report_payload.get("student_target_context") or "-"))],
        ["리포트 모드", "Premium Report" if _canonical_report_mode(report_mode) == "premium" else "Basic Report"],
        ["템플릿", "내부 고정 템플릿"],
        [
            "핵심 판정",
            _escape(str(render_hints.get("one_line_verdict") or "학생부 근거 기반으로 진단 결론을 정리했습니다.")),
        ],
        [
            "분석 신뢰도",
            f"{int(round(float(render_hints.get('analysis_confidence_score', 0.0)) * 100))}%",
        ],
        ["생성 시각", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M (UTC)")],
    ]
    cover_meta_table = Table(
        cover_meta_rows,
        colWidths=[doc.width * 0.22, doc.width * 0.78],
        hAlign="LEFT",
    )
    cover_meta_table.setStyle(
        TableStyle(
            [
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_hex(color_tokens.get("surface_soft"), "#F8FAFC"), _hex(color_tokens.get("surface_panel"), "#EEF2FF")]),
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
            text="진단서는 학생부 근거를 기반으로 작성되며, 불확실한 항목은 별도 검증 메모로 안내합니다.",
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
            semantic = _section_semantic_badge(section_id=section_id, color_tokens=color_tokens)
            if semantic is not None:
                story.append(
                    _build_callout(
                        text=semantic["label"],
                        width=doc.width,
                        style=style_tokens["meta_strong"],
                        border_color=semantic["border_color"],
                        fill_color=semantic["fill_color"],
                        padding=max(5, style_tokens["spacing"]["card_padding"] - 2),
                    )
                )
            subtitle = str(section.get("subtitle") or "").strip()
            if subtitle:
                story.append(Paragraph(_escape(subtitle), style_tokens["subtitle"]))

            story.extend(
                _render_section_body(
                    section,
                    style_tokens["body"],
                    style_tokens["bullet"],
                    section_id=section_id,
                )
            )

            if section_id == "record_baseline_dashboard":
                story.append(Spacer(1, style_tokens["spacing"]["paragraph_gap"]))
                if score_groups:
                    for group in score_groups:
                        group_title = str(group.get("title") or "점수 그룹")
                        story.append(Paragraph(_escape(group_title), style_tokens["h3"]))
                        group_blocks = [item for item in group.get("blocks", []) if isinstance(item, dict)]
                        if group_blocks:
                            story.append(
                                _build_score_table(
                                    score_blocks=group_blocks,
                                    doc=doc,
                                    style_tokens=style_tokens,
                                    font_name=font_name,
                                    font_bold=font_bold,
                                    color_tokens=color_tokens,
                                    compact=True,
                                )
                            )
                        note = str(group.get("note") or "").strip()
                        if note:
                            story.append(Paragraph(_escape(note), style_tokens["meta"]))
                        story.append(Spacer(1, style_tokens["spacing"]["list_item_gap"]))
                elif score_blocks:
                    story.append(Paragraph("평가 점수", style_tokens["h3"]))
                    story.append(
                        _build_score_table(
                            score_blocks=score_blocks,
                            doc=doc,
                            style_tokens=style_tokens,
                            font_name=font_name,
                            font_bold=font_bold,
                            color_tokens=color_tokens,
                        )
                    )

            if section_id == "roadmap" and roadmap:
                story.append(Spacer(1, style_tokens["spacing"]["paragraph_gap"]))
                story.append(Paragraph("단계별 실행 계획", style_tokens["h3"]))
                for roadmap_item in roadmap:
                    story.append(Paragraph(_escape(str(roadmap_item.get("title") or "-")), style_tokens["meta_strong"]))
                    for action in list(roadmap_item.get("actions") or [])[:4]:
                        story.append(Paragraph(f"&#8226; {_escape(str(action))}", style_tokens["bullet"]))

            evidence_items = [item for item in section.get("evidence_items", []) if isinstance(item, dict)]
            should_render_evidence = section_id in {
                "evidence_cards",
                "major_fit",
                "major_fit_interpretation",
                "risk_analysis",
                "weakness_risk_analysis",
                "recommended_report_directions",
                "recommended_report_direction",
            }
            if evidence_items and should_render_evidence:
                story.append(Spacer(1, style_tokens["spacing"]["paragraph_gap"]))
                story.append(Paragraph("근거 앵커", style_tokens["h3"]))
                max_evidence_cards = 3 if section_id == "evidence_cards" else 2
                for evidence in evidence_items[:max_evidence_cards]:
                    source_label = str(evidence.get("source_label") or "근거")
                    page = evidence.get("page_number")
                    excerpt = str(evidence.get("excerpt") or "").strip()
                    support_status = _support_status_label(str(evidence.get("support_status") or "verified"))
                    source_text = f"{source_label} {page}페이지" if page else source_label
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
                for item in verification_needed[:2]:
                    story.append(Paragraph(f"&#8226; {_escape(item)}", style_tokens["bullet"]))

            story.append(Spacer(1, style_tokens["spacing"]["section_gap"]))

    appendix_layout = design_contract.get("appendix_layout", {}) if isinstance(design_contract.get("appendix_layout"), dict) else {}
    max_uncertainty_items = int(appendix_layout.get("max_uncertainty_items", 12))
    max_citation_items = int(appendix_layout.get("max_citation_items", 60))

    if public_appendix_enabled and (uncertainty_notes or appendix_notes):
        story.append(PageBreak())
        story.append(Paragraph("부록 / 불확실성 및 검증 메모", style_tokens["h2"]))
        if uncertainty_notes:
            story.append(Paragraph("불확실성 및 검증 경계", style_tokens["h3"]))
            for note in uncertainty_notes[:max_uncertainty_items]:
                story.append(Paragraph(f"&#8226; {_escape(note)}", style_tokens["bullet"]))
        if appendix_notes:
            story.append(Spacer(1, style_tokens["spacing"]["section_gap"]))
            story.append(Paragraph("운영/파싱 메모", style_tokens["h3"]))
            for note in appendix_notes[:max_uncertainty_items]:
                story.append(Paragraph(f"&#8226; {_escape(note)}", style_tokens["bullet"]))

    if public_citations_enabled and citations:
        story.append(PageBreak())
        story.append(Paragraph("부록 / 출처 근거 목록", style_tokens["h2"]))
        for citation in citations[:max_citation_items]:
            source = str(citation.get("source_label") or "출처")
            page_number = citation.get("page_number")
            excerpt = str(citation.get("excerpt") or "").strip()
            score = citation.get("relevance_score")
            support_status = _support_status_label(str(citation.get("support_status") or "verified"))
            prefix = f"{source} ({page_number}페이지)" if page_number else source
            if score is not None:
                prefix = f"{prefix} | 관련도={score} | {support_status}"
            story.append(Paragraph(f"&#8226; {_escape(prefix)}: {_escape(excerpt)}", style_tokens["bullet"]))

    doc.build(
        story,
        onFirstPage=lambda canvas, doc_obj: _draw_page_chrome(canvas, doc_obj, template_id, font_name, font_bold, color_tokens),
        onLaterPages=lambda canvas, doc_obj: _draw_page_chrome(canvas, doc_obj, template_id, font_name, font_bold, color_tokens),
    )


def _canonical_report_mode(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"compact", "basic"}:
        return "basic"
    if normalized in {"premium_10p", "premium", ""}:
        return "premium"
    if normalized == "consultant":
        return "consultant"
    return "premium"


def _build_structured_report_story(
    *,
    report_payload: dict[str, Any],
    doc: SimpleDocTemplate,
    style_tokens: dict[str, Any],
    font_name: str,
    font_bold: str,
    color_tokens: dict[str, Any],
    report_mode: str,
    render_hints: dict[str, Any],
) -> list[Any]:
    mode = _canonical_report_mode(str(report_payload.get("report_mode") or report_mode))
    target_pages = int(render_hints.get("target_pages") or (9 if mode == "basic" else 32 if mode == "consultant" else 24))
    pages = _structured_page_definitions(report_payload=report_payload, mode=mode, target_pages=target_pages)
    story: list[Any] = []
    for page_index, page in enumerate(pages[:target_pages]):
        if page_index:
            story.append(PageBreak())
        story.extend(
            _render_structured_page(
                page=page,
                page_index=page_index,
                report_payload=report_payload,
                doc=doc,
                style_tokens=style_tokens,
                font_name=font_name,
                font_bold=font_bold,
                color_tokens=color_tokens,
                render_hints=render_hints,
            )
        )
    return story


def _structured_page_definitions(*, report_payload: dict[str, Any], mode: str, target_pages: int) -> list[dict[str, Any]]:
    if mode == "basic":
        pages = [
            {"kind": "cover", "title": "Cover"},
            {"kind": "summary", "title": "Executive Summary"},
            {"kind": "dashboard", "title": "Overall Dashboard"},
            {"kind": "subject_table", "title": "과목별 세특 핵심 점검"},
            {"kind": "strengths", "title": "강점 분석"},
            {"kind": "risks", "title": "약점 및 리스크"},
            {"kind": "topics", "title": "추천 탐구보고서"},
            {"kind": "roadmap", "title": "실행 로드맵"},
            {"kind": "appendix", "title": "근거 및 검증 메모"},
        ]
    else:
        pages = [
            {"kind": "cover", "title": "Cover"},
            {"kind": "summary", "title": "Executive Summary"},
            {"kind": "dashboard", "title": "Overall Dashboard"},
            {"kind": "record_structure", "title": "생기부 전체 구조 분석"},
            {"kind": "subject_table", "title": "과목별 세특 점수표"},
            {"kind": "subject_cards", "title": "과목별 세특 상세 분석 1", "slice": (0, 4)},
            {"kind": "subject_cards", "title": "과목별 세특 상세 분석 2", "slice": (4, 8)},
            {"kind": "competency", "title": "전공 역량 매핑"},
            {"kind": "network", "title": "생기부 연결망 분석"},
            {"kind": "growth", "title": "학년별 성장 서사 분석"},
            {"kind": "strengths", "title": "강점 분석"},
            {"kind": "risks", "title": "약점 및 리스크 분석"},
            {"kind": "topics", "title": "추천 탐구보고서 방향 1", "slice": (0, 6)},
            {"kind": "topics", "title": "추천 탐구보고서 방향 2", "slice": (6, 12)},
            {"kind": "avoid", "title": "피해야 할 탐구 주제"},
            {"kind": "rewrites", "title": "학생부 문장 Before/After"},
            {"kind": "interviews", "title": "면접 예상 질문 1: 전공 적합성", "category": "전공 적합성"},
            {"kind": "interviews", "title": "면접 예상 질문 2: 탐구 과정 검증", "category": "탐구 과정 검증"},
            {"kind": "interviews", "title": "면접 예상 질문 3: 약점 방어", "category": "약점 방어"},
            {"kind": "roadmap", "title": "실행 로드맵"},
            {"kind": "action_plan", "title": "우선순위 액션 플랜"},
            {"kind": "appendix", "title": "근거 및 검증 부록"},
        ]
        if mode == "consultant":
            pages.extend(
                [
                    {"kind": "subject_cards", "title": "과목별 세특 상세 진단 3", "slice": (0, 3)},
                    {"kind": "subject_cards", "title": "과목별 세특 상세 진단 4", "slice": (3, 6)},
                    {"kind": "subject_cards", "title": "과목별 세특 상세 진단 5", "slice": (5, 8)},
                    {"kind": "network", "title": "생기부 서사 네트워크 정밀 진단"},
                    {"kind": "competency", "title": "전공 역량별 근거 매핑 상세"},
                    {"kind": "topics", "title": "탐구보고서 기획서 상세 제안", "slice": (0, 4)},
                    {"kind": "interviews", "title": "면접 답변 초안", "category": "전공 적합성"},
                    {"kind": "rewrites", "title": "자기소개/세특 보완 문장 샘플"},
                    {"kind": "action_plan", "title": "생기부 전체 리디자인 전략"},
                    {"kind": "appendix", "title": "컨설턴트 검증 부록"},
                ]
            )
    while len(pages) < target_pages:
        pages.append({"kind": "action_plan", "title": "추가 실행 전략"})
    return pages


def _render_structured_page(
    *,
    page: dict[str, Any],
    page_index: int,
    report_payload: dict[str, Any],
    doc: SimpleDocTemplate,
    style_tokens: dict[str, Any],
    font_name: str,
    font_bold: str,
    color_tokens: dict[str, Any],
    render_hints: dict[str, Any],
) -> list[Any]:
    kind = str(page.get("kind") or "")
    title = str(page.get("title") or "Report")
    flowables: list[Any] = []
    if kind == "cover":
        return _render_structured_cover(
            report_payload=report_payload,
            doc=doc,
            style_tokens=style_tokens,
            font_name=font_name,
            font_bold=font_bold,
            color_tokens=color_tokens,
            render_hints=render_hints,
        )

    flowables.append(Paragraph(_escape(title), style_tokens["h2"]))
    mode_label = str(report_payload.get("report_mode_label") or render_hints.get("report_mode_label") or "Premium Report")
    flowables.append(Paragraph(_escape(f"{mode_label} | Uni-Foli Admissions Diagnosis"), style_tokens["subtitle"]))
    flowables.append(Spacer(1, 5))

    if kind == "summary":
        flowables.extend(_summary_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "dashboard":
        flowables.extend(_dashboard_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "record_structure":
        flowables.extend(_record_structure_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "subject_table":
        flowables.extend(_subject_table_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "subject_cards":
        flowables.extend(_subject_card_flowables(report_payload, doc, style_tokens, color_tokens, page.get("slice")))
    elif kind == "competency":
        flowables.extend(_competency_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "network":
        flowables.extend(_network_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "growth":
        flowables.extend(_growth_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "strengths":
        flowables.extend(_strength_risk_flowables(report_payload, doc, style_tokens, color_tokens, strengths=True))
    elif kind == "risks":
        flowables.extend(_strength_risk_flowables(report_payload, doc, style_tokens, color_tokens, strengths=False))
    elif kind == "topics":
        flowables.extend(_topics_flowables(report_payload, doc, style_tokens, color_tokens, page.get("slice")))
    elif kind == "avoid":
        flowables.extend(_avoid_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "rewrites":
        flowables.extend(_rewrite_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "interviews":
        flowables.extend(_interview_flowables(report_payload, doc, style_tokens, color_tokens, str(page.get("category") or "")))
    elif kind == "roadmap":
        flowables.extend(_roadmap_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "appendix":
        flowables.extend(_appendix_flowables(report_payload, doc, style_tokens, color_tokens))
    else:
        flowables.extend(_action_plan_flowables(report_payload, doc, style_tokens, color_tokens))

    if len(flowables) < 5:
        flowables.append(
            _structured_card(
                "밀도 보강 메모",
                "이 페이지는 핵심 판단, 근거, 다음 행동이 함께 보이도록 카드형 보조 분석을 추가했습니다.",
                doc.width,
                style_tokens,
                color_tokens,
                tone="action",
            )
        )
    return flowables


def _render_structured_cover(
    *,
    report_payload: dict[str, Any],
    doc: SimpleDocTemplate,
    style_tokens: dict[str, Any],
    font_name: str,
    font_bold: str,
    color_tokens: dict[str, Any],
    render_hints: dict[str, Any],
) -> list[Any]:
    mode_label = str(report_payload.get("report_mode_label") or render_hints.get("report_mode_label") or "Premium Report")
    context = str(report_payload.get("student_target_context") or "")
    student = _extract_context_value(context, ["학생:", "?숈깮:"]) or "학생명 비공개"
    if "미확인" in student or "誘" in student:
        student = "학생명 비공개"
    target_major = _extract_context_value(context, ["목표 전공:", "목표 학과:", "紐⑺몴 ?꾧났:"]) or "목표 학과 미설정"
    target_university = _extract_context_value(context, ["목표 대학:", "紐⑺몴 ???"]) or "목표 대학 미설정"
    confidence = int(round(float(render_hints.get("analysis_confidence_score", 0.72)) * 100))
    verdict = str(render_hints.get("one_line_verdict") or "학생부 전체 기록을 전공 적합성, 탐구 심화도, 연결망 관점에서 진단했습니다.")
    rows = [
        ["학생", student],
        ["목표", f"{target_university} / {target_major}"],
        ["리포트 모드", mode_label],
        ["진단일", datetime.now(timezone.utc).strftime("%Y-%m-%d")],
        ["종합 판정", _truncate_plain(verdict, 90)],
        ["분석 신뢰도", f"{confidence}%"],
    ]
    table = _structured_table(rows, doc.width, [0.24, 0.76], style_tokens, font_name, font_bold, color_tokens)
    return [
        Spacer(1, 20),
        Paragraph("UNI-FOLI CONSULTANT DIAGNOSIS", style_tokens["cover_label"]),
        Paragraph(_escape(str(report_payload.get("title") or "입시 진단 프리미엄 리포트")), style_tokens["cover_title"]),
        Paragraph(_escape(str(report_payload.get("subtitle") or "학생부 전체 연결망 기반 고급 입시 컨설팅 리포트")), style_tokens["cover_subtitle"]),
        Spacer(1, 18),
        table,
        Spacer(1, 16),
        _structured_card(
            "진단 범위",
            "이 보고서는 교과 세특, 창체, 독서, 진로, 행동특성, 탐구 활동이 목표 학과 서사로 연결되는 방식을 분석합니다.",
            doc.width,
            style_tokens,
            color_tokens,
            tone="evidence",
        ),
        Spacer(1, 10),
        _chip_row(["핵심 키워드: 전공 적합성", "세특 밀도", "서사 연결망"], doc.width, style_tokens, color_tokens),
    ]


def _summary_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    executive = premium.get("executive_summary") if isinstance(premium.get("executive_summary"), dict) else {}
    if executive:
        strengths = [str(item) for item in executive.get("top_strengths", [])[:3]]
        risks = [str(item) for item in executive.get("top_risks", [])[:3]]
        actions = [str(item) for item in executive.get("first_actions", [])[:5]]
        return [
            _structured_card("전체 인상", _truncate_plain(str(executive.get("overall_judgement") or ""), 420), doc.width, style_tokens, color_tokens, tone="evidence"),
            Spacer(1, 8),
            _two_column_cards("가장 강한 강점 3개", strengths[:3], "가장 위험한 약점 3개", risks[:3], doc, style_tokens, color_tokens),
            Spacer(1, 8),
            _structured_card("최우선 보완 액션", " / ".join(actions) or "대표 활동 3개를 먼저 정리하세요.", doc.width, style_tokens, color_tokens, tone="action"),
        ]
    sections = [item for item in report_payload.get("sections", []) if isinstance(item, dict)]
    executive = next((item for item in sections if str(item.get("id")) == "executive_verdict"), None)
    body = str((executive or {}).get("body_markdown") or report_payload.get("final_consultant_memo") or "")
    strengths = _first_lines(report_payload.get("sections"), "strength_analysis", 3) or ["근거가 있는 강점을 전공 역량 언어로 재정리할 수 있습니다."]
    risks = _first_lines(report_payload.get("sections"), "weakness_risk_analysis", 3) or ["산출물과 과정 기록이 약하면 면접에서 추가 질문을 받을 수 있습니다."]
    actions = [item.get("message") for item in report_payload.get("quality_gates", []) if isinstance(item, dict)]
    return [
        _structured_card("전체 인상", _truncate_plain(body, 420), doc.width, style_tokens, color_tokens, tone="evidence"),
        Spacer(1, 8),
        _two_column_cards("가장 강한 강점 3개", strengths[:3], "가장 위험한 약점 3개", risks[:3], doc, style_tokens, color_tokens),
        Spacer(1, 8),
        _structured_card("최우선 보완 액션", " / ".join(str(item) for item in actions[:5]) or "탐구 산출물, 세특 문장, 면접 답변을 같은 질문으로 연결하세요.", doc.width, style_tokens, color_tokens, tone="action"),
    ]


def _dashboard_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    premium_dashboard = [item for item in premium.get("score_dashboard", []) if isinstance(item, dict)]
    blocks = premium_dashboard or [item for item in report_payload.get("score_blocks", []) if isinstance(item, dict)]
    if not blocks:
        blocks = [
            {"label": "종합 점수", "score": 72, "interpretation": "현재 기록의 강점은 보이지만 산출물 근거 보강이 필요합니다."},
            {"label": "전공 적합성", "score": 68, "interpretation": "목표 학과와 직접 연결되는 질문을 강화해야 합니다."},
            {"label": "탐구 심화도", "score": 64, "interpretation": "방법과 결과 해석을 더 구체화할 필요가 있습니다."},
        ]
    rows = [["항목", "점수", "점수 막대", "해석"]]
    for block in blocks[:8]:
        score = _safe_int(block.get("score"), 0)
        rows.append([
            str(block.get("axis") or block.get("label") or block.get("key") or "-"),
            f"{score}",
            _score_bar_text(score),
            _truncate_plain(str(block.get("interpretation") or block.get("improvement") or block.get("next_best_action") or "-"), 80),
        ])
    table = _structured_table(rows, doc.width, [0.22, 0.10, 0.22, 0.46], style_tokens, font_name, font_bold, color_tokens)
    return [table, Spacer(1, 8), _structured_card("위험도 해석", "점수는 합격 가능성 예측이 아니라 학생부 근거의 밀도, 과정성, 전공 연결성, 면접 방어력을 종합한 컨설팅 지표입니다.", doc.width, style_tokens, color_tokens, tone="warning")]


def _record_structure_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    evidence_map = [item for item in premium.get("evidence_map", []) if isinstance(item, dict)]
    if evidence_map:
        cards = []
        for item in evidence_map[:8]:
            title = f"{item.get('grade') or '학년 확인'} | {item.get('subject_or_activity') or item.get('section') or '근거'}"
            body = (
                f"원문 요약: {_truncate_plain(str(item.get('raw_summary') or '-'), 92)}\n"
                f"전공 의미: {_truncate_plain(str(item.get('major_relevance') or '-'), 92)}\n"
                f"보완 포인트: {_truncate_plain(str(item.get('risk') or '-'), 72)}"
            )
            cards.append((title, body))
        return [_card_grid(cards, doc, style_tokens, color_tokens)]
    intelligence = report_payload.get("diagnosis_intelligence") if isinstance(report_payload.get("diagnosis_intelligence"), dict) else {}
    metrics = intelligence.get("evidence_metrics") if isinstance(intelligence.get("evidence_metrics"), dict) else {}
    cards = [
        ("기록이 풍부한 영역", ", ".join(str(item) for item in intelligence.get("strong_sections_to_avoid_repeating", [])[:4]) or "교과/활동 근거 확인 필요"),
        ("입시적으로 비어 보이는 영역", ", ".join(str(item) for item in intelligence.get("weak_sections_to_complement", [])[:4]) or "누락 섹션은 원문 재확인 필요"),
        ("근거 분산", f"고유 근거 {metrics.get('unique_anchor_count', 0)}개, 페이지 분산 {metrics.get('unique_page_count', 0)}쪽"),
        ("보완 방향", "세특, 창체, 독서, 진로가 같은 질문으로 이어지도록 연결 문장을 추가합니다."),
    ]
    return [_card_grid(cards, doc, style_tokens, color_tokens)]


def _subject_table_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> list[Any]:
    subjects = [item for item in report_payload.get("subject_specialty_analyses", []) if isinstance(item, dict)]
    rows = [["과목명", "핵심 기록 요약", "강점", "약점", "점수", "개선 방향", "전공 연결"]]
    for item in subjects[:8]:
        rows.append([
            str(item.get("subject") or "-"),
            _truncate_plain(str(item.get("core_record_summary") or "-"), 58),
            _truncate_plain(" / ".join(str(v) for v in item.get("strengths", [])[:1]), 42),
            _truncate_plain(" / ".join(str(v) for v in item.get("weaknesses", [])[:1]), 42),
            str(item.get("score") or "-"),
            _truncate_plain(str(item.get("recommended_follow_up") or "-"), 52),
            _truncate_plain(str(item.get("major_connection") or "-"), 54),
        ])
    return [_structured_table(rows, doc.width, [0.10, 0.20, 0.13, 0.13, 0.07, 0.18, 0.19], style_tokens, font_name, font_bold, color_tokens)]


def _subject_card_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], slice_value: Any) -> list[Any]:
    subjects = [item for item in report_payload.get("subject_specialty_analyses", []) if isinstance(item, dict)]
    start, end = _slice_tuple(slice_value, 0, 4)
    selected = subjects[start:end] or subjects[:4]
    cards = []
    for item in selected:
        cards.append(
            (
                f"{item.get('subject')} | {item.get('score')}점 | {item.get('level')}",
                f"요약: {_truncate_plain(str(item.get('core_record_summary') or '-'), 95)}\n"
                f"입시적 의미: {_truncate_plain(str(item.get('admissions_meaning') or '-'), 95)}\n"
                f"후속 탐구: {_truncate_plain(str(item.get('recommended_follow_up') or '-'), 95)}",
            )
        )
    return [_card_grid(cards, doc, style_tokens, color_tokens)]


def _competency_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    matrix = [item for item in premium.get("major_competency_matrix", []) if isinstance(item, dict)]
    if matrix:
        rows = [["전공역량", "점수", "생기부 근거", "보완 방향"]]
        for item in matrix[:8]:
            rows.append([
                str(item.get("competency") or "-"),
                f"{_safe_int(item.get('score'), 0)}",
                _truncate_plain(str(item.get("evidence") or "근거 확인 필요"), 72),
                _truncate_plain(str(item.get("improvement") or "-"), 74),
            ])
        return [_structured_table(rows, doc.width, [0.18, 0.08, 0.38, 0.36], style_tokens, font_name, font_bold, color_tokens)]
    subjects = [item for item in report_payload.get("subject_specialty_analyses", []) if isinstance(item, dict)]
    competencies = ["공간 이해력", "구조적 사고", "수학/물리 기반 분석력", "미적 감각과 표현력", "도시/사회/환경 문제의식", "탐구 설계 능력", "협업 및 커뮤니케이션", "자기주도 문제 해결력"]
    rows = [["핵심 역량", "연결 근거", "근거 강도", "부족한 증거", "보완 활동", "면접 가능성"]]
    for idx, competency in enumerate(competencies):
        item = subjects[idx % max(1, len(subjects))] if subjects else {}
        rows.append([
            competency,
            _truncate_plain(str(item.get("core_record_summary") or "근거 확인 필요"), 46),
            str(item.get("level") or "보통"),
            "산출물/방법/한계 문장",
            _truncate_plain(str(item.get("recommended_follow_up") or "후속 탐구 설계"), 42),
            "높음" if idx < 5 else "보통",
        ])
    return [_structured_table(rows, doc.width, [0.15, 0.24, 0.10, 0.16, 0.23, 0.12], style_tokens, font_name, font_bold, color_tokens)]


def _network_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    premium_network = [item for item in premium.get("narrative_network", []) if isinstance(item, dict)]
    if premium_network:
        network_payload = premium_network[0]
        rows = [["연결", "강도", "해석"]]
        for edge in [item for item in network_payload.get("edges", []) if isinstance(item, dict)][:10]:
            rows.append([
                f"{edge.get('from') or '-'} -> {edge.get('to') or '-'}",
                _network_strength_label(str(edge.get("strength") or "-")),
                _truncate_plain(str(edge.get("rationale") or "-"), 82),
            ])
        node_text = " / ".join(str(item) for item in network_payload.get("nodes", [])[:10])
        return [
            _structured_card("중심 주제", str(network_payload.get("central_node") or "전공 적합성 연결망"), doc.width, style_tokens, color_tokens, tone="evidence"),
            Spacer(1, 7),
            _structured_card("네트워크 노드", node_text, doc.width, style_tokens, color_tokens, tone="action"),
            Spacer(1, 7),
            _structured_table(rows, doc.width, [0.34, 0.12, 0.54], style_tokens, font_name, font_bold, color_tokens),
        ]
    network = report_payload.get("record_network") if isinstance(report_payload.get("record_network"), dict) else {}
    nodes = [item for item in network.get("nodes", []) if isinstance(item, dict)]
    edges = [item for item in network.get("edges", []) if isinstance(item, dict)]
    rows = [["연결", "강도", "해석"]]
    for edge in edges[:10]:
        rows.append([
            str(edge.get("label") or "-"),
            _network_strength_label(str(edge.get("strength") or "-")),
            _truncate_plain(str(edge.get("rationale") or "-"), 82),
        ])
    node_text = " / ".join(str(item.get("label") or "") for item in nodes[:8])
    return [
        _structured_card("중심 주제", str(network.get("central_theme") or "전공 적합성 연결망"), doc.width, style_tokens, color_tokens, tone="evidence"),
        Spacer(1, 7),
        _structured_card("네트워크 노드", node_text, doc.width, style_tokens, color_tokens, tone="action"),
        Spacer(1, 7),
        _structured_table(rows, doc.width, [0.26, 0.14, 0.60], style_tokens, font_name, font_bold, color_tokens),
        Spacer(1, 8),
        _card_grid(
            [
                ("중심 주제 존재 여부", "동일 관심사가 과목과 활동에서 반복되는지 확인합니다."),
                ("학년 간 흐름", "관심 출발, 개념 심화, 전공 수렴 순서로 재배열합니다."),
                ("과목 간 융합성", "인문 과목은 문제의식, 이공 과목은 검증 도구로 역할을 나눕니다."),
                ("억지 연결 위험도", "산출물이 없는 연결은 강력 추천이 아니라 확장 가능 주제로 낮춰 표기합니다."),
            ],
            doc,
            style_tokens,
            color_tokens,
        ),
    ]


def _growth_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    timeline = [item for item in premium.get("growth_timeline", []) if isinstance(item, dict)]
    if timeline:
        cards = []
        for item in timeline[:3]:
            core = " / ".join(str(value) for value in item.get("core_activities", [])[:2])
            competencies = " / ".join(str(value) for value in item.get("visible_competencies", [])[:2])
            cards.append(
                (
                    f"{item.get('grade')}: {item.get('role')}",
                    f"핵심 활동: {core or '-'}\n드러나는 역량: {competencies or '-'}\n다음 흐름: {item.get('next_flow') or '-'}",
                )
            )
        return [_card_grid(cards, doc, style_tokens, color_tokens)]
    grade_stories = [item for item in report_payload.get("grade_story_analyses", []) if isinstance(item, dict)]
    cards: list[tuple[str, str]] = []
    for item in grade_stories[:3]:
        title = f"{item.get('grade_label')}: {item.get('stage_role')}"
        core = " / ".join(str(value) for value in item.get("core_activities", [])[:2])
        competencies = " / ".join(str(value) for value in item.get("visible_competencies", [])[:2])
        weak = " / ".join(str(value) for value in item.get("weak_connections", [])[:2])
        body = (
            f"핵심 활동: {core or '-'}\n"
            f"드러나는 역량: {competencies or '-'}\n"
            f"부족한 연결: {weak or '-'}\n"
            f"다음 흐름: {item.get('next_flow') or '-'}"
        )
        cards.append((title, body))
    if not cards:
        grade_profile = report_payload.get("render_hints", {}).get("grade_profile") if isinstance(report_payload.get("render_hints"), dict) else {}
        current_grade = _safe_int((grade_profile or {}).get("current_grade"), 0) if isinstance(grade_profile, dict) else 0
        if current_grade == 1:
            cards = [
                ("1학년: 현재 관심의 출발점", "전공을 단정하기보다 문제의식, 독서, 발표 경험을 넓게 확보합니다.\n다음 흐름: 2학년에 같은 관심사를 교과 개념과 작은 산출물로 연결합니다."),
                ("2학년: 다음 심화 설계", "아직 기록이 없을 수 있으므로 로드맵 관점으로 표시합니다.\n다음 흐름: 탐구 질문, 방법, 결과 해석이 남는 활동을 설계합니다."),
                ("3학년: 최종 수렴 계획", "장기 목표 카드입니다.\n다음 흐름: 면접에서 설명 가능한 전공 서사로 정리합니다."),
            ]
        elif current_grade == 2:
            cards = [
                ("1학년: 이전 근거 회수", "초기 관심과 독서/발표 경험을 현재 탐구의 출발점으로 회수합니다."),
                ("2학년: 현재 개념적 심화", "수업 개념을 탐구 질문으로 바꾸고 산출물과 결과 해석을 남깁니다."),
                ("3학년: 다음 전공 수렴", "목표 학과 면접 답변과 최종 탐구로 이어질 연결 문장을 준비합니다."),
            ]
        elif current_grade == 3:
            cards = [
                ("1학년: 출발점 근거 정리", "초기 관심을 현재 전공 선택의 배경으로 압축합니다."),
                ("2학년: 심화 과정 회수", "개념 심화와 탐구 과정성을 보여주는 근거를 선별합니다."),
                ("3학년: 현재 전공 수렴", "새 활동보다 기존 기록의 역할, 결과 해석, 한계를 면접 답변으로 정리합니다."),
            ]
        else:
            cards = [
                ("1학년: 관심의 출발점", "전공 키워드를 직접 선언하기보다 문제의식, 독서, 발표 경험에서 관심의 씨앗을 찾습니다."),
                ("2학년: 개념적 심화", "수업 개념을 탐구 질문으로 바꾸고 산출물과 결과 해석을 남기는 단계입니다."),
                ("3학년: 전공 방향 수렴", "교과-창체-독서-진로 기록을 목표 학과 언어로 모아 면접 답변 구조로 정리합니다."),
            ]
    return [_card_grid(cards, doc, style_tokens, color_tokens)]


def _strength_risk_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], *, strengths: bool) -> list[Any]:
    section_id = "strength_analysis" if strengths else "weakness_risk_analysis"
    lines = _first_lines(report_payload.get("sections"), section_id, 5)
    if not lines:
        lines = [
            "학생부 근거를 전공 역량 언어로 바꾸는 작업이 필요합니다.",
            "면접에서 설명 가능한 활동 과정과 산출물 근거를 보강해야 합니다.",
            "동일 키워드 반복보다 질문의 진화가 보이도록 재배열해야 합니다.",
            "교과와 창체의 연결 문장을 추가하면 서사 응집도가 올라갑니다.",
            "추가 검증이 필요한 기록은 보수적으로 표기해야 합니다.",
        ]
    cards = []
    for idx, line in enumerate(lines[:5], start=1):
        title = f"{'강점' if strengths else '리스크'} {idx}"
        detail = (
            f"근거 요약: {_truncate_plain(line, 95)}\n"
            "입시적 의미: 목표 학과 관점에서 설명 가능한 역량 언어로 전환합니다.\n"
            "면접 활용: 활동 배경, 본인 역할, 결과 해석 순서로 답변합니다."
        )
        cards.append((title, detail))
    return [_card_grid(cards, doc, style_tokens, color_tokens)]


def _topics_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], slice_value: Any) -> list[Any]:
    premium = _premium_analysis(report_payload)
    premium_topics = [item for item in premium.get("recommended_research_topics", []) if isinstance(item, dict)]
    topics = premium_topics or [item for item in report_payload.get("research_topics", []) if isinstance(item, dict)]
    start, end = _slice_tuple(slice_value, 0, 6)
    selected = topics[start:end] or topics[:6]
    featured = selected[:2]
    compact = selected[2:8]
    flowables: list[Any] = []
    for topic in featured:
        question = topic.get("research_question") or topic.get("inquiry_question")
        admission_value = topic.get("admission_value") or topic.get("classification")
        flowables.append(
            _structured_card(
                f"{topic.get('priority') or ''}. {topic.get('title')} ({admission_value or '추천'})",
                f"질문: {question}\n방법: {topic.get('method')}\n산출물: {topic.get('expected_output')}\n면접 활용: {topic.get('interview_value') or topic.get('interview_use')}",
                doc.width,
                style_tokens,
                color_tokens,
                tone="evidence",
            )
        )
        flowables.append(Spacer(1, 6))
    if compact:
        flowables.append(_card_grid([(str(item.get("title")), str(item.get("interview_value") or item.get("interview_use"))) for item in compact[:6]], doc, style_tokens, color_tokens))
    return flowables


def _avoid_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    cards = [
        ("전공 키워드만 붙인 주제", "위험한 이유: 실제 탐구 과정 없이 전공 관련성만 선언하면 억지 연결로 보입니다.\n안전한 대체: 학생부에 있는 교과 개념과 산출물을 먼저 두고 전공 문제로 확장합니다."),
        ("결과를 과장하는 주제", "위험한 이유: 검증하지 않은 효과를 단정하면 면접에서 근거 공격을 받습니다.\n안전한 대체: 비교 기준과 한계를 분명히 둔 소규모 탐구로 조정합니다."),
        ("활동 반복형 요약 주제", "위험한 이유: 기존 세특 문장을 다시 쓰는 수준이면 심화도가 낮아 보입니다.\n안전한 대체: 같은 활동에서 새 변수, 새 자료, 새 해석을 추가합니다."),
    ]
    return [_card_grid(cards, doc, style_tokens, color_tokens)]


def _rewrite_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    examples = [item for item in report_payload.get("before_after_examples", []) if isinstance(item, dict)]
    cards = []
    for item in examples[:8]:
        cards.append(
            (
                "Before/After",
                f"기존 요약: {_truncate_plain(str(item.get('original_summary') or '-'), 72)}\n"
                f"문제점: {_truncate_plain(str(item.get('problem') or '-'), 72)}\n"
                f"개선 문장: {_truncate_plain(str(item.get('improved_sentence') or '-'), 98)}\n"
                f"과장 위험: {_truncate_plain(str(item.get('exaggeration_risk') or '-'), 72)}",
            )
        )
    return [_card_grid(cards, doc, style_tokens, color_tokens)]


def _interview_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], category: str) -> list[Any]:
    premium = _premium_analysis(report_payload)
    premium_questions = [item for item in premium.get("interview_questions", []) if isinstance(item, dict)]
    questions = premium_questions or [item for item in report_payload.get("interview_questions", []) if isinstance(item, dict)]
    selected = [item for item in questions if str(item.get("category")) == category] or questions[:5]
    cards = []
    for item in selected[:6]:
        cards.append(
            (
                str(item.get("question") or "면접 질문"),
                f"의도: {_truncate_plain(str(item.get('intent') or '-'), 70)}\n"
                f"답변 프레임: {_truncate_plain(str(item.get('answer_frame') or '-'), 85)}\n"
                f"연결 근거: {_truncate_plain(str(item.get('connected_evidence') or '-'), 80)}\n"
                f"피해야 할 답변: {_truncate_plain(str(item.get('avoid') or '-'), 70)}",
            )
        )
    while len(cards) < 6:
        cards.append(
            (
                "답변 구조 보강",
                "학생부 근거 1개를 고르고 활동 배경 - 선택한 개념 - 본인 역할 - 결과 해석 - 다음 질문 순서로 60초 답변을 만듭니다.",
            )
        )
    return [_card_grid(cards, doc, style_tokens, color_tokens)]


def _roadmap_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> list[Any]:
    roadmap = [item for item in report_payload.get("roadmap", []) if isinstance(item, dict)]
    rows = [["단계", "목표", "해야 할 일", "산출물/완료 기준"]]
    for item in roadmap[:3]:
        rows.append([
            str(item.get("horizon") or "-"),
            str(item.get("title") or "-"),
            _truncate_plain(" / ".join(str(v) for v in item.get("actions", [])[:3]), 95),
            _truncate_plain(" / ".join(str(v) for v in item.get("success_signals", [])[:2]), 80),
        ])
    return [_structured_table(rows, doc.width, [0.13, 0.22, 0.40, 0.25], style_tokens, font_name, font_bold, color_tokens)]


def _action_plan_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    action_items = [item for item in premium.get("action_plan", []) if isinstance(item, dict)]
    if action_items:
        cards = [
            (
                f"{item.get('priority')}. {item.get('action')}",
                f"산출물: {item.get('output') or '실행 결과물'}",
            )
            for item in action_items[:8]
        ]
        return [_card_grid(cards, doc, style_tokens, color_tokens)]
    gates = [item for item in report_payload.get("quality_gates", []) if isinstance(item, dict)]
    cards = []
    for idx, gate in enumerate(gates[:6], start=1):
        cards.append((f"{idx}. {gate.get('label')}", str(gate.get("message") or "")))
    if not cards:
        cards = [("1. 세특 보완", "질문-방법-결과-한계가 드러나는 문장으로 고칩니다."), ("2. 탐구 산출물", "보고서와 발표 자료를 면접 답변 근거로 정리합니다.")]
    return [_card_grid(cards, doc, style_tokens, color_tokens)]


def _appendix_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    gates = [item for item in report_payload.get("quality_gates", []) if isinstance(item, dict)]
    cards = []
    for gate in gates:
        status = "충족" if gate.get("passed") else "보완 권장"
        cards.append((f"{gate.get('label')} - {status}", str(gate.get("message") or "")))
    cards.append(("표기 원칙", "확인된 근거, 가능성이 높은 해석, 추가 확인이 필요한 항목을 자연어로 구분해 과장 위험을 줄였습니다."))
    return [_card_grid(cards[:8], doc, style_tokens, color_tokens)]


def _structured_card(
    title: str,
    body: str,
    width: float,
    style_tokens: dict[str, Any],
    color_tokens: dict[str, Any],
    *,
    tone: str = "panel",
) -> Table:
    tone_map = {
        "evidence": ("line_evidence", "surface_evidence"),
        "warning": ("line_warning", "surface_warning"),
        "action": ("line_action", "surface_action"),
        "panel": ("line_soft", "surface_panel"),
    }
    border_key, fill_key = tone_map.get(tone, tone_map["panel"])
    content = [
        Paragraph(_escape(title), style_tokens["meta_strong"]),
        Paragraph(_escape(body).replace("\n", "<br/>"), style_tokens["meta"]),
    ]
    table = Table([[content]], colWidths=[width], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _hex(color_tokens.get(fill_key), "#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.7, _hex(color_tokens.get(border_key), "#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _card_grid(cards: list[tuple[str, str]], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> Table:
    cleaned = cards or [("보완 메모", "추가 원문 확인 후 세부 카드가 채워집니다.")]
    rows: list[list[Any]] = []
    col_width = (doc.width - 8) / 2
    for idx in range(0, len(cleaned), 2):
        row_cards = cleaned[idx: idx + 2]
        row = [
            _structured_card(title, body, col_width, style_tokens, color_tokens, tone="panel")
            for title, body in row_cards
        ]
        if len(row) == 1:
            row.append("")
        rows.append(row)
    table = Table(rows, colWidths=[col_width, col_width], hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return table


def _two_column_cards(left_title: str, left_items: list[str], right_title: str, right_items: list[str], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> Table:
    left = "\n".join(f"- {item}" for item in left_items)
    right = "\n".join(f"- {item}" for item in right_items)
    return _card_grid([(left_title, left), (right_title, right)], doc, style_tokens, color_tokens)


def _structured_table(rows: list[list[Any]], width: float, fractions: list[float], style_tokens: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> Table:
    prepared: list[list[Any]] = []
    for row in rows:
        prepared.append([Paragraph(_escape(str(cell)), style_tokens["meta_strong"] if len(prepared) == 0 else style_tokens["meta"]) for cell in row])
    table = Table(prepared, colWidths=[width * fraction for fraction in fractions], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _hex(color_tokens.get("surface_panel"), "#F3F4F6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), _hex(color_tokens.get("text_primary"), "#111827")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_hex(color_tokens.get("surface_soft"), "#FBFCFE"), _hex(color_tokens.get("surface_panel"), "#F3F4F6")]),
                ("GRID", (0, 0), (-1, -1), 0.35, _hex(color_tokens.get("line_soft"), "#E5E7EB")),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTNAME", (0, 1), (-1, -1), font_name),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _chip_row(labels: list[str], width: float, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> Table:
    col_width = width / max(1, len(labels))
    table = Table([[Paragraph(_escape(label), style_tokens["meta_strong"]) for label in labels]], colWidths=[col_width] * len(labels))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _hex(color_tokens.get("surface_panel"), "#F3F4F6")),
                ("BOX", (0, 0), (-1, -1), 0.5, _hex(color_tokens.get("premium_gold"), "#C9A227")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, _hex(color_tokens.get("line_soft"), "#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _first_lines(sections_value: Any, section_id: str, limit: int) -> list[str]:
    sections = [item for item in sections_value or [] if isinstance(item, dict)]
    section = next((item for item in sections if str(item.get("id")) == section_id), None)
    text = str((section or {}).get("body_markdown") or "")
    lines = []
    for line in _markdown_to_lines(text):
        cleaned = line.strip().lstrip("-").strip()
        if cleaned:
            lines.append(cleaned)
        if len(lines) >= limit:
            break
    return lines


def _extract_context_value(context: str, prefixes: list[str]) -> str | None:
    for prefix in prefixes:
        if prefix in context:
            return context.split(prefix, 1)[1].split("|", 1)[0].strip()
    return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _score_bar_text(score: int) -> str:
    clamped = max(0, min(100, int(score)))
    return f"{clamped}점 / 100"


def _network_strength_label(value: str) -> str:
    mapping = {
        "strong": "강함",
        "moderate": "보통",
        "weak": "약함",
        "artificial": "보완 필요",
        "강함": "강함",
        "보통": "보통",
        "약함": "약함",
        "보완 필요": "보완 필요",
    }
    return mapping.get(str(value or "").strip().lower(), str(value or "-"))


def _premium_analysis(report_payload: dict[str, Any]) -> dict[str, Any]:
    intelligence = report_payload.get("diagnosis_intelligence")
    if isinstance(intelligence, dict):
        premium = intelligence.get("premium_analysis_json")
        if isinstance(premium, dict):
            return premium
    render_hints = report_payload.get("render_hints")
    if isinstance(render_hints, dict):
        nested_intelligence = render_hints.get("diagnosis_intelligence")
        if isinstance(nested_intelligence, dict):
            premium = nested_intelligence.get("premium_analysis_json")
            if isinstance(premium, dict):
                return premium
    return {}


def _public_display_text(value: Any) -> str:
    text = str(value or "")
    text = _PUBLIC_INTERNAL_TOKEN_RE.sub("", text)
    text = re.sub(r"\s*\|\s*\|\s*", " | ", text)
    text = re.sub(r"^\s*\|\s*|\s*\|\s*$", "", text).strip(" -|")
    return text


def _slice_tuple(value: Any, default_start: int, default_end: int) -> tuple[int, int]:
    if isinstance(value, tuple) and len(value) == 2:
        return int(value[0]), int(value[1])
    if isinstance(value, list) and len(value) == 2:
        return int(value[0]), int(value[1])
    return default_start, default_end


def _build_style_tokens(*, design_contract: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> dict[str, Any]:
    styles = getSampleStyleSheet()
    typography = design_contract.get("typography", {}) if isinstance(design_contract.get("typography"), dict) else {}
    spacing = design_contract.get("spacing", {}) if isinstance(design_contract.get("spacing"), dict) else {}
    body_font_size = max(
        11.0,
        float(typography.get("body", {}).get("font_size", 11.0) if isinstance(typography.get("body"), dict) else 11.0),
    )
    body_leading = max(
        16.0,
        float(typography.get("body", {}).get("leading", 16.0) if isinstance(typography.get("body"), dict) else 16.0),
    )
    common_wrap = {
        "wordWrap": "CJK",
        "splitLongWords": True,
    }
    title_style = ParagraphStyle(
        "DiagnosisCoverTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=float(typography.get("cover_title", {}).get("font_size", 26) if isinstance(typography.get("cover_title"), dict) else 26),
        leading=float(typography.get("cover_title", {}).get("leading", 32) if isinstance(typography.get("cover_title"), dict) else 32),
        textColor=_hex(color_tokens.get("brand_primary"), "#1E3A5F"),
        alignment=TA_LEFT,
        spaceAfter=10,
        **common_wrap,
    )
    subtitle_style = ParagraphStyle(
        "DiagnosisCoverSubtitle",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=max(11.2, float(typography.get("cover_subtitle", {}).get("font_size", 11.2) if isinstance(typography.get("cover_subtitle"), dict) else 11.2)),
        leading=max(16.0, float(typography.get("cover_subtitle", {}).get("leading", 16.0) if isinstance(typography.get("cover_subtitle"), dict) else 16.0)),
        textColor=_hex(color_tokens.get("text_secondary"), "#334155"),
        alignment=TA_LEFT,
        spaceAfter=8,
        **common_wrap,
    )
    h2_style = ParagraphStyle(
        "DiagnosisHeading",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=max(17.0, float(typography.get("section_heading", {}).get("font_size", 17) if isinstance(typography.get("section_heading"), dict) else 17)),
        leading=max(22.0, float(typography.get("section_heading", {}).get("leading", 22) if isinstance(typography.get("section_heading"), dict) else 22)),
        textColor=_hex(color_tokens.get("brand_secondary"), "#2B4F7B"),
        spaceBefore=4,
        spaceAfter=6,
        **common_wrap,
    )
    h3_style = ParagraphStyle(
        "DiagnosisHeading3",
        parent=styles["Heading3"],
        fontName=font_bold,
        fontSize=11.8,
        leading=15.6,
        textColor=_hex(color_tokens.get("text_primary"), "#0F172A"),
        spaceAfter=4,
        **common_wrap,
    )
    body_style = ParagraphStyle(
        "DiagnosisBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=body_font_size,
        leading=body_leading,
        textColor=_hex(color_tokens.get("text_primary"), "#0F172A"),
        spaceAfter=float(spacing.get("paragraph_gap", 6)),
        **common_wrap,
    )
    bullet_style = ParagraphStyle(
        "DiagnosisBullet",
        parent=body_style,
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=float(spacing.get("list_item_gap", 4)),
        **common_wrap,
    )
    meta_style = ParagraphStyle(
        "DiagnosisMeta",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=max(9.4, float(typography.get("meta", {}).get("font_size", 9.4) if isinstance(typography.get("meta"), dict) else 9.4)),
        leading=max(13.2, float(typography.get("meta", {}).get("leading", 13.2) if isinstance(typography.get("meta"), dict) else 13.2)),
        textColor=_hex(color_tokens.get("text_muted"), "#526173"),
        alignment=TA_LEFT,
        **common_wrap,
    )
    meta_strong_style = ParagraphStyle(
        "DiagnosisMetaStrong",
        parent=meta_style,
        fontName=font_bold,
        textColor=_hex(color_tokens.get("text_secondary"), "#334155"),
        **common_wrap,
    )
    callout_style = ParagraphStyle(
        "DiagnosisCallout",
        parent=styles["BodyText"],
        fontName=font_bold,
        fontSize=10.4,
        leading=14.8,
        textColor=_hex(color_tokens.get("text_primary"), "#0F172A"),
        alignment=TA_CENTER,
        **common_wrap,
    )
    cover_label_style = ParagraphStyle(
        "DiagnosisCoverLabel",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=max(9.2, float(typography.get("cover_label", {}).get("font_size", 9.2) if isinstance(typography.get("cover_label"), dict) else 9.2)),
        leading=max(12.6, float(typography.get("cover_label", {}).get("leading", 12.6) if isinstance(typography.get("cover_label"), dict) else 12.6)),
        textColor=_hex(color_tokens.get("text_muted"), "#526173"),
        alignment=TA_LEFT,
        spaceAfter=3,
        **common_wrap,
    )
    meta_size = max(9.2, float(typography.get("meta", {}).get("font_size", 9.2) if isinstance(typography.get("meta"), dict) else 9.2))
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
            "meta_size": meta_size,
        },
        "spacing": {
            "cover_block_gap": float(spacing.get("cover_block_gap", 10)),
            "section_gap": float(spacing.get("section_gap", 8)),
            "paragraph_gap": float(spacing.get("paragraph_gap", 6)),
            "list_item_gap": float(spacing.get("list_item_gap", 4)),
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
    compact: bool = False,
) -> Table:
    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None

    def _score_bar(score: int | None) -> str:
        if score is None:
            return "점수 없음"
        clamped = max(0, min(100, score))
        return f"{clamped}점"

    if compact:
        rows = [["항목", "점수", "지표", "요약"]]
        for block in score_blocks:
            score = _to_int(block.get("score"))
            interpretation = str(block.get("interpretation") or "").strip()
            uncertainty = str(block.get("uncertainty_note") or "").strip()
            summary = interpretation or uncertainty or "-"
            summary = _truncate_plain(summary, 56)
            rows.append(
                [
                    _escape(str(block.get("label") or block.get("key") or "-")),
                    f"{score}점" if score is not None else "-",
                    _escape(_score_bar(score)),
                    _escape(summary),
                ]
            )
        table = Table(
            rows,
            colWidths=[doc.width * 0.24, doc.width * 0.12, doc.width * 0.22, doc.width * 0.42],
            repeatRows=1,
            hAlign="LEFT",
        )
    else:
        rows = [["항목", "점수", "지표", "해석", "검증 메모"]]
        for block in score_blocks:
            score = _to_int(block.get("score"))
            rows.append(
                [
                    _escape(str(block.get("label") or block.get("key") or "-")),
                    f"{score}점" if score is not None else "-",
                    _escape(_score_bar(score)),
                    _escape(_truncate_plain(str(block.get("interpretation") or "-"), 90)),
                    _escape(_truncate_plain(str(block.get("uncertainty_note") or "-"), 70)),
                ]
            )
        table = Table(
            rows,
            colWidths=[doc.width * 0.16, doc.width * 0.10, doc.width * 0.18, doc.width * 0.32, doc.width * 0.24],
            repeatRows=1,
            hAlign="LEFT",
        )
    table_font_size = max(9.2, style_tokens["typography"]["meta_size"])
    table_top_bottom_padding = style_tokens["spacing"]["list_item_gap"] + 1
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _hex(color_tokens.get("surface_panel"), "#F1F5F9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), _hex(color_tokens.get("text_primary"), "#0F172A")),
                ("GRID", (0, 0), (-1, -1), 0.35, _hex(color_tokens.get("line_soft"), "#D7DEE8")),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTNAME", (0, 1), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), table_font_size),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["table_cell_padding"]),
                ("RIGHTPADDING", (0, 0), (-1, -1), style_tokens["spacing"]["table_cell_padding"]),
                ("TOPPADDING", (0, 0), (-1, -1), table_top_bottom_padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), table_top_bottom_padding),
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


def _resolve_font_names() -> tuple[str, str]:
    for regular, bold in (
        ("HYSMyeongJo-Medium", "HYGothic-Medium"),
        ("HeiseiMin-W3", "HeiseiKakuGo-W5"),
    ):
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(regular))
            pdfmetrics.registerFont(UnicodeCIDFont(bold))
            return regular, bold
        except Exception:
            continue
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
                ("TOPPADDING", (0, 0), (-1, -1), max(4, padding - 1)),
                ("BOTTOMPADDING", (0, 0), (-1, -1), max(4, padding - 1)),
            ]
        )
    )
    return table


def _render_section_body(
    section: dict[str, Any],
    body_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
    *,
    section_id: str | None = None,
) -> list[Any]:
    lines = _markdown_to_lines(str(section.get("body_markdown") or ""))
    if not lines:
        return [Paragraph("내용이 아직 준비되지 않았습니다.", body_style)]
    line_caps = {
        "record_baseline_dashboard": 5,
        "student_evaluation_matrix": 8,
        "system_quality_reliability": 8,
        "recommended_report_directions": 10,
        "recommended_report_direction": 9,
        "weakness_risk_analysis": 9,
        "uncertainty_verification_note": 9,
        "evidence_cards": 7,
        "major_fit": 7,
        "major_fit_interpretation": 8,
    }
    max_lines = line_caps.get(str(section_id or "").strip(), 8)
    if len(lines) > max_lines:
        lines = [*lines[:max_lines], "- 본문 분량은 페이지 가독성을 위해 요약했습니다."]
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


def _truncate_plain(text: str, limit: int) -> str:
    stripped = " ".join(_public_display_text(text).replace("\n", " ").split())
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: max(1, limit - 3)].rstrip()}..."


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
    canvas.drawString(doc.leftMargin, height - 11, "유니폴리 진단 보고서")

    canvas.setStrokeColor(_hex(color_tokens.get("line_soft"), "#D7DEE8"))
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, 32, width - doc.rightMargin, 32)
    canvas.setFont(font_name, 8.3)
    canvas.setFillColor(_hex(color_tokens.get("text_muted"), "#526173"))
    canvas.drawString(doc.leftMargin, 18, "근거 중심 진단 리포트")
    canvas.drawRightString(width - doc.rightMargin, 18, f"{canvas.getPageNumber()} 페이지")
    canvas.restoreState()


def _section_semantic_badge(*, section_id: str, color_tokens: dict[str, Any]) -> dict[str, Any] | None:
    mapping = {
        "cover_title_summary": ("메타 정보", "line_soft", "surface_panel"),
        "record_baseline_dashboard": ("검증된 사실", "line_evidence", "surface_evidence"),
        "student_evaluation_matrix": ("검증된 사실", "line_evidence", "surface_evidence"),
        "system_quality_reliability": ("검증된 사실", "line_evidence", "surface_evidence"),
        "strength_analysis": ("검증된 사실", "line_evidence", "surface_evidence"),
        "section_by_section_diagnosis": ("검증된 사실", "line_evidence", "surface_evidence"),
        "evidence_cards": ("검증된 사실", "line_evidence", "surface_evidence"),
        "citation_appendix": ("검증된 사실", "line_evidence", "surface_evidence"),
        "major_fit_interpretation": ("추론 기반 해석", "line_inferred", "surface_inferred"),
        "interview_readiness": ("추론 기반 해석", "line_inferred", "surface_inferred"),
        "risk_analysis": ("불확실성·리스크", "line_warning", "surface_warning"),
        "weakness_risk_analysis": ("불확실성·리스크", "line_warning", "surface_warning"),
        "uncertainty_verification_note": ("불확실성·리스크", "line_warning", "surface_warning"),
        "executive_verdict": ("실행 지시", "line_action", "surface_action"),
        "recommended_report_directions": ("실행 지시", "line_action", "surface_action"),
        "recommended_report_direction": ("실행 지시", "line_action", "surface_action"),
        "roadmap": ("실행 지시", "line_action", "surface_action"),
    }
    config = mapping.get(section_id)
    if config is None:
        return None
    label, border_key, fill_key = config
    return {
        "label": label,
        "border_color": _hex(color_tokens.get(border_key), "#D7DEE8"),
        "fill_color": _hex(color_tokens.get(fill_key), "#F8FAFC"),
    }


def _support_status_label(value: str) -> str:
    normalized = value.strip().lower()
    mapping = {
        "verified": "검증됨",
        "supported": "근거 충분",
        "probable": "가능성 높음",
        "partial": "부분 검증",
        "needs_review": "검토 필요",
        "needs_verification": "검증 필요",
        "unsupported": "근거 부족",
    }
    return mapping.get(normalized, "확인 필요")


def _hex(value: Any, fallback: str) -> colors.Color:
    candidate = str(value or "").strip() or fallback
    try:
        return colors.HexColor(candidate)
    except Exception:
        return colors.HexColor(fallback)


def _escape(value: str) -> str:
    text = _public_display_text(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Dashboard premium renderer v4
# ---------------------------------------------------------------------------


class _DashboardDonutChart(Flowable):
    def __init__(
        self,
        *,
        score: int,
        total: int,
        width: float,
        height: float,
        color_tokens: dict[str, Any],
        font_name: str,
        font_bold: str,
        label: str = "종합 점수",
    ) -> None:
        super().__init__()
        self.score = max(0, min(total, int(score)))
        self.total = max(1, int(total))
        self.width = width
        self.height = height
        self.color_tokens = color_tokens
        self.font_name = font_name
        self.font_bold = font_bold
        self.label = label

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:  # noqa: N802
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        primary = _hex(self.color_tokens.get("brand_primary"), "#7C3AED")
        soft = _hex(self.color_tokens.get("surface_action"), "#EDE9FE")
        muted = _hex(self.color_tokens.get("text_muted"), "#6B7280")
        text = _hex(self.color_tokens.get("text_primary"), "#111827")

        canvas.setFillColor(colors.white)
        canvas.setStrokeColor(_hex(self.color_tokens.get("line_soft"), "#E5E7EB"))
        canvas.roundRect(0, 0, self.width, self.height, 12, stroke=1, fill=1)

        cx = self.width / 2
        cy = self.height / 2 + 8
        radius = min(self.width, self.height) * 0.29
        thickness = 15
        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        canvas.setLineWidth(thickness)
        try:
            canvas.setLineCap(1)
        except Exception:
            pass
        canvas.setStrokeColor(soft)
        canvas.circle(cx, cy, radius, stroke=1, fill=0)
        canvas.setStrokeColor(primary)
        canvas.arc(*bbox, startAng=90, extent=-(self.score / self.total) * 360)

        canvas.setFillColor(text)
        canvas.setFont(self.font_bold, 25)
        canvas.drawCentredString(cx, cy + 1, f"{self.score}")
        canvas.setFont(self.font_name, 10)
        canvas.setFillColor(muted)
        canvas.drawCentredString(cx, cy - 17, f"/ {self.total}")
        canvas.setFont(self.font_bold, 9)
        canvas.setFillColor(primary)
        canvas.drawCentredString(cx, 16, self.label)
        canvas.restoreState()


class _ProgressBar(Flowable):
    def __init__(
        self,
        *,
        score: int,
        width: float,
        height: float = 8,
        color_tokens: dict[str, Any],
        fill_key: str = "brand_primary",
    ) -> None:
        super().__init__()
        self.score = max(0, min(100, int(score)))
        self.width = width
        self.height = height
        self.color_tokens = color_tokens
        self.fill_key = fill_key

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:  # noqa: N802
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        radius = self.height / 2
        canvas.setFillColor(_hex(self.color_tokens.get("line_soft"), "#E5E7EB"))
        canvas.roundRect(0, 0, self.width, self.height, radius, stroke=0, fill=1)
        canvas.setFillColor(_hex(self.color_tokens.get(self.fill_key), "#7C3AED"))
        canvas.roundRect(0, 0, self.width * (self.score / 100), self.height, radius, stroke=0, fill=1)
        canvas.restoreState()


class _ComparisonBarChart(Flowable):
    def __init__(
        self,
        *,
        items: list[tuple[str, int, str]],
        width: float,
        height: float,
        color_tokens: dict[str, Any],
        font_name: str,
        font_bold: str,
    ) -> None:
        super().__init__()
        self.items = [(label, max(0, min(100, int(score))), color_key) for label, score, color_key in items]
        self.width = width
        self.height = height
        self.color_tokens = color_tokens
        self.font_name = font_name
        self.font_bold = font_bold

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:  # noqa: N802
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.setStrokeColor(_hex(self.color_tokens.get("line_soft"), "#E5E7EB"))
        canvas.roundRect(0, 0, self.width, self.height, 10, stroke=1, fill=1)

        left = 18
        right = self.width - 18
        bar_x = 118
        bar_w = max(80, right - bar_x - 38)
        y = self.height - 34
        canvas.setFont(self.font_bold, 10)
        canvas.setFillColor(_hex(self.color_tokens.get("text_primary"), "#111827"))
        canvas.drawString(left, self.height - 18, "역량 축 점수")
        for label, score, color_key in self.items:
            canvas.setFont(self.font_name, 8.6)
            canvas.setFillColor(_hex(self.color_tokens.get("text_muted"), "#6B7280"))
            canvas.drawString(left, y + 1, label)
            canvas.setFillColor(_hex(self.color_tokens.get("line_soft"), "#E5E7EB"))
            canvas.roundRect(bar_x, y, bar_w, 10, 5, stroke=0, fill=1)
            canvas.setFillColor(_hex(self.color_tokens.get(color_key), "#7C3AED"))
            canvas.roundRect(bar_x, y, bar_w * score / 100, 10, 5, stroke=0, fill=1)
            canvas.setFont(self.font_bold, 8.8)
            canvas.setFillColor(_hex(self.color_tokens.get("text_primary"), "#111827"))
            canvas.drawRightString(right, y, f"{score}점")
            y -= 23
        canvas.restoreState()


class _TimelineFlowable(Flowable):
    def __init__(
        self,
        *,
        items: list[tuple[str, str]],
        width: float,
        height: float,
        color_tokens: dict[str, Any],
        font_name: str,
        font_bold: str,
    ) -> None:
        super().__init__()
        self.items = items[:3]
        self.width = width
        self.height = height
        self.color_tokens = color_tokens
        self.font_name = font_name
        self.font_bold = font_bold

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:  # noqa: N802
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        primary = _hex(self.color_tokens.get("brand_primary"), "#7C3AED")
        line = _hex(self.color_tokens.get("line_evidence"), "#C4B5FD")
        text = _hex(self.color_tokens.get("text_primary"), "#111827")
        muted = _hex(self.color_tokens.get("text_muted"), "#6B7280")
        canvas.setFillColor(colors.white)
        canvas.setStrokeColor(_hex(self.color_tokens.get("line_soft"), "#E5E7EB"))
        canvas.roundRect(0, 0, self.width, self.height, 12, stroke=1, fill=1)
        y = self.height / 2 + 8
        start = 38
        end = self.width - 38
        canvas.setStrokeColor(line)
        canvas.setLineWidth(4)
        canvas.line(start, y, end, y)
        count = max(1, len(self.items))
        for index, (grade, summary) in enumerate(self.items):
            x = start + (end - start) * (index / max(1, count - 1))
            canvas.setFillColor(primary)
            canvas.circle(x, y, 8, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.circle(x, y, 3, stroke=0, fill=1)
            canvas.setFillColor(text)
            canvas.setFont(self.font_bold, 10)
            canvas.drawCentredString(x, y + 17, grade)
            canvas.setFillColor(muted)
            canvas.setFont(self.font_name, 7.8)
            trimmed = _truncate_plain(summary, 34)
            canvas.drawCentredString(x, y - 24, trimmed)
        canvas.restoreState()


def _resolve_font_names() -> tuple[str, str]:
    font_path_candidates = [
        Path(__file__).with_name("assets") / "fonts" / "NotoSansKR-VF.ttf",
        Path("C:/Windows/Fonts/NotoSansKR-VF.ttf"),
    ]
    for font_path in font_path_candidates:
        try:
            if not font_path.exists():
                continue
            for name in ("NotoSansKR", "NotoSansKR-Bold"):
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, str(font_path)))
            return "NotoSansKR", "NotoSansKR-Bold"
        except Exception:
            continue
    for regular, bold in (
        ("HYSMyeongJo-Medium", "HYGothic-Medium"),
        ("HeiseiMin-W3", "HeiseiKakuGo-W5"),
    ):
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(regular))
            pdfmetrics.registerFont(UnicodeCIDFont(bold))
            return regular, bold
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold"


def _build_style_tokens(*, design_contract: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> dict[str, Any]:
    styles = getSampleStyleSheet()
    typography = design_contract.get("typography", {}) if isinstance(design_contract.get("typography"), dict) else {}
    spacing = design_contract.get("spacing", {}) if isinstance(design_contract.get("spacing"), dict) else {}
    common_wrap = {"wordWrap": "CJK", "splitLongWords": True}

    def _font_size(key: str, fallback: float) -> float:
        value = typography.get(key, {})
        if isinstance(value, dict):
            return float(value.get("font_size", fallback))
        return fallback

    def _leading(key: str, fallback: float) -> float:
        value = typography.get(key, {})
        if isinstance(value, dict):
            return float(value.get("leading", fallback))
        return fallback

    title_style = ParagraphStyle(
        "DashboardCoverTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=_font_size("cover_title", 30),
        leading=_leading("cover_title", 36),
        textColor=_hex(color_tokens.get("text_primary"), "#111827"),
        alignment=TA_LEFT,
        spaceAfter=8,
        **common_wrap,
    )
    subtitle_style = ParagraphStyle(
        "DashboardCoverSubtitle",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=_font_size("cover_subtitle", 11.4),
        leading=_leading("cover_subtitle", 16.8),
        textColor=_hex(color_tokens.get("text_muted"), "#6B7280"),
        alignment=TA_LEFT,
        spaceAfter=8,
        **common_wrap,
    )
    h2_style = ParagraphStyle(
        "DashboardHeading",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=_font_size("section_heading", 18),
        leading=_leading("section_heading", 23),
        textColor=_hex(color_tokens.get("text_primary"), "#111827"),
        spaceBefore=3,
        spaceAfter=5,
        **common_wrap,
    )
    h3_style = ParagraphStyle(
        "DashboardHeading3",
        parent=styles["Heading3"],
        fontName=font_bold,
        fontSize=11.2,
        leading=14.6,
        textColor=_hex(color_tokens.get("text_primary"), "#111827"),
        spaceAfter=4,
        **common_wrap,
    )
    body_style = ParagraphStyle(
        "DashboardBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10.1,
        leading=14.7,
        textColor=_hex(color_tokens.get("text_primary"), "#111827"),
        spaceAfter=float(spacing.get("paragraph_gap", 5)),
        **common_wrap,
    )
    meta_style = ParagraphStyle(
        "DashboardMeta",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=8.8,
        leading=12.2,
        textColor=_hex(color_tokens.get("text_muted"), "#6B7280"),
        alignment=TA_LEFT,
        **common_wrap,
    )
    meta_strong_style = ParagraphStyle(
        "DashboardMetaStrong",
        parent=meta_style,
        fontName=font_bold,
        textColor=_hex(color_tokens.get("text_primary"), "#111827"),
        **common_wrap,
    )
    number_style = ParagraphStyle(
        "DashboardNumber",
        parent=styles["BodyText"],
        fontName=font_bold,
        fontSize=24,
        leading=27,
        textColor=_hex(color_tokens.get("brand_primary"), "#7C3AED"),
        **common_wrap,
    )
    badge_style = ParagraphStyle(
        "DashboardBadge",
        parent=meta_strong_style,
        fontSize=8.4,
        leading=10.8,
        textColor=_hex(color_tokens.get("brand_secondary"), "#5B21B6"),
        alignment=TA_CENTER,
        **common_wrap,
    )
    cover_label_style = ParagraphStyle(
        "DashboardCoverLabel",
        parent=styles["BodyText"],
        fontName=font_bold,
        fontSize=9.2,
        leading=12,
        textColor=_hex(color_tokens.get("brand_primary"), "#7C3AED"),
        alignment=TA_LEFT,
        spaceAfter=4,
        **common_wrap,
    )
    return {
        "cover_label": cover_label_style,
        "cover_title": title_style,
        "cover_subtitle": subtitle_style,
        "h2": h2_style,
        "h3": h3_style,
        "subtitle": meta_style,
        "body": body_style,
        "bullet": ParagraphStyle("DashboardBullet", parent=body_style, leftIndent=12, bulletIndent=0, spaceAfter=3, **common_wrap),
        "meta": meta_style,
        "meta_strong": meta_strong_style,
        "callout": ParagraphStyle("DashboardCallout", parent=body_style, fontName=font_bold, alignment=TA_CENTER, **common_wrap),
        "number": number_style,
        "badge": badge_style,
        "typography": {"meta_size": 8.8},
        "spacing": {
            "cover_block_gap": float(spacing.get("cover_block_gap", 10)),
            "section_gap": float(spacing.get("section_gap", 8)),
            "paragraph_gap": float(spacing.get("paragraph_gap", 5)),
            "list_item_gap": float(spacing.get("list_item_gap", 3)),
            "card_padding": float(spacing.get("card_padding", 9)),
            "table_cell_padding": float(spacing.get("table_cell_padding", 5)),
        },
    }


def _structured_page_definitions(*, report_payload: dict[str, Any], mode: str, target_pages: int) -> list[dict[str, Any]]:
    if mode == "basic":
        pages = [
            {"kind": "cover", "title": "Cover Hero Page"},
            {"kind": "toc", "title": "보고서 목차"},
            {"kind": "dashboard", "title": "생기부 진단 요약"},
            {"kind": "major_fit_dashboard", "title": "목표 전공 진단"},
            {"kind": "competency", "title": "역량별 점수"},
            {"kind": "record_structure", "title": "생기부 섹션 분석"},
            {"kind": "topics", "title": "맞춤형 탐구 추천", "slice": (0, 4)},
            {"kind": "interviews", "title": "면접 예상 질문", "category": ""},
            {"kind": "action_plan", "title": "30일 액션 플랜"},
        ]
        return _fit_structured_pages(pages, target_pages)

    pages = [
        {"kind": "cover", "title": "Cover Hero Page"},
        {"kind": "toc", "title": "보고서 목차"},
        {
            "kind": "part_intro",
            "title": "Part 1. 생기부 진단",
            "lead": "원본 학생부 근거만으로 현재 기록의 유형, 점수, 전공 연결성을 먼저 정리합니다.",
            "items": ["생기부 유형", "목표 전공 진단", "생기부 총점", "역량별 점수", "학업역량", "진단 해석 원칙"],
        },
        {"kind": "summary", "title": "생기부 유형 및 핵심 판정"},
        {"kind": "dashboard", "title": "생기부 총점"},
        {"kind": "competency", "title": "생기부 역량별 점수"},
        {"kind": "major_fit_dashboard", "title": "목표 전공 진단"},
        {"kind": "subject_table", "title": "학업역량 / 과목별 세특 점검"},
        {"kind": "subject_cards", "title": "과목별 세특 상세 분석", "slice": (0, 6)},
        {"kind": "growth", "title": "학년별 성장 흐름"},
        {
            "kind": "part_intro",
            "title": "Part 2. 생기부 분석",
            "lead": "출결, 리더십, 자율·동아리·진로, 세특, 행동특성을 섹션별 근거 카드로 재배치합니다.",
            "items": ["섹션별 기록 밀도", "활동 연결망", "강점", "약점/리스크", "문장 보완", "총평"],
        },
        {"kind": "record_structure", "title": "섹션별 생기부 분석"},
        {"kind": "network", "title": "생기부 연결망 분석"},
        {"kind": "strengths", "title": "강점 분석"},
        {"kind": "risks", "title": "약점 및 리스크 분석"},
        {"kind": "rewrites", "title": "기록 보완 문장 설계"},
        {
            "kind": "part_intro",
            "title": "Part 3. 맞춤형 보완점",
            "lead": "외부 표본 없이 현재 학생부에서 이어갈 수 있는 전공·탐구·면접 보완 전략만 제안합니다.",
            "items": ["전공 적합성 보완", "탐구활동 추천", "키워드 클라우드", "피해야 할 주제", "로드맵", "검증 메모"],
        },
        {"kind": "major_strategy", "title": "전공 적합성 보완 방향"},
        {"kind": "topics", "title": "탐구활동 추천", "slice": (0, 6)},
        {"kind": "keyword_cloud", "title": "생기부 키워드 클라우드"},
        {"kind": "avoid", "title": "피해야 할 탐구 주제"},
        {"kind": "interviews", "title": "면접 예상 질문", "category": ""},
        {"kind": "roadmap", "title": "맞춤형 실행 로드맵"},
        {"kind": "appendix", "title": "검증 메모 / 부록"},
    ]
    if mode == "consultant":
        pages.extend(
            [
                {"kind": "subject_cards", "title": "과목별 세특 상세 분석 2", "slice": (6, 12)},
                {"kind": "competency", "title": "역량별 근거 매트릭스 심화"},
                {"kind": "record_structure", "title": "섹션별 근거 맵 심화"},
                {"kind": "topics", "title": "추가 탐구활동 추천", "slice": (6, 12)},
                {"kind": "interviews", "title": "면접 예상 질문: 전공 적합성", "category": "전공 적합성"},
                {"kind": "interviews", "title": "면접 예상 질문: 탐구 과정 검증", "category": "탐구 과정 검증"},
                {"kind": "action_plan", "title": "우선순위 액션 플랜"},
                {"kind": "appendix", "title": "컨설턴트 검증 부록"},
            ]
        )
    return _fit_structured_pages(pages, target_pages)


def _render_structured_page(
    *,
    page: dict[str, Any],
    page_index: int,
    report_payload: dict[str, Any],
    doc: SimpleDocTemplate,
    style_tokens: dict[str, Any],
    font_name: str,
    font_bold: str,
    color_tokens: dict[str, Any],
    render_hints: dict[str, Any],
) -> list[Any]:
    kind = str(page.get("kind") or "")
    title = str(page.get("title") or "Report")
    if kind == "cover":
        return _render_structured_cover(
            report_payload=report_payload,
            doc=doc,
            style_tokens=style_tokens,
            font_name=font_name,
            font_bold=font_bold,
            color_tokens=color_tokens,
            render_hints=render_hints,
        )

    flowables: list[Any] = [
        Paragraph(_escape(title), style_tokens["h2"]),
        Paragraph(_escape("Uni-Foli 생기부 진단 | 외부 표본 없는 근거 기반 분석"), style_tokens["subtitle"]),
        Spacer(1, 6),
    ]
    if kind == "toc":
        flowables.extend(_toc_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "part_intro":
        flowables.extend(_part_intro_flowables(page, doc, style_tokens, color_tokens))
    elif kind == "summary":
        flowables.extend(_summary_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "dashboard":
        flowables.extend(_dashboard_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "major_fit_dashboard":
        flowables.extend(_major_fit_dashboard_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "major_strategy":
        flowables.extend(_major_strategy_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "strengths":
        flowables.extend(_strength_risk_flowables(report_payload, doc, style_tokens, color_tokens, strengths=True))
    elif kind == "risks":
        flowables.extend(_strength_risk_flowables(report_payload, doc, style_tokens, color_tokens, strengths=False))
    elif kind == "growth":
        flowables.extend(_growth_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "record_structure":
        flowables.extend(_record_structure_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "subject_table":
        flowables.extend(_subject_table_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "subject_cards":
        flowables.extend(_subject_card_flowables(report_payload, doc, style_tokens, color_tokens, page.get("slice")))
    elif kind == "competency":
        flowables.extend(_competency_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "network":
        flowables.extend(_network_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "topics":
        flowables.extend(_topics_flowables(report_payload, doc, style_tokens, color_tokens, page.get("slice")))
    elif kind == "keyword_cloud":
        flowables.extend(_keyword_cloud_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "avoid":
        flowables.extend(_avoid_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "rewrites":
        flowables.extend(_rewrite_flowables(report_payload, doc, style_tokens, color_tokens))
    elif kind == "interviews":
        flowables.extend(_interview_flowables(report_payload, doc, style_tokens, color_tokens, str(page.get("category") or "")))
    elif kind == "roadmap":
        flowables.extend(_roadmap_flowables(report_payload, doc, style_tokens, font_name, font_bold, color_tokens))
    elif kind == "appendix":
        flowables.extend(_appendix_flowables(report_payload, doc, style_tokens, color_tokens))
    else:
        flowables.extend(_action_plan_flowables(report_payload, doc, style_tokens, color_tokens))
    return flowables


def _fit_structured_pages(pages: list[dict[str, Any]], target_pages: int) -> list[dict[str, Any]]:
    target = max(1, int(target_pages or len(pages) or 1))
    result = [dict(page) for page in pages]
    fillers = [
        {"kind": "action_plan", "title": "추가 실행 체크리스트"},
        {"kind": "topics", "title": "추가 탐구활동 추천", "slice": (0, 6)},
        {"kind": "interviews", "title": "추가 면접 예상 질문", "category": ""},
        {"kind": "appendix", "title": "추가 검증 메모"},
    ]
    filler_index = 0
    while len(result) < target:
        result.append(dict(fillers[filler_index % len(fillers)]))
        filler_index += 1
    return result[:target]


def _toc_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    context = _dashboard_context(report_payload)
    cards = [
        {
            "title": "Part 1. 생기부 진단",
            "body": "생기부 유형, 목표 전공 진단, 총점, 역량별 점수, 학업역량을 먼저 확인합니다.",
            "chips": ["Diagnosis"],
            "tone": "action",
        },
        {
            "title": "Part 2. 생기부 분석",
            "body": "출결·리더십·자율·동아리·진로·세특·행동특성을 섹션별 근거 카드로 봅니다.",
            "chips": ["Record Map"],
            "tone": "plain",
        },
        {
            "title": "Part 3. 맞춤형 보완점",
            "body": "전공 적합성 보완, 탐구활동 추천, 키워드, 면접 질문, 실행 로드맵을 정리합니다.",
            "chips": ["Action"],
            "tone": "plain",
        },
    ]
    return [
        _dashboard_card(
            "보고서 구성 원칙",
            (
                f"대상 학생: {context['student']} | 목표 학과: {context['target_major']}. "
                "외부 표본, 합격자 데이터, 지원 적정 구간, 결과 단정 문구는 사용하지 않고 업로드된 학생부 근거와 우리 진단 축만 사용합니다."
            ),
            doc.width,
            style_tokens,
            color_tokens,
            tone="plain",
        ),
        Spacer(1, 10),
        _dashboard_card_grid(cards, doc, style_tokens, color_tokens, cols=3),
        Spacer(1, 9),
        _chip_row(["생기부 진단", "생기부 분석", "맞춤형 보완점", "검증 메모"], doc.width, style_tokens, color_tokens),
    ]


def _part_intro_flowables(page: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    title = str(page.get("title") or "Part")
    lead = str(page.get("lead") or "이 파트의 핵심 흐름을 정리합니다.")
    items = [str(item) for item in page.get("items", []) if str(item).strip()]
    cards = [
        {
            "title": f"{index}. {item}",
            "body": "현재 학생부에서 확인 가능한 근거만 연결해 해석합니다.",
            "chips": ["근거 기반"],
            "tone": "plain",
        }
        for index, item in enumerate(items[:6], start=1)
    ]
    return [
        _dashboard_card(title, lead, doc.width, style_tokens, color_tokens, tone="action"),
        Spacer(1, 11),
        _dashboard_card_grid(cards, doc, style_tokens, color_tokens, cols=3),
        Spacer(1, 8),
        _dashboard_card(
            "해석 범위",
            "이 파트의 점수와 판단은 합격 예측이 아니라 학생부 원문 근거의 밀도, 연결성, 과정성, 설명 가능성을 재구성한 내부 진단입니다.",
            doc.width,
            style_tokens,
            color_tokens,
            tone="plain",
        ),
    ]


def _major_strategy_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    context = _dashboard_context(report_payload)
    branding = premium.get("student_branding") if isinstance(premium.get("student_branding"), dict) else {}
    matrix = [item for item in premium.get("major_competency_matrix", []) if isinstance(item, dict)]
    strongest = max(matrix, key=lambda item: _safe_int(item.get("score"), 0), default={})
    weakest = min(matrix, key=lambda item: _safe_int(item.get("score"), 100), default={})
    cards = [
        {
            "title": "목표 전공",
            "body": f"{context['target_university']} / {context['target_major']}",
            "chips": ["Target"],
            "tone": "action",
        },
        {
            "title": "현재 브랜딩",
            "body": _truncate_plain(str(branding.get("one_line_branding") or branding.get("core_narrative") or "전공 연결 문장을 학생부 근거 중심으로 재정리합니다."), 130),
            "chips": ["Narrative"],
            "tone": "plain",
        },
        {
            "title": "가장 강한 연결",
            "body": f"{strongest.get('competency') or '확인 필요'}: {_truncate_plain(str(strongest.get('evidence') or ''), 96)}",
            "chips": ["Strength"],
            "tone": "plain",
        },
        {
            "title": "우선 보완축",
            "body": f"{weakest.get('competency') or '확인 필요'}: {_truncate_plain(str(weakest.get('improvement') or '과정, 산출물, 한계 설명을 보강하세요.'), 96)}",
            "chips": ["Priority"],
            "tone": "risk",
        },
    ]
    return [
        _dashboard_card_grid(cards[:2], doc, style_tokens, color_tokens, cols=2),
        Spacer(1, 8),
        _dashboard_card_grid(cards[2:4], doc, style_tokens, color_tokens, cols=2),
        Spacer(1, 8),
        _dashboard_card(
            "보완 원칙",
            "새 활동을 억지로 만들기보다 기존 기록에서 문제의식, 사용 개념, 방법, 산출물, 한계를 분리해 전공 질문으로 다시 연결합니다.",
            doc.width,
            style_tokens,
            color_tokens,
            tone="plain",
        ),
    ]


def _keyword_cloud_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    terms = _keyword_cloud_terms(report_payload)
    flowables: list[Any] = [
        _dashboard_card(
            "키워드 해석",
            "키워드는 학생부와 진단 결과에서 반복적으로 드러난 표현입니다. 외부 학생 데이터가 아니라 현재 문서 안의 전공 연결 단서를 압축해 보여줍니다.",
            doc.width,
            style_tokens,
            color_tokens,
            tone="plain",
        ),
        Spacer(1, 10),
    ]
    for index in range(0, min(len(terms), 24), 4):
        flowables.append(_chip_row(terms[index: index + 4], doc.width, style_tokens, color_tokens))
        flowables.append(Spacer(1, 6))
    flowables.append(
        _dashboard_card(
            "활용법",
            "상위 키워드 3개를 골라 세특 문장, 탐구보고서 제목, 면접 답변의 같은 축으로 반복 배치하면 기록의 일관성이 올라갑니다.",
            doc.width,
            style_tokens,
            color_tokens,
            tone="action",
        )
    )
    return flowables


def _keyword_cloud_terms(report_payload: dict[str, Any]) -> list[str]:
    premium = _premium_analysis(report_payload)
    candidates: list[Any] = []
    candidates.extend(item.get("axis") for item in _dashboard_score_items(report_payload))
    candidates.extend(report_payload.get("recommended_topics", []) if isinstance(report_payload.get("recommended_topics"), list) else [])
    for key in ("major_competency_matrix", "evidence_map", "recommended_research_topics", "subject_analysis"):
        values = premium.get(key)
        if isinstance(values, list):
            candidates.extend(values)
    for key in ("strengths", "weaknesses"):
        values = premium.get(key)
        if isinstance(values, list):
            candidates.extend(values)

    terms: list[str] = []
    seen: set[str] = set()
    generic = {
        "근거",
        "분석",
        "필요",
        "보완",
        "학생부",
        "기록",
        "확인",
        "활동",
        "추천",
        "주제",
        "결과",
        "과정",
        "점수",
        "리스크",
    }

    def add(value: Any) -> None:
        if isinstance(value, dict):
            for nested_key in (
                "competency",
                "subject_or_activity",
                "section",
                "title",
                "major_connection",
                "major_relevance",
                "competency_tags",
            ):
                add(value.get(nested_key))
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                add(item)
            return
        text = re.sub(r"[^0-9A-Za-z가-힣·/\s-]", " ", str(value or ""))
        for chunk in re.split(r"[,/|·•\n]+", text):
            chunk = " ".join(chunk.split()).strip(" -")
            if not chunk:
                continue
            pieces = [chunk] if len(chunk) <= 10 else [piece for piece in chunk.split() if len(piece) >= 2]
            for piece in pieces:
                clean = _truncate_plain(piece.strip(" -"), 14)
                key = clean.lower()
                if len(clean) < 2 or key in seen or clean in generic:
                    continue
                seen.add(key)
                terms.append(clean)

    for candidate in candidates:
        add(candidate)
        if len(terms) >= 28:
            break
    fallback = ["전공 적합성", "탐구 심화", "서사 연결", "근거 밀도", "면접 방어", "과정성", "산출물", "후속 질문"]
    for term in fallback:
        if len(terms) >= 24:
            break
        key = term.lower()
        if key not in seen:
            seen.add(key)
            terms.append(term)
    return terms[:24]


def _render_structured_cover(
    *,
    report_payload: dict[str, Any],
    doc: SimpleDocTemplate,
    style_tokens: dict[str, Any],
    font_name: str,
    font_bold: str,
    color_tokens: dict[str, Any],
    render_hints: dict[str, Any],
) -> list[Any]:
    premium = _premium_analysis(report_payload)
    context = _dashboard_context(report_payload)
    score_400, score_100, _ = _overall_score_metrics(report_payload)
    branding = str((premium.get("student_branding") or {}).get("one_line_branding") or render_hints.get("one_line_verdict") or "생기부 근거를 전공 역량과 면접 전략으로 구조화한 프리미엄 진단서입니다.")
    hero_left = [
        _badge("Uni-Foli Record ON", doc.width * 0.30, style_tokens, color_tokens, tone="purple"),
        Spacer(1, 10),
        Paragraph("AI 생기부 분석 리포트", style_tokens["cover_title"]),
        Paragraph(_escape(_truncate_plain(branding, 150)), style_tokens["cover_subtitle"]),
        Spacer(1, 10),
        _mini_meta_grid(
            [
                ("학생", context["student"]),
                ("목표 학과", context["target_major"]),
                ("분석일", _report_date_kst()),
            ],
            doc.width * 0.55,
            style_tokens,
            color_tokens,
        ),
    ]
    hero = Table(
        [[hero_left, _DashboardDonutChart(score=score_400, total=400, width=doc.width * 0.32, height=190, color_tokens=color_tokens, font_name=font_name, font_bold=font_bold, label="종합 점수")]],
        colWidths=[doc.width * 0.62, doc.width * 0.34],
        hAlign="LEFT",
    )
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _hex(color_tokens.get("surface_evidence"), "#F5F3FF")),
                ("BOX", (0, 0), (-1, -1), 0.7, _hex(color_tokens.get("line_evidence"), "#C4B5FD")),
                ("LEFTPADDING", (0, 0), (-1, -1), 18),
                ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                ("TOPPADDING", (0, 0), (-1, -1), 20),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    stat_cards = _metric_grid(
        [
            ("종합 환산", f"{score_400}/400", "4개 핵심 축 기준"),
            ("100점 환산", f"{score_100}점", "우리 진단 축 기반"),
            ("분석 신뢰도", f"{int(round(float(render_hints.get('analysis_confidence_score', 0.72)) * 100))}%", "근거 연결 품질"),
        ],
        doc,
        style_tokens,
        color_tokens,
    )
    return [
        Spacer(1, 14),
        hero,
        Spacer(1, 12),
        stat_cards,
        Spacer(1, 10),
        _dashboard_card(
            "리포트 사용 원칙",
            "이 보고서는 합격 가능성을 단정하지 않고, 학생부 원문 근거를 전공 역량, 리스크, 후속 탐구, 면접 질문으로 재배치합니다. 내부 근거 코드와 파싱 ID는 공개 문서에 표시하지 않습니다.",
            doc.width,
            style_tokens,
            color_tokens,
            tone="plain",
        ),
        Spacer(1, 8),
        _chip_row(["생기부 진단", "생기부 분석", "맞춤형 보완점", "검증 메모"], doc.width, style_tokens, color_tokens),
    ]


def _dashboard_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> list[Any]:
    blocks = _dashboard_score_items(report_payload)
    score_400, score_100, _ = _overall_score_metrics(report_payload)
    axis_items = _axis_chart_items(report_payload)
    top_cards = [
        {
            "title": item["axis"],
            "body": _truncate_plain(item.get("interpretation") or item.get("improvement") or "근거 기반 점수입니다.", 105),
            "score": item["score"],
            "chips": [_score_level(item["score"])],
            "tone": "purple" if index == 0 else "plain",
        }
        for index, item in enumerate(blocks[:4])
    ]
    chart_row = Table(
        [[
            _DashboardDonutChart(score=score_400, total=400, width=doc.width * 0.34, height=178, color_tokens=color_tokens, font_name=font_name, font_bold=font_bold, label="종합 / 400"),
            [
                _metric_grid(
                    [
                        ("100점 환산", f"{score_100}점", "핵심 축 환산"),
                        ("역량 축", f"{len(axis_items)}개", "확인된 평가 항목"),
                    ],
                    doc,
                    style_tokens,
                    color_tokens,
                    width=doc.width * 0.56,
                    cols=2,
                ),
                Spacer(1, 8),
                _ComparisonBarChart(items=axis_items, width=doc.width * 0.56, height=112, color_tokens=color_tokens, font_name=font_name, font_bold=font_bold),
            ],
        ]],
        colWidths=[doc.width * 0.38, doc.width * 0.58],
        hAlign="LEFT",
    )
    chart_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return [
        chart_row,
        Spacer(1, 10),
        _dashboard_card_grid(top_cards, doc, style_tokens, color_tokens, cols=2),
        Spacer(1, 8),
        Paragraph("점수는 외부 표본 비교가 아니라 현재 학생부 근거의 밀도, 연결성, 과정성, 설명 가능성을 환산한 내부 진단 축입니다.", style_tokens["subtitle"]),
    ]


def _major_fit_dashboard_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    branding = premium.get("student_branding") if isinstance(premium.get("student_branding"), dict) else {}
    blocks = _dashboard_score_items(report_payload)
    major_score = next((item["score"] for item in blocks if "전공" in item["axis"] or "major" in item["axis"].lower()), blocks[0]["score"] if blocks else 72)
    evidence_map = [item for item in premium.get("evidence_map", []) if isinstance(item, dict)]
    matrix = [item for item in premium.get("major_competency_matrix", []) if isinstance(item, dict)]
    featured_evidence = evidence_map[:3]
    evidence_cards = [
        {
            "title": str(item.get("subject_or_activity") or item.get("section") or "핵심 근거"),
            "body": f"{_truncate_plain(str(item.get('raw_summary') or ''), 82)}\n전공 연결: {_truncate_plain(str(item.get('major_relevance') or ''), 78)}",
            "chips": [str(tag) for tag in (item.get("competency_tags") or [])[:2]],
            "tone": "plain",
        }
        for item in featured_evidence
    ]
    if not evidence_cards:
        evidence_cards = [{"title": "핵심 근거 정리", "body": "생기부 원문에서 전공 연결 근거를 카드형으로 정리합니다.", "chips": ["근거"], "tone": "plain"}]
    competency_cards = [
        {
            "title": str(item.get("competency") or "전공역량"),
            "body": _truncate_plain(str(item.get("evidence") or item.get("improvement") or ""), 88),
            "score": _safe_int(item.get("score"), 0),
            "chips": [_score_level(_safe_int(item.get("score"), 0))],
            "tone": "purple" if index == 0 else "plain",
        }
        for index, item in enumerate(matrix[:3])
    ]
    return [
        _dashboard_card(
            "전공 브랜딩",
            _truncate_plain(str(branding.get("one_line_branding") or branding.get("core_narrative") or "전공 적합성을 학생부 근거 중심으로 재정리합니다."), 220),
            doc.width,
            style_tokens,
            color_tokens,
            score=major_score,
            chips=["Major Fit", _score_level(major_score)],
            tone="purple",
        ),
        Spacer(1, 9),
        _dashboard_card_grid(evidence_cards[:3], doc, style_tokens, color_tokens, cols=3),
        Spacer(1, 9),
        _dashboard_card_grid(competency_cards[:3], doc, style_tokens, color_tokens, cols=3),
    ]


def _strength_risk_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], *, strengths: bool) -> list[Any]:
    premium = _premium_analysis(report_payload)
    if strengths:
        source = [str(item) for item in premium.get("strengths", []) if str(item).strip()]
        default_title = "강점"
        tone = "purple"
    else:
        risks = [item for item in premium.get("risk_analysis", []) if isinstance(item, dict)]
        source = [
            f"{item.get('risk')}: {item.get('impact')} 보완: {item.get('mitigation')}"
            for item in risks
        ] or [str(item) for item in premium.get("weaknesses", []) if str(item).strip()]
        default_title = "리스크"
        tone = "risk"
    if not source:
        source = _first_lines(report_payload.get("sections"), "strength_analysis" if strengths else "weakness_risk_analysis", 5)
    if not source:
        source = ["대표 활동 3개를 고르고 문제-방법-결과-한계 흐름으로 정리해야 합니다."]
    cards = [
        {
            "title": f"{default_title} TOP {index}",
            "body": _truncate_plain(text, 150),
            "chips": ["Evidence" if strengths else "Risk"],
            "tone": tone if index <= 2 else "plain",
        }
        for index, text in enumerate(source[:5], start=1)
    ]
    return [
        _dashboard_card_grid(cards[:2], doc, style_tokens, color_tokens, cols=2),
        Spacer(1, 8),
        _dashboard_card_grid(cards[2:5], doc, style_tokens, color_tokens, cols=3),
        Spacer(1, 8),
        _dashboard_card(
            "해석 포인트" if strengths else "방어 포인트",
            "강점은 자기소개식 칭찬이 아니라 면접에서 설명 가능한 근거 카드로 바꿔야 합니다." if strengths else "리스크는 감점 예측이 아니라 질문 받을 가능성이 높은 부분입니다. 대표 활동 3개로 압축해 방어 문장을 준비하세요.",
            doc.width,
            style_tokens,
            color_tokens,
            tone="plain",
        ),
    ]


def _growth_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    timeline = [item for item in premium.get("growth_timeline", []) if isinstance(item, dict)]
    font_name = getattr(style_tokens["meta"], "fontName", "Helvetica")
    font_bold = getattr(style_tokens["meta_strong"], "fontName", "Helvetica-Bold")
    timeline_items = [
        (str(item.get("grade") or f"{index}학년"), str(item.get("role") or item.get("next_flow") or "성장 흐름"))
        for index, item in enumerate(timeline[:3], start=1)
    ]
    if not timeline_items:
        timeline_items = [("1학년", "관심 발견"), ("2학년", "개념 심화"), ("3학년", "전공 서사 압축")]
    cards = []
    for item in timeline[:3]:
        core = " / ".join(str(value) for value in (item.get("core_activities") or [])[:2])
        comps = " / ".join(str(value) for value in (item.get("visible_competencies") or [])[:2])
        cards.append(
            {
                "title": f"{item.get('grade')}: {item.get('role')}",
                "body": f"핵심 활동: {_truncate_plain(core, 84)}\n드러나는 역량: {_truncate_plain(comps, 78)}\n다음 흐름: {_truncate_plain(str(item.get('next_flow') or ''), 82)}",
                "chips": ["Timeline"],
                "tone": "plain",
            }
        )
    if not cards:
        cards = [
            {"title": "1학년: 관심 발견", "body": "전공 관심의 시작점을 확인합니다.", "chips": ["1학년"], "tone": "plain"},
            {"title": "2학년: 심화", "body": "수업 개념과 활동 경험을 연결합니다.", "chips": ["2학년"], "tone": "plain"},
            {"title": "3학년: 압축", "body": "대표 활동 3개로 면접 서사를 정리합니다.", "chips": ["3학년"], "tone": "plain"},
        ]
    return [
        _TimelineFlowable(items=timeline_items, width=doc.width, height=128, color_tokens=color_tokens, font_name=font_name, font_bold=font_bold),
        Spacer(1, 10),
        _dashboard_card_grid(cards[:3], doc, style_tokens, color_tokens, cols=3),
        Spacer(1, 8),
        _dashboard_card("성장 서사 한 줄", "공간에 대한 관심에서 출발해 사회 문제 해결형 탐구를 거쳐, 전공 면접에서 방어 가능한 핵심 활동으로 압축하는 흐름이 필요합니다.", doc.width, style_tokens, color_tokens, tone="purple"),
    ]


def _record_structure_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    evidence_map = [item for item in premium.get("evidence_map", []) if isinstance(item, dict)]
    cards = []
    for item in evidence_map[:8]:
        tags = [str(tag) for tag in (item.get("competency_tags") or [])[:2]]
        cards.append(
            {
                "title": f"{item.get('grade') or '학년'} | {item.get('subject_or_activity') or item.get('section') or '근거'}",
                "body": f"원문 요약: {_truncate_plain(str(item.get('raw_summary') or ''), 82)}\n전공 의미: {_truncate_plain(str(item.get('major_relevance') or ''), 82)}",
                "chips": tags or [str(item.get("section") or "근거")],
                "tone": "plain",
            }
        )
    if not cards:
        cards = [{"title": "생기부 근거 맵", "body": "원문에서 학년, 활동, 전공역량을 분리해 카드로 배치합니다.", "chips": ["Evidence"], "tone": "plain"}]
    return [
        _dashboard_card_grid(cards[:4], doc, style_tokens, color_tokens, cols=2),
        Spacer(1, 8),
        _dashboard_card_grid(cards[4:8], doc, style_tokens, color_tokens, cols=2),
    ]


def _subject_card_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], slice_value: Any) -> list[Any]:
    premium = _premium_analysis(report_payload)
    premium_subjects = [item for item in premium.get("subject_analysis", []) if isinstance(item, dict)]
    fallback_subjects = [item for item in report_payload.get("subject_specialty_analyses", []) if isinstance(item, dict)]
    subjects = premium_subjects or fallback_subjects
    start, end = _slice_tuple(slice_value, 0, 6)
    selected = subjects[start:end] or subjects[:6]
    cards = []
    for item in selected:
        subject = str(item.get("subject") or "과목")
        score = _safe_int(item.get("score"), 0)
        body = (
            f"핵심 근거: {_truncate_plain(str(item.get('evidence_summary') or item.get('core_record_summary') or ''), 70)}\n"
            f"전공 연결: {_truncate_plain(str(item.get('major_connection') or ''), 66)}\n"
            f"후속 탐구: {_truncate_plain(str(item.get('recommended_followup') or item.get('recommended_follow_up') or ''), 66)}"
        )
        cards.append({"title": subject, "body": body, "score": score, "chips": [str(item.get("level") or _score_level(score))], "tone": "plain"})
    if not cards:
        cards = [{"title": "과목별 세특", "body": "과목별 원문 근거, 전공 연결, 후속 탐구를 카드로 표시합니다.", "score": 0, "chips": ["준비중"], "tone": "plain"}]
    return [
        _dashboard_card_grid(cards[:3], doc, style_tokens, color_tokens, cols=3),
        Spacer(1, 8),
        _dashboard_card_grid(cards[3:6], doc, style_tokens, color_tokens, cols=3),
    ]


def _competency_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], font_name: str, font_bold: str, color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    matrix = [item for item in premium.get("major_competency_matrix", []) if isinstance(item, dict)]
    cards = []
    for index, item in enumerate(matrix[:6]):
        score = _safe_int(item.get("score"), 0)
        cards.append(
            {
                "title": str(item.get("competency") or "전공역량"),
                "body": f"근거: {_truncate_plain(str(item.get('evidence') or ''), 78)}\n보완: {_truncate_plain(str(item.get('improvement') or ''), 76)}",
                "score": score,
                "chips": [_score_level(score)],
                "tone": "purple" if index == 0 else "plain",
            }
        )
    if not cards:
        for item in _dashboard_score_items(report_payload)[:6]:
            cards.append({"title": item["axis"], "body": _truncate_plain(item.get("interpretation") or "", 92), "score": item["score"], "chips": [_score_level(item["score"])], "tone": "plain"})
    return [
        _dashboard_card_grid(cards[:3], doc, style_tokens, color_tokens, cols=3),
        Spacer(1, 8),
        _dashboard_card_grid(cards[3:6], doc, style_tokens, color_tokens, cols=3),
        Spacer(1, 8),
        _dashboard_card("매트릭스 읽는 법", "점수는 전공역량의 강도만 보지 않고 원문 근거, 산출물, 정량성, 면접 방어 가능성을 함께 반영합니다.", doc.width, style_tokens, color_tokens, tone="plain"),
    ]


def _topics_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], slice_value: Any) -> list[Any]:
    premium = _premium_analysis(report_payload)
    topics = [item for item in premium.get("recommended_research_topics", []) if isinstance(item, dict)] or [item for item in report_payload.get("research_topics", []) if isinstance(item, dict)]
    start, end = _slice_tuple(slice_value, 0, 6)
    selected = topics[start:end] or topics[:6]
    cards = []
    for index, topic in enumerate(selected[:6], start=1):
        cards.append(
            {
                "title": f"{index}. {topic.get('title') or '추천 탐구'}",
                "body": (
                    f"질문: {_truncate_plain(str(topic.get('research_question') or topic.get('inquiry_question') or ''), 70)}\n"
                    f"방법: {_truncate_plain(str(topic.get('method') or ''), 56)}\n"
                    f"산출물: {_truncate_plain(str(topic.get('expected_output') or ''), 56)}"
                ),
                "chips": [str(topic.get("difficulty") or "보통"), str(topic.get("interview_value") or topic.get("interview_use") or "면접 활용")[:12]],
                "tone": "plain",
            }
        )
    if not cards:
        cards = [{"title": "추천 탐구 주제", "body": "생기부 근거와 이어지는 후속 탐구를 보고서 제목 형태로 제안합니다.", "chips": ["Research"], "tone": "plain"}]
    return [
        _dashboard_card_grid(cards[:2], doc, style_tokens, color_tokens, cols=2),
        Spacer(1, 8),
        _dashboard_card_grid(cards[2:6], doc, style_tokens, color_tokens, cols=2),
    ]


def _interview_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], category: str) -> list[Any]:
    premium = _premium_analysis(report_payload)
    questions = [item for item in premium.get("interview_questions", []) if isinstance(item, dict)] or [item for item in report_payload.get("interview_questions", []) if isinstance(item, dict)]
    selected = [item for item in questions if not category or str(item.get("category")) == category] or questions[:6]
    cards = []
    for index, item in enumerate(selected[:6], start=1):
        cards.append(
            {
                "title": f"Q{index}. {item.get('question') or '면접 질문'}",
                "body": (
                    f"답변 프레임: {_truncate_plain(str(item.get('answer_frame') or ''), 92)}\n"
                    f"연결 근거: {_truncate_plain(str(item.get('connected_evidence') or ''), 64)}\n"
                    f"주의: {_truncate_plain(str(item.get('avoid') or ''), 52)}"
                ),
                "chips": [str(item.get("category") or "면접")[:16]],
                "tone": "plain",
            }
        )
    while len(cards) < 4:
        cards.append({"title": "면접 답변 구조", "body": "활동 배경, 사용 개념, 본인 역할, 결과 해석, 한계와 후속 탐구 순서로 답변을 구성하세요.", "chips": ["Frame"], "tone": "plain"})
    return [
        _dashboard_card_grid(cards[:2], doc, style_tokens, color_tokens, cols=2),
        Spacer(1, 8),
        _dashboard_card_grid(cards[2:6], doc, style_tokens, color_tokens, cols=2),
    ]


def _action_plan_flowables(report_payload: dict[str, Any], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> list[Any]:
    premium = _premium_analysis(report_payload)
    actions = [item for item in premium.get("action_plan", []) if isinstance(item, dict)]
    text_actions = [str(item.get("action") or item.get("message") or "") for item in actions if str(item.get("action") or item.get("message") or "").strip()]
    if not text_actions:
        text_actions = [
            "대표 활동 3개를 선정하고 한 줄 브랜딩 문장을 고정한다.",
            "각 활동의 문제, 방법, 결과, 한계를 5줄 카드로 정리한다.",
            "정량 근거가 있는 활동은 그래프, 표, 도면 중 하나로 산출물을 만든다.",
            "면접 예상 질문 10개를 60초 답변 프레임으로 연습한다.",
        ]
    periods = ["1-7일", "8-14일", "15-21일", "22-30일"]
    cards = []
    for index, period in enumerate(periods):
        first = text_actions[index % len(text_actions)]
        second = text_actions[(index + 1) % len(text_actions)]
        cards.append(
            {
                "title": period,
                "body": f"[ ] {_truncate_plain(first, 74)}\n[ ] {_truncate_plain(second, 74)}",
                "chips": ["Checklist"],
                "tone": "purple" if index == 0 else "plain",
            }
        )
    return [
        _dashboard_card("30일 목표", "새로운 활동을 억지로 늘리는 것이 아니라, 이미 있는 생기부 근거를 대표 활동, 정량 산출물, 면접 답변으로 재구성하는 데 집중합니다.", doc.width, style_tokens, color_tokens, tone="purple"),
        Spacer(1, 9),
        _dashboard_card_grid(cards[:2], doc, style_tokens, color_tokens, cols=2),
        Spacer(1, 8),
        _dashboard_card_grid(cards[2:4], doc, style_tokens, color_tokens, cols=2),
    ]


def _structured_card(
    title: str,
    body: str,
    width: float,
    style_tokens: dict[str, Any],
    color_tokens: dict[str, Any],
    *,
    tone: str = "panel",
) -> Table:
    return _dashboard_card(title, body, width, style_tokens, color_tokens, tone="plain" if tone == "panel" else tone)


def _card_grid(cards: list[tuple[str, str]], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> Table:
    mapped = [{"title": title, "body": body, "tone": "plain", "chips": []} for title, body in (cards or [])]
    return _dashboard_card_grid(mapped, doc, style_tokens, color_tokens, cols=2)


def _dashboard_card(
    title: str,
    body: str,
    width: float,
    style_tokens: dict[str, Any],
    color_tokens: dict[str, Any],
    *,
    score: int | None = None,
    chips: list[str] | None = None,
    tone: str = "plain",
) -> Table:
    fill = {
        "purple": "surface_evidence",
        "risk": "surface_warning",
        "action": "surface_action",
        "plain": "surface_panel",
        "evidence": "surface_evidence",
        "warning": "surface_warning",
    }.get(tone, "surface_panel")
    border = {
        "purple": "line_evidence",
        "risk": "line_warning",
        "action": "line_action",
        "plain": "line_soft",
        "evidence": "line_evidence",
        "warning": "line_warning",
    }.get(tone, "line_soft")
    content: list[Any] = [Paragraph(_escape(title), style_tokens["meta_strong"])]
    if chips:
        content.append(Spacer(1, 3))
        content.append(_inline_badges([str(chip) for chip in chips if str(chip).strip()][:3], max(80, width - 18), style_tokens, color_tokens, tone="risk" if tone == "risk" else "purple"))
    if score is not None:
        clamped = max(0, min(100, int(score)))
        content.append(Spacer(1, 4))
        content.append(Paragraph(f"{clamped}점", style_tokens["number"]))
        content.append(_ProgressBar(score=clamped, width=max(64, width - 24), height=7, color_tokens=color_tokens, fill_key="risk_red" if tone == "risk" else "brand_primary"))
    if body:
        content.append(Spacer(1, 5))
        content.append(Paragraph(_escape(body).replace("\n", "<br/>"), style_tokens["meta"]))
    table = Table([[content]], colWidths=[width], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _hex(color_tokens.get(fill), "#FFFFFF")),
                ("BOX", (0, 0), (-1, -1), 0.65, _hex(color_tokens.get(border), "#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _dashboard_card_grid(cards: list[dict[str, Any]], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], *, cols: int = 2) -> Table:
    cols = max(1, min(3, cols))
    placeholder = {
        "title": "추가 확인",
        "body": "업로드 문서에서 이 영역을 판단할 근거가 충분하지 않습니다. 원문 근거가 확보되면 세부 분석을 보강합니다.",
        "tone": "plain",
        "chips": ["확인 필요"],
    }
    cleaned = list(cards or [])
    if not cleaned:
        cleaned = [placeholder.copy() for _ in range(cols)]
    gutter = 8
    col_width = (doc.width - gutter * (cols - 1)) / cols
    rows: list[list[Any]] = []
    for index in range(0, len(cleaned), cols):
        row_items = cleaned[index: index + cols]
        row = [
            _dashboard_card(
                str(item.get("title") or "분석 카드"),
                str(item.get("body") or ""),
                col_width,
                style_tokens,
                color_tokens,
                score=item.get("score") if item.get("score") is not None else None,
                chips=[str(chip) for chip in item.get("chips", []) if str(chip).strip()],
                tone=str(item.get("tone") or "plain"),
            )
            for item in row_items
        ]
        while len(row) < cols:
            item = placeholder.copy()
            row.append(
                _dashboard_card(
                    str(item.get("title")),
                    str(item.get("body")),
                    col_width,
                    style_tokens,
                    color_tokens,
                    chips=[str(chip) for chip in item.get("chips", [])],
                    tone=str(item.get("tone") or "plain"),
                )
            )
        rows.append(row)
    table = Table(rows, colWidths=[col_width] * cols, hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return table


def _metric_grid(items: list[tuple[str, str, str]], doc: SimpleDocTemplate, style_tokens: dict[str, Any], color_tokens: dict[str, Any], *, width: float | None = None, cols: int = 3) -> Table:
    target_width = width or doc.width
    cols = max(1, min(3, cols))
    gutter = 8
    col_width = (target_width - gutter * (cols - 1)) / cols
    cells = [
        _metric_tile(label, value, note, col_width, style_tokens, color_tokens)
        for label, value, note in items
    ]
    rows = [cells[index: index + cols] for index in range(0, len(cells), cols)]
    for row in rows:
        while len(row) < cols:
            row.append("")
    table = Table(rows, colWidths=[col_width] * cols, hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return table


def _metric_tile(label: str, value: str, note: str, width: float, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> Table:
    content = [
        Paragraph(_escape(label), style_tokens["meta_strong"]),
        Spacer(1, 2),
        Paragraph(_escape(value), style_tokens["number"]),
        Paragraph(_escape(note), style_tokens["meta"]),
    ]
    table = Table([[content]], colWidths=[width], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.65, _hex(color_tokens.get("line_soft"), "#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _badge(label: str, width: float, style_tokens: dict[str, Any], color_tokens: dict[str, Any], *, tone: str = "purple") -> Table:
    return _inline_badges([label], width, style_tokens, color_tokens, tone=tone)


def _inline_badges(labels: list[str], width: float, style_tokens: dict[str, Any], color_tokens: dict[str, Any], *, tone: str = "purple") -> Table:
    clean = [_truncate_plain(label, 22) for label in labels if str(label).strip()] or ["분석"]
    cols = len(clean)
    col_width = width / cols
    fill = "surface_warning" if tone == "risk" else "surface_action"
    border = "line_warning" if tone == "risk" else "line_action"
    table = Table([[Paragraph(_escape(label), style_tokens["badge"]) for label in clean]], colWidths=[col_width] * cols)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _hex(color_tokens.get(fill), "#EDE9FE")),
                ("BOX", (0, 0), (-1, -1), 0.55, _hex(color_tokens.get(border), "#7C3AED")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, _hex(color_tokens.get(border), "#7C3AED")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _mini_meta_grid(items: list[tuple[str, str]], width: float, style_tokens: dict[str, Any], color_tokens: dict[str, Any]) -> Table:
    rows = [[Paragraph(_escape(label), style_tokens["meta_strong"]), Paragraph(_escape(value), style_tokens["meta"])] for label, value in items]
    table = Table(rows, colWidths=[width * 0.24, width * 0.76], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.45, _hex(color_tokens.get("line_soft"), "#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, _hex(color_tokens.get("line_soft"), "#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _dashboard_context(report_payload: dict[str, Any]) -> dict[str, str]:
    premium = _premium_analysis(report_payload)
    context = str(report_payload.get("student_target_context") or "")
    report_meta = premium.get("report_meta") if isinstance(premium.get("report_meta"), dict) else {}

    def _value(labels: list[str], default: str) -> str:
        for label in labels:
            if label in context:
                value = context.split(label, 1)[1].split("|", 1)[0].strip()
                if value:
                    return _truncate_plain(value, 42)
        return default

    student = _value(["학생:", "학생명:", "Student:"], "학생명 비공개")
    target_major = _value(["목표 전공:", "목표 학과:", "학과:", "Major:"], str(report_meta.get("target_major") or "목표 학과 미설정"))
    target_university = _value(["목표 대학:", "대학:", "University:"], "목표 대학 미설정")
    return {"student": student, "target_major": _truncate_plain(target_major, 42), "target_university": _truncate_plain(target_university, 42)}


def _dashboard_score_items(report_payload: dict[str, Any]) -> list[dict[str, Any]]:
    premium = _premium_analysis(report_payload)
    premium_dashboard = [item for item in premium.get("score_dashboard", []) if isinstance(item, dict)]
    source = premium_dashboard or [item for item in report_payload.get("score_blocks", []) if isinstance(item, dict)]
    items: list[dict[str, Any]] = []
    for item in source:
        score = _safe_int(item.get("score"), 0)
        axis = str(item.get("axis") or item.get("label") or item.get("key") or "평가축")
        items.append(
            {
                "axis": _truncate_plain(axis, 34),
                "score": max(0, min(100, score)),
                "evidence": str(item.get("evidence") or item.get("evidence_summary") or ""),
                "interpretation": str(item.get("interpretation") or item.get("rationale") or ""),
                "improvement": str(item.get("improvement") or item.get("next_best_action") or ""),
            }
        )
    if not items:
        items = [
            {"axis": "전공 적합성", "score": 76, "interpretation": "전공 연결 근거를 중심으로 평가합니다.", "evidence": "", "improvement": ""},
            {"axis": "탐구 심화도", "score": 72, "interpretation": "탐구 질문과 산출물을 함께 봅니다.", "evidence": "", "improvement": ""},
            {"axis": "서사 일관성", "score": 74, "interpretation": "학년별 흐름을 평가합니다.", "evidence": "", "improvement": ""},
            {"axis": "면접 방어력", "score": 68, "interpretation": "대표 활동 설명 가능성을 평가합니다.", "evidence": "", "improvement": ""},
        ]
    return items


def _overall_score_metrics(report_payload: dict[str, Any]) -> tuple[int, int, int]:
    scores = [item["score"] for item in _dashboard_score_items(report_payload) if isinstance(item.get("score"), int)]
    if not scores:
        scores = [72, 70, 68, 74]
    first_four = scores[:4]
    while len(first_four) < 4:
        first_four.append(round(sum(first_four) / len(first_four)))
    score_400 = max(0, min(400, int(sum(first_four))))
    score_100 = round(score_400 / 4)
    percentile = max(1, min(99, round(score_400 / 400 * 100)))
    return score_400, score_100, percentile


def _axis_chart_items(report_payload: dict[str, Any]) -> list[tuple[str, int, str]]:
    color_keys = ["brand_primary", "academic_blue", "success_green", "warning_orange"]
    items: list[tuple[str, int, str]] = []
    for index, item in enumerate(_dashboard_score_items(report_payload)[:4]):
        items.append((item["axis"], item["score"], color_keys[index % len(color_keys)]))
    while len(items) < 4:
        fallback = _benchmark_items(72)[len(items)]
        items.append(fallback)
    return items[:4]


def _benchmark_items(score_100: int) -> list[tuple[str, int, str]]:
    return [
        ("전공 적합성", score_100, "brand_primary"),
        ("탐구 심화", max(0, min(100, score_100 - 3)), "academic_blue"),
        ("서사 연결", max(0, min(100, score_100 - 5)), "success_green"),
        ("면접 방어", max(0, min(100, score_100 - 7)), "warning_orange"),
    ]


def _score_level(score: int) -> str:
    score = max(0, min(100, int(score)))
    if score >= 90:
        return "매우 강함"
    if score >= 80:
        return "강함"
    if score >= 70:
        return "보완 가능"
    if score >= 60:
        return "주의"
    return "리스크"


def _report_date_kst() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


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
    canvas.setFillColor(_hex(color_tokens.get("brand_primary"), "#0F766E"))
    canvas.rect(0, height - 13, width, 13, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont(font_bold, 7.2)
    canvas.drawString(doc.leftMargin, height - 9, "Uni-Foli Record ON")
    canvas.setStrokeColor(_hex(color_tokens.get("line_soft"), "#E5E7EB"))
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, 32, width - doc.rightMargin, 32)
    canvas.setFont(font_name, 8.1)
    canvas.setFillColor(_hex(color_tokens.get("text_muted"), "#6B7280"))
    canvas.drawString(doc.leftMargin, 18, "AI 생기부 진단 리포트")
    canvas.drawRightString(width - doc.rightMargin, 18, f"{canvas.getPageNumber()} 페이지")
    canvas.restoreState()

