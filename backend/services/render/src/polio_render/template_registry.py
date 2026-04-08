from __future__ import annotations

from dataclasses import dataclass

from polio_domain.enums import RenderFormat


@dataclass(frozen=True, slots=True)
class TemplatePreviewMetadata:
    accent_color: str
    surface_tone: str
    cover_title: str
    preview_sections: tuple[str, ...]
    thumbnail_hint: str


@dataclass(frozen=True, slots=True)
class RenderTemplate:
    id: str
    label: str
    description: str
    supported_formats: tuple[RenderFormat, ...]
    category: str
    section_schema: tuple[str, ...]
    density: str
    visual_priority: str
    supports_provenance_appendix: bool
    recommended_for: tuple[str, ...]
    preview: TemplatePreviewMetadata


@dataclass(frozen=True, slots=True)
class RenderExportPolicy:
    include_provenance_appendix: bool = False
    hide_internal_provenance_on_final_export: bool = True


_TEMPLATES: tuple[RenderTemplate, ...] = (
    RenderTemplate(
        id="clean_report_basic",
        label="Clean Report",
        description="A simple report-first structure for grounded academic writing and safe submissions.",
        supported_formats=(RenderFormat.PDF, RenderFormat.HWPX, RenderFormat.PPTX),
        category="report",
        section_schema=("title", "context", "analysis", "reflection", "next_steps"),
        density="balanced",
        visual_priority="low",
        supports_provenance_appendix=True,
        recommended_for=("grounded summary", "submission-safe report", "teacher review"),
        preview=TemplatePreviewMetadata(
            accent_color="#0f172a",
            surface_tone="paper",
            cover_title="Grounded report",
            preview_sections=("Question", "Evidence", "Reflection"),
            thumbnail_hint="Minimal serif-like report cover with one accent rule.",
        ),
    ),
    RenderTemplate(
        id="academic_report_evidence",
        label="Academic Report with Evidence",
        description="A denser academic layout that foregrounds claim-evidence links and method notes.",
        supported_formats=(RenderFormat.PDF, RenderFormat.HWPX, RenderFormat.PPTX),
        category="report",
        section_schema=("title", "research_question", "evidence_review", "method", "analysis", "limitations"),
        density="dense",
        visual_priority="medium",
        supports_provenance_appendix=True,
        recommended_for=("evidence density", "method explanation", "concept-driven inquiry"),
        preview=TemplatePreviewMetadata(
            accent_color="#1d4ed8",
            surface_tone="scholarly",
            cover_title="Evidence-backed inquiry",
            preview_sections=("Question", "Method", "Evidence Matrix", "Limitations"),
            thumbnail_hint="Academic report preview with blue section dividers and evidence callouts.",
        ),
    ),
    RenderTemplate(
        id="activity_summary_school",
        label="School Activity Summary",
        description="A conservative, school-friendly summary layout that keeps claims compact and auditable.",
        supported_formats=(RenderFormat.PDF, RenderFormat.HWPX),
        category="school_record",
        section_schema=("title", "activity_scope", "what_i_did", "what_i_learned", "record_note"),
        density="light",
        visual_priority="low",
        supports_provenance_appendix=True,
        recommended_for=("school submission", "activity recap", "authenticity-sensitive export"),
        preview=TemplatePreviewMetadata(
            accent_color="#166534",
            surface_tone="school",
            cover_title="Activity summary",
            preview_sections=("Scope", "Actions", "Learning", "Record Note"),
            thumbnail_hint="Soft green submission sheet with restrained headings and no decorative visuals.",
        ),
    ),
    RenderTemplate(
        id="comparison_analysis",
        label="Comparison Analysis",
        description="A side-by-side comparison structure for before/after, case A/case B, or method contrasts.",
        supported_formats=(RenderFormat.PDF, RenderFormat.HWPX, RenderFormat.PPTX),
        category="analysis",
        section_schema=("title", "comparison_frame", "case_a", "case_b", "analysis", "implications"),
        density="balanced",
        visual_priority="medium",
        supports_provenance_appendix=True,
        recommended_for=("comparison", "inquiry continuity", "measured differences"),
        preview=TemplatePreviewMetadata(
            accent_color="#b45309",
            surface_tone="contrast",
            cover_title="Comparison frame",
            preview_sections=("Frame", "Case A", "Case B", "Implications"),
            thumbnail_hint="Split-column preview with warm contrast blocks and conclusion band.",
        ),
    ),
    RenderTemplate(
        id="proposal_pitch",
        label="Proposal Pitch",
        description="A persuasive but grounded structure for future plans, interventions, or next-step proposals.",
        supported_formats=(RenderFormat.PDF, RenderFormat.PPTX),
        category="proposal",
        section_schema=("title", "problem", "insight", "proposal", "expected_impact", "feasibility"),
        density="balanced",
        visual_priority="high",
        supports_provenance_appendix=True,
        recommended_for=("future direction", "proposal", "impact framing"),
        preview=TemplatePreviewMetadata(
            accent_color="#7c3aed",
            surface_tone="pitch",
            cover_title="Evidence-backed proposal",
            preview_sections=("Problem", "Insight", "Proposal", "Impact"),
            thumbnail_hint="Modern pitch board with bold headline and short impact blocks.",
        ),
    ),
    RenderTemplate(
        id="timeline_growth_story",
        label="Timeline Growth Story",
        description="A chronological structure for growth, iteration, and continuity across activities.",
        supported_formats=(RenderFormat.PDF, RenderFormat.HWPX, RenderFormat.PPTX),
        category="story",
        section_schema=("title", "starting_point", "turning_points", "growth", "current_position", "next_move"),
        density="balanced",
        visual_priority="medium",
        supports_provenance_appendix=True,
        recommended_for=("growth narrative", "continuity", "semester progression"),
        preview=TemplatePreviewMetadata(
            accent_color="#0f766e",
            surface_tone="timeline",
            cover_title="Growth timeline",
            preview_sections=("Starting Point", "Turning Points", "Current Position"),
            thumbnail_hint="Horizontal progression preview with anchored milestones and reflective notes.",
        ),
    ),
    RenderTemplate(
        id="presentation_minimal",
        label="Minimal Presentation",
        description="A compact presentation structure that keeps slides readable and submission-safe.",
        supported_formats=(RenderFormat.PPTX, RenderFormat.PDF),
        category="presentation",
        section_schema=("title", "agenda", "evidence", "insight", "next_step"),
        density="light",
        visual_priority="medium",
        supports_provenance_appendix=True,
        recommended_for=("slide export", "teacher presentation", "clean visual summary"),
        preview=TemplatePreviewMetadata(
            accent_color="#0f172a",
            surface_tone="screen",
            cover_title="Minimal deck",
            preview_sections=("Agenda", "Evidence", "Insight"),
            thumbnail_hint="Sparse slide deck with strong title slide and generous whitespace.",
        ),
    ),
    RenderTemplate(
        id="presentation_visual_focus",
        label="Visual Focus Presentation",
        description="A presentation-forward layout that gives more space to visual hierarchy and concise takeaways.",
        supported_formats=(RenderFormat.PPTX, RenderFormat.PDF),
        category="presentation",
        section_schema=("title", "hook", "visual_evidence", "interpretation", "takeaway"),
        density="light",
        visual_priority="high",
        supports_provenance_appendix=True,
        recommended_for=("visual summary", "presentation", "showcase deck"),
        preview=TemplatePreviewMetadata(
            accent_color="#dc2626",
            surface_tone="showcase",
            cover_title="Visual-first deck",
            preview_sections=("Hook", "Visual Evidence", "Takeaway"),
            thumbnail_hint="Large visual card layout with strong color accents and minimal body text.",
        ),
    ),
    RenderTemplate(
        id="consultant_diagnosis_compact",
        label="Consultant Diagnosis (Compact)",
        description="Compact consultant-grade diagnosis layout with evidence notes and actionable roadmap.",
        supported_formats=(RenderFormat.PDF,),
        category="diagnosis_report",
        section_schema=(
            "cover_context",
            "executive_summary",
            "current_record_status",
            "strength_analysis",
            "weakness_risk",
            "roadmap",
            "final_memo",
        ),
        density="balanced",
        visual_priority="medium",
        supports_provenance_appendix=True,
        recommended_for=("quick consultant review", "school-safe diagnosis summary", "evidence memo"),
        preview=TemplatePreviewMetadata(
            accent_color="#0f4c81",
            surface_tone="consultant",
            cover_title="Compact consultant diagnosis",
            preview_sections=("Summary", "Strengths", "Risks", "Roadmap"),
            thumbnail_hint="A4 brief with score strip and concise evidence callouts.",
        ),
    ),
    RenderTemplate(
        id="consultant_diagnosis_premium_10p",
        label="Consultant Diagnosis (Premium 10p)",
        description="Premium consultant diagnosis template targeting approximately ten A4 pages with section-depth and appendix.",
        supported_formats=(RenderFormat.PDF,),
        category="diagnosis_report",
        section_schema=(
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
        ),
        density="dense",
        visual_priority="high",
        supports_provenance_appendix=True,
        recommended_for=("premium consultant report", "diagnosis artifact", "auditable PDF export"),
        preview=TemplatePreviewMetadata(
            accent_color="#1d4ed8",
            surface_tone="premium_consultant",
            cover_title="Premium consultant diagnosis report",
            preview_sections=("Executive", "Axis Analysis", "Roadmap", "Appendix"),
            thumbnail_hint="Structured premium report with score panels, evidence boxes, and appendix tabs.",
        ),
    ),
)

