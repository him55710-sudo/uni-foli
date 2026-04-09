from __future__ import annotations

from typing import Any

_DIAGNOSIS_SECTION_ORDER_PREMIUM: tuple[str, ...] = (
    "cover_context",
    "executive_summary",
    "current_record_status",
    "evaluation_axis",
    "strength_analysis",
    "weakness_risk",
    "major_fit",
    "section_level_diagnosis",
    "roadmap",
    "topic_strategy",
    "final_memo",
    "appendix",
)

_DIAGNOSIS_SECTION_ORDER_COMPACT: tuple[str, ...] = (
    "cover_context",
    "executive_summary",
    "current_record_status",
    "strength_analysis",
    "weakness_risk",
    "roadmap",
    "final_memo",
)


def get_diagnosis_report_design_contract(
    *,
    report_mode: str,
    template_id: str,
    template_section_schema: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """
    Returns a reusable design-system contract consumed by diagnosis report
    payload generation and PDF rendering.

    The contract is code-first and deterministic, with Figma MCP metadata
    attached for registry mapping and future design handoff.
    """
    is_premium = report_mode == "premium_10p"
    section_order = _DIAGNOSIS_SECTION_ORDER_PREMIUM if is_premium else _DIAGNOSIS_SECTION_ORDER_COMPACT

    return {
        "contract_id": "diagnosis_report_premium_v2" if is_premium else "diagnosis_report_compact_v2",
        "template_id": template_id,
        "mode": report_mode,
        "figma_mapping": {
            "mcp_available": True,
            "source": "figma_mcp",
            "access_level": "view",
            "mapping_status": "code_first_contract_with_figma_reference",
            "note": "Figma MCP availability confirmed. Renderer consumes deterministic code contract mapped to template registry.",
        },
        "canvas": {
            "page_size": "A4",
            "margins": {
                "left": 46 if is_premium else 48,
                "right": 46 if is_premium else 48,
                "top": 44 if is_premium else 46,
                "bottom": 50 if is_premium else 52,
            },
            "minimum_pages": 10 if is_premium else 5,
        },
        "typography": {
            "cover_label": {"font_size": 9, "leading": 12, "weight": "medium"},
            "cover_title": {"font_size": 26 if is_premium else 23, "leading": 32 if is_premium else 29, "weight": "bold"},
            "cover_subtitle": {"font_size": 11, "leading": 16, "weight": "regular"},
            "section_heading": {"font_size": 17 if is_premium else 16, "leading": 22, "weight": "bold"},
            "section_subtitle": {"font_size": 9.5, "leading": 13, "weight": "regular"},
            "body": {"font_size": 10.4 if is_premium else 10.2, "leading": 15.6 if is_premium else 15.2, "weight": "regular"},
            "meta": {"font_size": 8.6, "leading": 12, "weight": "regular"},
            "caption": {"font_size": 8.2, "leading": 11.5, "weight": "medium"},
        },
        "spacing": {
            "cover_block_gap": 10,
            "section_gap": 8,
            "paragraph_gap": 5,
            "list_item_gap": 3,
            "card_padding": 9,
            "table_cell_padding": 5,
        },
        "colors": {
            "brand_primary": "#1E3A5F",
            "brand_secondary": "#2B4F7B",
            "text_primary": "#0F172A",
            "text_secondary": "#334155",
            "text_muted": "#526173",
            "line_soft": "#D7DEE8",
            "surface_soft": "#F8FAFC",
            "surface_panel": "#F1F5F9",
            "surface_warning": "#FFF7ED",
            "line_warning": "#FDBA74",
            "surface_evidence": "#EEF2FF",
            "line_evidence": "#C7D2FE",
        },
        "section_hierarchy": {
            "required_order": list(section_order),
            "section_groups": [
                ["cover_context", "executive_summary", "current_record_status"],
                ["evaluation_axis", "strength_analysis"],
                ["weakness_risk", "major_fit"],
                ["section_level_diagnosis", "roadmap"],
                ["topic_strategy", "final_memo"],
                ["appendix"],
            ]
            if is_premium
            else [
                ["cover_context", "executive_summary"],
                ["current_record_status", "strength_analysis"],
                ["weakness_risk", "roadmap"],
                ["final_memo"],
            ],
            "template_registry_section_schema": list(template_section_schema or ()),
        },
        "card_hierarchy": {
            "cover_meta": {"tone": "quiet_panel", "border": "line_soft"},
            "evidence_card": {"tone": "evidence", "border": "line_evidence"},
            "uncertainty_card": {"tone": "warning", "border": "line_warning"},
            "score_table": {"header_tone": "surface_panel", "grid": "line_soft"},
        },
        "appendix_layout": {
            "citations_visible": True,
            "uncertainty_notes_visible": True,
            "uncertainty_before_citations": True,
            "max_citation_items": 60 if is_premium else 30,
            "max_uncertainty_items": 12 if is_premium else 8,
        },
    }
