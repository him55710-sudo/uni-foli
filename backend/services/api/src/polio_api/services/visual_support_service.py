from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from polio_domain.enums import EvidenceProvenance

_SECTION_HEADING_RE = re.compile(r"^(#{1,3})\s+(?P<title>.+?)\s*$")
_BULLET_RE = re.compile(r"^(?:[-*]\s+|\d+\.\s+)")
_LATEX_BLOCK_RE = re.compile(r"\$\$(?P<latex>.+?)\$\$", re.DOTALL)
_INLINE_LATEX_RE = re.compile(r"\$(?P<latex>[^$\n]+)\$")
_PLAIN_EQUATION_RE = re.compile(r"(?P<equation>[A-Za-z가-힣][A-Za-z0-9가-힣_ ()/\-*+^]{0,50}=\s*[A-Za-z0-9가-힣_ ()/\-*+^.%]{1,60})")
_WORD_RE = re.compile(r"[A-Za-z가-힣]{2,}")
_NUMERIC_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?(?:%|명|건|점|kg|g|cm|mm|℃|회|시간|년)?")

_COMPARISON_KEYWORDS = {
    "compare",
    "comparison",
    "vs",
    "versus",
    "tradeoff",
    "difference",
    "differences",
    "contrast",
    "비교",
    "차이",
    "장단점",
    "대조",
    "선택",
}
_CHART_KEYWORDS = {
    "trend",
    "trends",
    "data",
    "rate",
    "rates",
    "ratio",
    "ratios",
    "share",
    "shares",
    "count",
    "counts",
    "distribution",
    "추이",
    "수치",
    "비율",
    "분포",
    "데이터",
}
_FLOW_KEYWORDS = {
    "process",
    "workflow",
    "pipeline",
    "steps",
    "step",
    "flow",
    "과정",
    "단계",
    "흐름",
    "절차",
}
_EQUATION_KEYWORDS = {
    "equation",
    "formula",
    "formulas",
    "수식",
    "공식",
}
_DECORATIVE_IMAGE_KEYWORDS = {
    "campus",
    "portrait",
    "stock",
    "banner",
    "hero",
    "logo",
    "smiling",
    "lifestyle",
    "graduation",
    "students",
    "student life",
}

_MIN_VISUAL_CONFIDENCE = 0.72
_MAX_VISUALS_PER_REPORT = 3


def regenerate_visual_variant(
    *,
    old_visual_id: str,
    original_specs: list[dict[str, Any]],
    report_markdown: str,
    evidence_map: dict[str, Any] | None,
    advanced_mode: bool,
) -> dict[str, Any] | None:
    """Generates a fresh variant for a specifically rejected/replaced visual."""
    if not advanced_mode or not report_markdown.strip():
        return None

    # Find the old spec to understand the context (which section was it supporting?)
    target_spec = next((s for s in original_specs if s.get("id") == old_visual_id), None)
    if not target_spec:
        return None

    section_title = target_spec.get("section_title")
    old_type = target_spec.get("type")

    # Re-run the plan builder but focus on candidates that might replace this one
    # For a high-quality 'Replace', we could slightly lower the threshold or 
    # pick the 2nd best candidate for that section.
    
    # In this implementation, we simulate 'Replacement' by finding another candidate
    # of the same or compatible type for that section, or slightly modifying the existing one
    # with a 'v2' flag if no alternatives exist in the top-k.
    
    # Let's rebuild the plan to see all candidates again
    new_plan = build_visual_support_plan(
        report_markdown=report_markdown,
        evidence_map=evidence_map,
        student_submission_note=None,
        turns=[],
        references=[],
        advanced_mode=advanced_mode
    )
    
    all_new_specs = new_plan.get("visual_specs", [])
    
    # Filter for candidates supporting the same section but DIFFERENT from the old one
    alternatives = [
        s for s in all_new_specs 
        if s.get("section_title") == section_title and s.get("id") != old_visual_id
    ]
    
    if alternatives:
        # Pick the best alternative
        match = alternatives[0]
        match["approval_status"] = "proposed"
        match["origin"] = "regenerated_variant"
        return match
        
    # If no alternatives, we 'Force' a variant of the same spec (e.g. change chart type or refine)
    # For now, we'll return a modified version of the target_spec to show 'Change' has happened
    # In a real LLM-backed system, this would be a new LLM call with 'Make this chart different' prompt.
    refined = target_spec.copy()
    refined["id"] = f"{old_visual_id}-v2"
    refined["approval_status"] = "proposed"
    if refined["type"] == "chart" and "chart_spec" in refined:
        # Simple heuristic: swap bar <-> line or similar
        ctype = refined["chart_spec"].get("type", "bar")
        refined["chart_spec"]["type"] = "line" if ctype == "bar" else "bar"
        refined["title"] = f"{refined['title']} (Alternative view)"
    
    refined["rationale"] = f"Regenerated variant replacing the previous proposal. {refined.get('rationale', '')}"
    return refined