_TEMPLATE_BY_ID = {template.id: template for template in _TEMPLATES}
_DEFAULT_TEMPLATE_BY_FORMAT = {
    RenderFormat.PDF: "clean_report_basic",
    RenderFormat.HWPX: "activity_summary_school",
    RenderFormat.PPTX: "presentation_minimal",
}


def list_templates(*, render_format: RenderFormat | None = None) -> list[RenderTemplate]:
    if render_format is None:
        return list(_TEMPLATES)
    return [
        template
        for template in _TEMPLATES
        if render_format in template.supported_formats
    ]


def get_default_template_id(render_format: RenderFormat) -> str:
    return _DEFAULT_TEMPLATE_BY_FORMAT[render_format]


def get_template(
    template_id: str | None,
    *,
    render_format: RenderFormat,
) -> RenderTemplate:
    resolved_id = template_id or get_default_template_id(render_format)
    template = _TEMPLATE_BY_ID.get(resolved_id)
    if template is None:
        raise ValueError(f"Unknown render template: {resolved_id}")
    if render_format not in template.supported_formats:
        raise ValueError(
            f"Template '{resolved_id}' does not support {render_format.value.upper()} exports."
        )
    return template


def humanize_provenance_source(
    source: str | None,
    *,
    hide_internal: bool,
) -> str:
    normalized = (source or "").strip()
    if not normalized:
        return "Student record evidence"
    if not hide_internal:
        return normalized
    if normalized.startswith("turn:"):
        return "Workshop conversation"
    if normalized.startswith("reference:"):
        return "Pinned reference"
    if normalized.startswith("document:"):
        return "Parsed student record"
    if normalized.startswith(("session:", "trace:", "job:", "draft:", "chunk:")):
        return "Internal workflow record"
    return normalized


def build_provenance_appendix_lines(
    *,
    evidence_map: dict[str, dict] | None,
    authenticity_log_lines: list[str] | None,
    hide_internal: bool,
    max_evidence_items: int = 5,
    max_authenticity_notes: int = 3,
) -> list[str]:
    lines: list[str] = []

    for claim, support in list((evidence_map or {}).items())[:max_evidence_items]:
        if not isinstance(support, dict):
            continue
        evidence = str(support.get("洹쇨굅") or support.get("evidence") or "Grounded student evidence")
        source = humanize_provenance_source(
            str(support.get("異쒖쿂") or support.get("source") or ""),
            hide_internal=hide_internal,
        )
        lines.append(f"{claim}: {evidence} ({source})")

    notes = [line.strip() for line in (authenticity_log_lines or []) if line and line.strip()]
    if not notes:
        return lines

    if hide_internal:
        lines.append(
            f"Internal workshop grounding notes were applied during drafting ({min(len(notes), max_authenticity_notes)} note(s) retained internally)."
        )
        return lines

    for prompt in notes[-max_authenticity_notes:]:
        lines.append(f"Workshop note: {prompt[:180]}")
    return lines


def rank_templates_for_keywords(
    *,
    render_format: RenderFormat,
    keywords: list[str],
) -> list[RenderTemplate]:
    lowered_keywords = [item.strip().lower() for item in keywords if item and item.strip()]

    def score(template: RenderTemplate) -> tuple[int, str]:
        template_terms = " ".join(
            [
                template.category,
                template.label,
                template.description,
                *template.recommended_for,
                *template.section_schema,
            ]
        ).lower()
        matches = sum(1 for keyword in lowered_keywords if keyword in template_terms)
        return matches, template.id

    ranked = list_templates(render_format=render_format)
    ranked.sort(key=lambda item: score(item), reverse=True)
    return ranked