def build_visual_support_plan(
    *,
    report_markdown: str,
    evidence_map: dict[str, Any] | None,
    student_submission_note: str | None,
    turns: Sequence[Any],
    references: Sequence[Any],
    advanced_mode: bool,
    target_major: str | None = None,
    external_image_candidates: Sequence[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if not advanced_mode or not report_markdown.strip():
        return {"visual_specs": [], "math_expressions": []}

    sections = _split_markdown_sections(report_markdown)
    grounding_text = "\n".join(
        part
        for part in [
            _serialize_grounding_turns(turns),
            _serialize_grounding_references(references),
            _serialize_evidence_map(evidence_map or {}),
            student_submission_note or "",
        ]
        if part
    )
    visuals: list[dict[str, Any]] = []
    math_expressions: list[dict[str, Any]] = []

    for index, section in enumerate(sections, start=1):
        generated_candidates = [
            _build_chart_candidate(
                section=section,
                visual_index=index,
                grounding_text=grounding_text,
                evidence_map=evidence_map or {},
                references=references,
            ),
            _build_table_candidate(
                section=section,
                visual_index=index,
                evidence_map=evidence_map or {},
                references=references,
            ),
            _build_diagram_candidate(
                section=section,
                visual_index=index,
                evidence_map=evidence_map or {},
                references=references,
            ),
            _build_equation_candidate(
                section=section,
                visual_index=index,
                grounding_text=grounding_text,
                evidence_map=evidence_map or {},
                references=references,
            ),
        ]
        generated_candidates = [candidate for candidate in generated_candidates if candidate is not None]
        best_generated = max(generated_candidates, key=lambda item: float(item["confidence"]), default=None)

        best_external_image = None
        if external_image_candidates:
            ranked_images = rank_external_image_candidates(
                section_title=section["title"],
                section_text=section["text"],
                candidates=external_image_candidates,
                target_major=target_major,
                limit=1,
            )
            if ranked_images:
                best_external_image = _build_external_image_candidate(
                    section=section,
                    visual_index=index,
                    ranked_image=ranked_images[0],
                )

        chosen = _choose_section_visual(best_generated=best_generated, best_external_image=best_external_image)
        if chosen is None or float(chosen["confidence"]) < _MIN_VISUAL_CONFIDENCE:
            continue

        visuals.append(chosen)
        if chosen["type"] == "equation":
            math_expressions.append(
                {
                    "label": chosen.get("title") or section["title"],
                    "latex": chosen.get("equation_spec", {}).get("latex", ""),
                    "context": chosen.get("caption") or chosen.get("rationale"),
                }
            )

        if len(visuals) >= _MAX_VISUALS_PER_REPORT:
            break

    return {
        "visual_specs": visuals,
        "math_expressions": [item for item in math_expressions if item.get("latex")],
    }


def rank_external_image_candidates(
    *,
    section_title: str,
    section_text: str,
    candidates: Sequence[dict[str, Any]],
    target_major: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    query_terms = _extract_terms(" ".join(part for part in [target_major or "", section_title, section_text] if part))
    ranked: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for candidate in candidates:
        source_url = str(candidate.get("source_url") or candidate.get("image_url") or "").strip()
        if source_url and source_url in seen_urls:
            continue
        if source_url:
            seen_urls.add(source_url)

        candidate_text = " ".join(
            str(
                candidate.get(key) or ""
            ).strip()
            for key in ("source_title", "caption", "alt_text", "context_text", "source_type")
        )
        candidate_terms = _extract_terms(candidate_text)
        relevance = _overlap_ratio(query_terms, candidate_terms)
        trust_rank = max(0, min(int(candidate.get("trust_rank") or 0), 400))
        trust_score = trust_rank / 400
        decorative_penalty = 0.22 if _looks_decorative(candidate_text) else 0.0
        usefulness_bonus = 0.12 if _looks_explanatory_image(candidate_text, section_text) else 0.0
        score = round((relevance * 0.62) + (trust_score * 0.26) + usefulness_bonus - decorative_penalty, 3)

        if score < _MIN_VISUAL_CONFIDENCE:
            continue

        ranked.append(
            {
                **candidate,
                "score": score,
                "confidence": score,
                "selection_reason": (
                    "High lexical/context match with the supported paragraph, acceptable trust level, and non-decorative framing."
                ),
            }
        )

    ranked.sort(
        key=lambda item: (
            float(item.get("score") or 0.0),
            int(item.get("trust_rank") or 0),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _split_markdown_sections(content: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_title = "Overview"
    current_lines: list[str] = []

    for raw_line in (content or "").splitlines():
        line = raw_line.rstrip()
        heading_match = _SECTION_HEADING_RE.match(line)
        if heading_match:
            if current_lines:
                sections.append(
                    {
                        "title": current_title,
                        "lines": [item for item in current_lines if item.strip()],
                        "text": "\n".join(item for item in current_lines if item.strip()),
                    }
                )
            current_title = heading_match.group("title").strip() or "Untitled Section"
            current_lines = []
            continue
        current_lines.append(line)

    if current_lines or not sections:
        sections.append(
            {
                "title": current_title,
                "lines": [item for item in current_lines if item.strip()],
                "text": "\n".join(item for item in current_lines if item.strip()),
            }
        )
    return sections


def _build_table_candidate(
    *,
    section: dict[str, Any],
    visual_index: int,
    evidence_map: dict[str, Any],
    references: Sequence[Any],
) -> dict[str, Any] | None:
    rows = _extract_table_rows(section["lines"])
    combined_text = f"{section['title']}\n{section['text']}".lower()
    comparison_signal = any(keyword in combined_text for keyword in _COMPARISON_KEYWORDS)
    if len(rows) < 2:
        return None
    if not comparison_signal and len(rows) < 3:
        return None

    confidence = 0.84 if comparison_signal else 0.76
    evidence_refs = _extract_evidence_refs(evidence_map)
    return {
        "id": f"visual-{visual_index}",
        "type": "table",
        "title": f"{section['title']} comparison table",
        "section_title": section["title"],
        "paragraph_anchor": _clip(section["text"], 120),
        "insertion_position": "after_section",
        "caption": "Summarizes the comparison already present in the paragraph so the trade-offs stay readable without introducing new claims.",
        "confidence": confidence,
        "rationale": "A compact table is clearer than an image here because the section is comparing multiple attributes rather than describing a scene.",
        "origin": "generated",
        "approval_status": "proposed",
        "table_spec": {
            "columns": ["Aspect", "Grounded point"],
            "rows": rows[:5],
        },
        "provenance": _build_generated_provenance(
            section_title=section["title"],
            rationale="Generated from comparison language already present in the report draft.",
            evidence_refs=evidence_refs,
            references=references,
            basis=["report_markdown", "evidence_map"],
        ),
    }


def _build_chart_candidate(
    *,
    section: dict[str, Any],
    visual_index: int,
    grounding_text: str,
    evidence_map: dict[str, Any],
    references: Sequence[Any],
) -> dict[str, Any] | None:
    datapoints = _extract_numeric_datapoints(section["lines"])
    if len(datapoints) < 2:
        return None

    supported_points = [item for item in datapoints if _datapoint_is_grounded(item, grounding_text)]
    if len(supported_points) < 2:
        return None

    combined_text = f"{section['title']}\n{section['text']}".lower()
    chart_type = "line" if any(keyword in combined_text for keyword in {"trend", "trends", "추이"}) else "bar"
    confidence = 0.88 if any(keyword in combined_text for keyword in _CHART_KEYWORDS) else 0.79
    evidence_refs = _extract_evidence_refs(evidence_map)
    unit = next((item["unit"] for item in supported_points if item["unit"]), "")
    return {
        "id": f"visual-{visual_index}",
        "type": "chart",
        "title": f"{section['title']} data chart",
        "section_title": section["title"],
        "paragraph_anchor": _clip(section["text"], 120),
        "insertion_position": "after_section",
        "caption": "Only grounded numeric claims were charted. If the paragraph changes, this chart should be regenerated instead of reused.",
        "confidence": confidence,
        "rationale": "A chart is appropriate because the paragraph already presents multiple supported numeric values that benefit from direct comparison.",
        "origin": "generated",
        "approval_status": "proposed",
        "chart_spec": {
            "title": section["title"],
            "type": chart_type,
            "unit": unit,
            "data": [{"name": item["label"], "value": item["value"]} for item in supported_points[:6]],
        },
        "provenance": _build_generated_provenance(
            section_title=section["title"],
            rationale="Derived from numeric values already present in the paragraph and rechecked against grounding text.",
            evidence_refs=evidence_refs,
            references=references,
            basis=["report_markdown", "evidence_map", "pinned_references"],
        ),
    }


def _build_diagram_candidate(
    *,
    section: dict[str, Any],
    visual_index: int,
    evidence_map: dict[str, Any],
    references: Sequence[Any],
) -> dict[str, Any] | None:
    steps = _extract_steps(section["lines"])
    combined_text = f"{section['title']}\n{section['text']}".lower()
    if len(steps) < 3:
        return None
    if not any(keyword in combined_text for keyword in _FLOW_KEYWORDS) and len(steps) < 4:
        return None

    confidence = 0.83 if any(keyword in combined_text for keyword in _FLOW_KEYWORDS) else 0.74
    evidence_refs = _extract_evidence_refs(evidence_map)
    return {
        "id": f"visual-{visual_index}",
        "type": "diagram",
        "title": f"{section['title']} flow",
        "section_title": section["title"],
        "paragraph_anchor": _clip(section["text"], 120),
        "insertion_position": "after_section",
        "caption": "Clarifies the sequence already described in the report without adding unsupported process details.",
        "confidence": confidence,
        "rationale": "A simple flow diagram is better than an image when the paragraph is mainly about ordered steps or causal flow.",
        "origin": "generated",
        "approval_status": "proposed",
        "diagram_spec": {
            "layout": "vertical_flow",
            "steps": steps[:6],
        },
        "provenance": _build_generated_provenance(
            section_title=section["title"],
            rationale="Generated from explicit sequential language in the report draft.",
            evidence_refs=evidence_refs,
            references=references,
            basis=["report_markdown", "evidence_map"],
        ),
    }


def _build_equation_candidate(
    *,
    section: dict[str, Any],
    visual_index: int,
    grounding_text: str,
    evidence_map: dict[str, Any],
    references: Sequence[Any],
) -> dict[str, Any] | None:
    latex = _extract_equation(section["text"])
    if not latex:
        return None

    combined_text = f"{section['title']}\n{section['text']}".lower()
    if not any(keyword in combined_text for keyword in _EQUATION_KEYWORDS) and "$" not in section["text"] and "=" not in latex:
        return None
    if grounding_text and not _equation_is_grounded(latex, grounding_text, section["text"]):
        return None

    confidence = 0.86
    evidence_refs = _extract_evidence_refs(evidence_map)
    return {
        "id": f"visual-{visual_index}",
        "type": "equation",
        "title": section["title"],
        "section_title": section["title"],
        "paragraph_anchor": _clip(section["text"], 120),
        "insertion_position": "after_section",
        "caption": "Kept as a formula block because the paragraph explicitly uses an equation rather than a visual scene or data story.",
        "confidence": confidence,
        "rationale": "A formula block is appropriate only when the section already contains an explicit equation.",
        "origin": "generated",
        "approval_status": "proposed",
        "equation_spec": {
            "label": section["title"],
            "latex": latex,
        },
        "provenance": _build_generated_provenance(
            section_title=section["title"],
            rationale="Extracted from the report section itself instead of being invented as extra math decoration.",
            evidence_refs=evidence_refs,
            references=references,
            basis=["report_markdown", "evidence_map"],
        ),
    }


def _build_external_image_candidate(
    *,
    section: dict[str, Any],
    visual_index: int,
    ranked_image: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"visual-{visual_index}",
        "type": "external_image",
        "title": ranked_image.get("source_title") or section["title"],
        "section_title": section["title"],
        "paragraph_anchor": _clip(section["text"], 120),
        "insertion_position": "after_section",
        "caption": ranked_image.get("caption")
        or "Selected because it directly illustrates the paragraph context and outperformed generated alternatives.",
        "confidence": float(ranked_image.get("confidence") or 0.0),
        "rationale": ranked_image.get("selection_reason")
        or "Selected external image with higher contextual fit than the available generated options.",
        "origin": "external_source",
        "approval_status": "proposed",
        "image_spec": {
            "image_url": ranked_image.get("image_url"),
            "alt_text": ranked_image.get("alt_text"),
            "thumbnail_url": ranked_image.get("thumbnail_url"),
        },
        "provenance": {
            "kind": "external_source",
            "source_url": ranked_image.get("source_url") or ranked_image.get("image_url"),
            "source_title": ranked_image.get("source_title"),
            "source_type": ranked_image.get("source_type"),
            "trust_note": ranked_image.get("trust_note")
            or f"External visual candidate ranked with trust {ranked_image.get('trust_rank', 0)}.",
            "why_selected": ranked_image.get("selection_reason"),
            "supported_section": section["title"],
            "basis": ["external_visual_candidate"],
            "basis_provenance": [EvidenceProvenance.EXTERNAL_RESEARCH.value],
            "evidence_refs": [],
        },
    }


def _choose_section_visual(
    *,
    best_generated: dict[str, Any] | None,
    best_external_image: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if best_generated is None:
        return best_external_image
    if best_external_image is None:
        return best_generated

    if float(best_external_image["confidence"]) >= float(best_generated["confidence"]) + 0.08:
        return best_external_image
    return best_generated


def _extract_table_rows(lines: Sequence[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_line in lines:
        cleaned = _normalize_line(raw_line)
        if not cleaned:
            continue
        if ":" in cleaned:
            left, right = [part.strip() for part in cleaned.split(":", 1)]
            if left and right:
                rows.append([_clip(left, 32), _clip(right, 120)])
                continue
        if " - " in cleaned:
            left, right = [part.strip() for part in cleaned.split(" - ", 1)]
            if left and right:
                rows.append([_clip(left, 32), _clip(right, 120)])
                continue
        if len(cleaned.split()) >= 4:
            rows.append([f"Point {len(rows) + 1}", _clip(cleaned, 120)])
    return rows


def _extract_numeric_datapoints(lines: Sequence[str]) -> list[dict[str, Any]]:
    datapoints: list[dict[str, Any]] = []
    for raw_line in lines:
        cleaned = _normalize_line(raw_line)
        if not cleaned:
            continue
        match = re.match(
            r"(?P<label>[^0-9]{2,40}?)[\s:：-]+(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|명|건|점|kg|g|cm|mm|℃|회|시간|년)?",
            cleaned,
        )
        if not match:
            continue
        label = _clip(match.group("label").strip(" -:"), 24)
        if not label:
            continue
        datapoints.append(
            {
                "label": label,
                "value": float(match.group("value")),
                "value_token": f"{match.group('value')}{match.group('unit') or ''}",
                "unit": match.group("unit") or "",
            }
        )
    return datapoints


def _datapoint_is_grounded(datapoint: dict[str, Any], grounding_text: str) -> bool:
    if not grounding_text.strip():
        return False
    return datapoint["value_token"] in grounding_text or str(int(datapoint["value"])) in grounding_text


def _extract_steps(lines: Sequence[str]) -> list[str]:
    steps: list[str] = []
    for raw_line in lines:
        cleaned = _normalize_line(raw_line)
        if not cleaned:
            continue
        if "->" in cleaned or "→" in cleaned:
            parts = [part.strip() for part in re.split(r"->|→", cleaned) if part.strip()]
            steps.extend(_clip(part, 80) for part in parts)
            continue
        if re.match(r"^\d+\.", raw_line.strip()) or raw_line.strip().startswith("- "):
            steps.append(_clip(cleaned, 80))
    deduped: list[str] = []
    seen: set[str] = set()
    for step in steps:
        key = step.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(step)
    return deduped


def _extract_equation(text: str) -> str | None:
    block_match = _LATEX_BLOCK_RE.search(text)
    if block_match:
        return block_match.group("latex").strip()
    inline_match = _INLINE_LATEX_RE.search(text)
    if inline_match:
        return inline_match.group("latex").strip()
    plain_match = _PLAIN_EQUATION_RE.search(text)
    if plain_match:
        return plain_match.group("equation").strip()
    return None


def _equation_is_grounded(latex: str, grounding_text: str, section_text: str) -> bool:
    if latex in section_text:
        return True
    symbols = [token for token in _WORD_RE.findall(latex) if len(token) > 1]
    if not symbols:
        return True
    grounding_terms = _extract_terms(grounding_text)
    overlap = len({token.lower() for token in symbols} & grounding_terms)
    return overlap >= max(1, min(len(symbols), 2))


def _build_generated_provenance(
    *,
    section_title: str,
    rationale: str,
    evidence_refs: list[str],
    references: Sequence[Any],
    basis: list[str],
) -> dict[str, Any]:
    provenance_types: list[str] = []
    if references:
        provenance_types.append(EvidenceProvenance.EXTERNAL_RESEARCH.value)
    if any(ref.startswith("document:") or ref.startswith("chunk:") for ref in evidence_refs):
        provenance_types.append(EvidenceProvenance.STUDENT_RECORD.value)
    return {
        "kind": "generated",
        "source_url": None,
        "source_title": section_title,
        "source_type": "generated_visual",
        "trust_note": "Generated visual block derived from report text already in the artifact. It should be regenerated when the section changes.",
        "why_selected": rationale,
        "supported_section": section_title,
        "basis": basis,
        "basis_provenance": provenance_types,
        "evidence_refs": evidence_refs,
    }


def _extract_evidence_refs(evidence_map: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for value in evidence_map.values():
        refs.extend(_extract_refs_from_value(value))
    deduped: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        key = ref.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped[:6]


def _extract_refs_from_value(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).strip().lower()
            if key_text in {"source", "source_id", "supported_by", "citation", "reference", "출처", "異쒖쿂"}:
                refs.extend(_extract_refs_from_value(item))
            elif isinstance(item, str) and (item.startswith("reference:") or item.startswith("turn:") or item.startswith("document:") or item.startswith("chunk:")):
                refs.append(item)
    elif isinstance(value, list):
        for item in value:
            refs.extend(_extract_refs_from_value(item))
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("reference:", "turn:", "document:", "chunk:")):
            refs.append(stripped)
    return refs


def _serialize_grounding_turns(turns: Sequence[Any]) -> str:
    parts: list[str] = []
    for turn in turns:
        text = str(getattr(turn, "query", "") or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _serialize_grounding_references(references: Sequence[Any]) -> str:
    parts: list[str] = []
    for reference in references:
        text = str(getattr(reference, "text_content", "") or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _serialize_evidence_map(evidence_map: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in evidence_map.items():
        if isinstance(value, dict):
            value_text = " ".join(str(item) for item in value.values())
        else:
            value_text = str(value)
        parts.append(f"{key} {value_text}")
    return "\n".join(parts)


def _normalize_line(line: str) -> str:
    cleaned = _BULLET_RE.sub("", (line or "").strip())
    cleaned = cleaned.replace("### ", "").replace("## ", "").strip()
    return cleaned


def _extract_terms(text: str) -> set[str]:
    return {match.group(0).lower() for match in _WORD_RE.finditer(text or "")}


def _overlap_ratio(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set)


def _looks_decorative(text: str) -> bool:
    normalized = text.lower()
    return any(keyword in normalized for keyword in _DECORATIVE_IMAGE_KEYWORDS)


def _looks_explanatory_image(candidate_text: str, section_text: str) -> bool:
    combined = f"{candidate_text} {section_text}".lower()
    return any(keyword in combined for keyword in {"diagram", "schematic", "figure", "process", "workflow", "map", "chart", "structure"})


def _clip(text: str, length: int) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= length:
        return normalized
    return f"{normalized[:length].rstrip()}..."
