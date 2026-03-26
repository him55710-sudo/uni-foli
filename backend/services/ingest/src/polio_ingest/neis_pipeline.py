from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
import re
import sys
from typing import Any

import pdfplumber

from polio_ingest.masking import MaskingPipeline
from polio_ingest.models import ParsedChunkPayload, ParsedDocumentPayload

try:
    from polio_parsers.opendataloader_adapter import OpenDataLoaderAdapter, OpenDataLoaderError
except ImportError:
    from polio_shared.paths import find_project_root

    sys.path.append(str(find_project_root() / "packages" / "parsers" / "src"))
    from polio_parsers.opendataloader_adapter import OpenDataLoaderAdapter, OpenDataLoaderError

logger = logging.getLogger(__name__)

SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "교과학습발달상황": ("교과학습발달상황", "교과 학습 발달 상황", "세부능력 및 특기사항", "세특"),
    "창의적체험활동": ("창의적체험활동", "자율활동", "동아리활동", "진로활동", "봉사활동"),
    "행동특성 및 종합의견": ("행동특성 및 종합의견", "행동특성", "종합의견"),
    "독서활동": ("독서활동", "독서 활동"),
    "수상경력": ("수상경력", "수상 경력"),
}

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "school_year": ("학년", "school_year", "school year"),
    "semester": ("학기", "semester"),
    "subject_group": ("교과", "교과군", "영역", "과목군", "subject_group"),
    "subject_name": ("과목", "교과목", "subject", "subject_name"),
    "unit_or_credit": ("단위", "단위수", "이수", "credit", "unit"),
    "achievement": ("성취도", "등급", "원점수", "achievement"),
    "special_notes_text": (
        "세부능력 및 특기사항",
        "세특",
        "특기사항",
        "special_notes",
        "비고",
    ),
}


@dataclass(slots=True)
class RouteDecision:
    document_kind: str
    selected_strategy: str
    parse_mode: str
    ocr_enabled: bool
    confidence: float
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def inspect_pdf_route(file_path: Path) -> dict[str, Any]:
    page_count = 0
    total_chars = 0
    low_text_pages = 0
    image_heavy_pages = 0
    table_like_pages = 0
    mixed_signal_pages = 0

    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            try:
                text = (page.extract_text(layout=False) or "").strip()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Route inspection text extraction failed on %s: %s", file_path, exc)
                text = ""

            char_count = len(text)
            image_count = len(page.images)
            line_count = len(page.lines) + len(page.rects)
            looks_like_table = line_count >= 14 or any(
                token in text for token in ("학년", "학기", "세부능력", "과목", "창의적체험활동")
            )

            total_chars += char_count
            if char_count < 100:
                low_text_pages += 1
            if image_count > 0 and char_count < 80:
                image_heavy_pages += 1
            if looks_like_table:
                table_like_pages += 1
            if image_count > 0 and char_count >= 80:
                mixed_signal_pages += 1

    avg_chars_per_page = total_chars / max(page_count, 1)
    image_heavy_ratio = image_heavy_pages / max(page_count, 1)
    table_like_ratio = table_like_pages / max(page_count, 1)
    mixed_ratio = mixed_signal_pages / max(page_count, 1)

    if image_heavy_ratio >= 0.4 and avg_chars_per_page < 180:
        decision = RouteDecision(
            document_kind="scanned_or_image_heavy",
            selected_strategy="odl_hybrid",
            parse_mode="hybrid",
            ocr_enabled=True,
            confidence=0.78,
            reasons=[
                "multiple pages look image-heavy with sparse embedded text",
                "ocr is likely required to recover Korean and English mixed content",
            ],
        )
    elif table_like_ratio >= 0.4 or mixed_ratio >= 0.3:
        decision = RouteDecision(
            document_kind="mixed_or_complex_table",
            selected_strategy="odl_hybrid",
            parse_mode="hybrid",
            ocr_enabled=True,
            confidence=0.7,
            reasons=[
                "table-heavy layout or mixed text/image signals detected",
                "hybrid parsing is safer for NEIS continuation tables",
            ],
        )
    else:
        decision = RouteDecision(
            document_kind="digital_born",
            selected_strategy="odl_heuristic",
            parse_mode="heuristic",
            ocr_enabled=False,
            confidence=0.84,
            reasons=[
                "embedded text density is high enough for a digital-born PDF path",
                "document does not look image-heavy",
            ],
        )

    decision.metrics = {
        "page_count": page_count,
        "avg_chars_per_page": round(avg_chars_per_page, 2),
        "low_text_pages": low_text_pages,
        "image_heavy_pages": image_heavy_pages,
        "table_like_pages": table_like_pages,
        "mixed_signal_pages": mixed_signal_pages,
        "image_heavy_ratio": round(image_heavy_ratio, 3),
        "table_like_ratio": round(table_like_ratio, 3),
        "mixed_ratio": round(mixed_ratio, 3),
    }
    return asdict(decision)


def extract_raw_pdf_artifact(
    file_path: Path,
    *,
    route: dict[str, Any],
    odl_enabled: bool,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    attempted_odl = odl_enabled and route.get("selected_strategy", "").startswith("odl")

    if attempted_odl:
        adapter = OpenDataLoaderAdapter()
        if adapter.is_available():
            try:
                result = adapter.parse_pdf(
                    file_path,
                    parse_mode=str(route.get("parse_mode", "heuristic")),
                    ocr_enabled=bool(route.get("ocr_enabled", False)),
                )
                raw_json = {
                    "schema_version": "polio.raw_pdf.v1",
                    "source": "opendataloader",
                    "parse_mode": route.get("parse_mode", "heuristic"),
                    "ocr_enabled": route.get("ocr_enabled", False),
                    "annotated_pdf_path": result.annotated_pdf_path,
                    "trace": {
                        **result.trace_metadata,
                        "route_decision": route,
                    },
                    "payload": result.raw_json,
                }
                if _count_nested_pages(raw_json) > 0:
                    return raw_json, warnings
                warnings.append("OpenDataLoader returned an empty payload. Falling back to pdfplumber.")
            except OpenDataLoaderError as exc:
                warnings.append(f"OpenDataLoader unavailable: {exc}")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"OpenDataLoader parse failed: {exc}")
        else:
            warnings.append("OpenDataLoader is not installed. Falling back to pdfplumber.")

    fallback_raw = _extract_pdf_with_pdfplumber(file_path, route=route)
    if attempted_odl:
        fallback_raw.setdefault("trace", {})["fallback_reason"] = warnings[-1] if warnings else "low_confidence"
    return fallback_raw, warnings


def normalize_odl_payload(
    raw_json: dict[str, Any],
    *,
    source_file: str,
    route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = raw_json.get("payload") if isinstance(raw_json.get("payload"), dict) else raw_json
    page_nodes = _extract_pages(payload)
    normalized_pages: list[dict[str, Any]] = []
    normalized_elements: list[dict[str, Any]] = []
    normalized_tables: list[dict[str, Any]] = []

    for page_index, page in enumerate(page_nodes, start=1):
        page_number = _coerce_int(page.get("page_number") or page.get("page") or page_index, fallback=page_index)
        elements = _extract_elements(page)
        page_element_ids: list[str] = []

        for element_index, element in enumerate(elements):
            element_type = _normalize_element_type(element)
            element_id = str(
                element.get("element_id")
                or element.get("id")
                or element.get("uid")
                or f"page-{page_number}-element-{element_index}"
            )
            bbox = _coerce_bbox(element.get("bbox") or element.get("bounding_box") or element.get("box"))
            raw_text = _normalize_text(
                str(
                    element.get("raw_text")
                    or element.get("text")
                    or element.get("content")
                    or ""
                )
            )

            normalized_element = {
                "element_id": element_id,
                "page_number": page_number,
                "element_index": element_index,
                "element_type": element_type,
                "bbox": bbox,
                "raw_text": raw_text,
                "previous_table_id": None,
                "next_table_id": None,
                "table_id": None,
                "table_rows": [],
            }

            if element_type == "table":
                table_id = str(
                    element.get("table_id")
                    or element.get("id")
                    or element.get("uid")
                    or f"table-{page_number}-{element_index}"
                )
                rows = _normalize_table_rows(
                    element.get("table", {}).get("rows")
                    if isinstance(element.get("table"), dict)
                    else None
                    or element.get("rows")
                    or element.get("cells")
                    or []
                )
                previous_table_id = element.get("previous_table_id") or element.get("previous")
                next_table_id = element.get("next_table_id") or element.get("next")
                table_text = raw_text or _table_rows_to_text(rows)
                normalized_element.update(
                    {
                        "raw_text": table_text,
                        "table_id": table_id,
                        "previous_table_id": previous_table_id,
                        "next_table_id": next_table_id,
                        "table_rows": rows,
                    }
                )
                normalized_tables.append(
                    {
                        "table_id": table_id,
                        "page_number": page_number,
                        "element_id": element_id,
                        "bbox": bbox,
                        "raw_text": table_text,
                        "rows": rows,
                        "previous_table_id": previous_table_id,
                        "next_table_id": next_table_id,
                    }
                )

            normalized_elements.append(normalized_element)
            page_element_ids.append(element_id)

        normalized_pages.append(
            {
                "page_number": page_number,
                "width": page.get("width"),
                "height": page.get("height"),
                "element_ids": page_element_ids,
            }
        )

    parser_name = raw_json.get("source", "unknown")
    markdown_preview = _build_markdown_preview(normalized_elements)
    base_confidence = 0.55 if parser_name == "pdfplumber" else 0.82
    if route is not None:
        base_confidence = round((base_confidence * 0.6) + (float(route.get("confidence", 0.0)) * 0.4), 2)

    parse_confidence = round(
        min(
            0.98,
            max(
                0.25,
                base_confidence
                + (0.03 if normalized_tables else -0.05)
                + (0.02 if normalized_elements else -0.1),
            ),
        ),
        2,
    )

    return {
        "schema_version": "polio.neis.normalized.v1",
        "source_file": source_file,
        "parser_name": parser_name,
        "page_count": len(normalized_pages),
        "pages": normalized_pages,
        "elements": normalized_elements,
        "tables": normalized_tables,
        "markdown_preview": markdown_preview,
        "parse_confidence": parse_confidence,
        "trace": {
            "route": route or {},
            "raw_trace": raw_json.get("trace", {}),
            "normalized_element_count": len(normalized_elements),
            "normalized_table_count": len(normalized_tables),
        },
    }


def stitch_neis_context(normalized_artifact: dict[str, Any]) -> dict[str, Any]:
    tables = sorted(
        normalized_artifact.get("tables", []),
        key=lambda item: (item.get("page_number") or 0, item.get("table_id") or ""),
    )
    table_by_id = {table["table_id"]: table for table in tables}
    visited: set[str] = set()
    chains: list[dict[str, Any]] = []

    for table in tables:
        table_id = table["table_id"]
        if table_id in visited:
            continue
        if table.get("previous_table_id") and table.get("previous_table_id") in table_by_id:
            continue

        chain_tables = [table]
        visited.add(table_id)
        current = table
        stitch_reasons: list[str] = []
        while current.get("next_table_id") and current["next_table_id"] in table_by_id:
            next_table = table_by_id[current["next_table_id"]]
            if next_table["table_id"] in visited:
                break
            chain_tables.append(next_table)
            visited.add(next_table["table_id"])
            stitch_reasons.append("odl_previous_next_link")
            current = next_table

        chains.append(_build_table_chain(chain_tables, stitch_reasons=stitch_reasons))

    for table in tables:
        if table["table_id"] not in visited:
            visited.add(table["table_id"])
            chains.append(_build_table_chain([table], stitch_reasons=[]))

    merged_chains: list[dict[str, Any]] = []
    for chain in sorted(chains, key=lambda item: (item["page_span"][0], item["table_ids"][0])):
        if not merged_chains:
            merged_chains.append(chain)
            continue
        previous_chain = merged_chains[-1]
        should_merge, reasons = _should_merge_chains(previous_chain, chain)
        if should_merge:
            merged_chains[-1] = _merge_chains(previous_chain, chain, reasons)
        else:
            merged_chains.append(chain)

    for chain in merged_chains:
        expanded_rows = _expand_chain_rows(chain["rows"])
        chain["expanded_rows"] = expanded_rows
        chain["stitch_confidence"] = round(
            min(
                0.97,
                0.55
                + (0.22 if "odl_previous_next_link" in chain["stitch_reasons"] else 0.0)
                + (0.16 if "repeated_header_or_context" in chain["stitch_reasons"] else 0.0)
                + (0.08 if chain["continuation_flag"] else 0.0),
            ),
            2,
        )
        chain["needs_review"] = chain["stitch_confidence"] < 0.6

    table_chain_map = {table_id: chain["table_chain_id"] for chain in merged_chains for table_id in chain["table_ids"]}
    page_span_map = {table_id: chain["page_span"] for chain in merged_chains for table_id in chain["table_ids"]}
    continuation_map = {
        table_id: chain["continuation_flag"] for chain in merged_chains for table_id in chain["table_ids"]
    }

    for table in normalized_artifact.get("tables", []):
        table["table_chain_id"] = table_chain_map.get(table["table_id"])
        table["page_span"] = page_span_map.get(table["table_id"], [table["page_number"], table["page_number"]])
        table["continuation_flag"] = continuation_map.get(table["table_id"], False)

    for element in normalized_artifact.get("elements", []):
        table_id = element.get("table_id")
        if not table_id:
            continue
        element["table_chain_id"] = table_chain_map.get(table_id)
        element["page_span"] = page_span_map.get(table_id, [element["page_number"], element["page_number"]])
        element["continuation_flag"] = continuation_map.get(table_id, False)

    normalized_artifact["table_chains"] = merged_chains
    normalized_artifact["stitch_confidence"] = round(
        min(0.96, max((chain["stitch_confidence"] for chain in merged_chains), default=0.55)),
        2,
    )
    normalized_artifact.setdefault("trace", {})["stitching"] = {
        "table_chain_count": len(merged_chains),
        "steps": [
            "previous_next_table_id",
            "repeated_header_or_subject_context",
            "row_span_column_span_structure_correction",
        ],
    }
    return normalized_artifact


def _build_table_chain(chain_tables: list[dict[str, Any]], *, stitch_reasons: list[str]) -> dict[str, Any]:
    raw_rows: list[dict[str, Any]] = []
    raw_text_parts: list[str] = []
    table_ids = [table["table_id"] for table in chain_tables]
    page_numbers = [table["page_number"] for table in chain_tables]

    for table in chain_tables:
        rows = table.get("rows", [])
        if raw_rows and rows and _row_signature(raw_rows[0]) == _row_signature(rows[0]):
            rows = rows[1:]
        raw_rows.extend(rows)
        raw_text_parts.append(table.get("raw_text", ""))

    return {
        "table_chain_id": f"chain-{'-'.join(table_ids)}",
        "table_ids": table_ids,
        "page_span": [min(page_numbers), max(page_numbers)],
        "continuation_flag": len(table_ids) > 1,
        "rows": raw_rows,
        "raw_text": _normalize_text("\n".join(part for part in raw_text_parts if part)),
        "stitch_reasons": list(dict.fromkeys(stitch_reasons)),
    }


def _should_merge_chains(left_chain: dict[str, Any], right_chain: dict[str, Any]) -> tuple[bool, list[str]]:
    if right_chain["page_span"][0] - left_chain["page_span"][1] > 1:
        return False, []

    left_header = _header_signature(left_chain.get("rows", []))
    right_header = _header_signature(right_chain.get("rows", []))
    left_context = _extract_chain_context(left_chain)
    right_context = _extract_chain_context(right_chain)

    score = 0.0
    reasons: list[str] = []
    if left_header and left_header == right_header:
        score += 0.45
        reasons.append("repeated_header_or_context")
    if left_context["section_type"] and left_context["section_type"] == right_context["section_type"]:
        score += 0.15
    if left_context["subject_name"] and left_context["subject_name"] == right_context["subject_name"]:
        score += 0.2
    if left_context["school_year"] and left_context["school_year"] == right_context["school_year"]:
        score += 0.1
    if left_context["semester"] and left_context["semester"] == right_context["semester"]:
        score += 0.1
    if _looks_like_continuation_row(right_chain.get("rows", [])):
        score += 0.15

    return score >= 0.65, reasons


def _merge_chains(left_chain: dict[str, Any], right_chain: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    merged_rows = list(left_chain.get("rows", []))
    right_rows = list(right_chain.get("rows", []))
    if merged_rows and right_rows and _row_signature(merged_rows[0]) == _row_signature(right_rows[0]):
        right_rows = right_rows[1:]

    return {
        "table_chain_id": f"{left_chain['table_chain_id']}__{right_chain['table_chain_id']}",
        "table_ids": [*left_chain["table_ids"], *right_chain["table_ids"]],
        "page_span": [left_chain["page_span"][0], right_chain["page_span"][1]],
        "continuation_flag": True,
        "rows": [*merged_rows, *right_rows],
        "raw_text": _normalize_text(f"{left_chain.get('raw_text', '')}\n{right_chain.get('raw_text', '')}"),
        "stitch_reasons": list(dict.fromkeys([*left_chain["stitch_reasons"], *right_chain["stitch_reasons"], *reasons])),
    }


def _expand_chain_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded_rows: list[dict[str, Any]] = []
    pending_row_spans: dict[int, tuple[int, dict[str, Any]]] = {}

    for row in rows:
        expanded_cells: list[dict[str, Any]] = []
        column_index = 0
        cells = list(row.get("cells", []))

        for cell in cells:
            while column_index in pending_row_spans and pending_row_spans[column_index][0] > 0:
                remaining, source_cell = pending_row_spans[column_index]
                expanded_cells.append(
                    {
                        "text": "",
                        "row_span": 1,
                        "column_span": 1,
                        "bbox": source_cell.get("bbox"),
                        "span_placeholder": True,
                        "source_cell_id": source_cell.get("cell_id"),
                    }
                )
                pending_row_spans[column_index] = (remaining - 1, source_cell)
                if pending_row_spans[column_index][0] <= 0:
                    del pending_row_spans[column_index]
                column_index += 1

            cell_copy = dict(cell)
            cell_copy["span_placeholder"] = False
            expanded_cells.append(cell_copy)
            row_span = _coerce_int(cell.get("row_span") or 1, fallback=1)
            column_span = _coerce_int(cell.get("column_span") or 1, fallback=1)

            if row_span > 1:
                for offset in range(column_span):
                    pending_row_spans[column_index + offset] = (row_span - 1, cell_copy)

            for _ in range(1, column_span):
                expanded_cells.append(
                    {
                        "text": "",
                        "row_span": 1,
                        "column_span": 1,
                        "bbox": cell.get("bbox"),
                        "span_placeholder": True,
                        "source_cell_id": cell.get("cell_id"),
                    }
                )
            column_index += column_span

        while column_index in pending_row_spans and pending_row_spans[column_index][0] > 0:
            remaining, source_cell = pending_row_spans[column_index]
            expanded_cells.append(
                {
                    "text": "",
                    "row_span": 1,
                    "column_span": 1,
                    "bbox": source_cell.get("bbox"),
                    "span_placeholder": True,
                    "source_cell_id": source_cell.get("cell_id"),
                }
            )
            pending_row_spans[column_index] = (remaining - 1, source_cell)
            if pending_row_spans[column_index][0] <= 0:
                del pending_row_spans[column_index]
            column_index += 1

        expanded_rows.append({"row_index": row.get("row_index"), "cells": expanded_cells})

    max_columns = max((len(row["cells"]) for row in expanded_rows), default=0)
    for row in expanded_rows:
        while len(row["cells"]) < max_columns:
            row["cells"].append(
                {
                    "text": "",
                    "row_span": 1,
                    "column_span": 1,
                    "bbox": None,
                    "span_placeholder": True,
                    "source_cell_id": None,
                }
            )
    return expanded_rows


def map_neis_semantics(
    stitched_artifact: dict[str, Any],
    *,
    masking_pipeline: MaskingPipeline | None = None,
) -> dict[str, Any]:
    masking_pipeline = masking_pipeline or MaskingPipeline()
    sections: list[dict[str, Any]] = []
    evidence_references: list[dict[str, Any]] = []
    masking_counter: Counter[str] = Counter()
    masking_warnings: list[str] = []
    record_confidences: list[float] = []

    page_text_lookup = _page_text_lookup(stitched_artifact)
    for chain_index, chain in enumerate(stitched_artifact.get("table_chains", [])):
        page_span = chain["page_span"]
        context_text = _normalize_text(
            "\n".join(page_text_lookup.get(page_number, "") for page_number in range(page_span[0], page_span[1] + 1))
        )
        chain_text = _normalize_text(f"{context_text}\n{chain.get('raw_text', '')}")
        section_type = _classify_section_type(chain_text)

        if section_type == "교과학습발달상황":
            records, references = _map_course_records(chain, section_type, masking_pipeline)
        else:
            records, references = _map_activity_records(chain, section_type, masking_pipeline)

        evidence_references.extend(references)
        record_confidences.extend(record["source_confidence"] for record in records)
        for record in records:
            masking_counter.update(record.get("masking", {}).get("pattern_hits", {}))
            masking_warnings.extend(record.get("masking", {}).get("warnings", []))

        section_text = _normalize_text("\n".join(record["normalized_text"] for record in records if record["normalized_text"]))
        section_masked_text = _normalize_text("\n".join(record["masked_text"] for record in records if record["masked_text"]))
        section_confidence = round(sum(record["source_confidence"] for record in records) / max(len(records), 1), 2)
        sections.append(
            {
                "section_id": f"section-{chain_index}",
                "section_type": section_type,
                "page_span": page_span,
                "table_chain_id": chain["table_chain_id"],
                "continuation_flag": chain["continuation_flag"],
                "raw_text": chain.get("raw_text", ""),
                "normalized_text": section_text,
                "masked_text": section_masked_text,
                "source_confidence": section_confidence,
                "needs_review": section_confidence < 0.65 or any(record["needs_review"] for record in records),
                "records": records,
            }
        )

    if not sections:
        text_sections = _map_text_only_sections(stitched_artifact, masking_pipeline)
        sections.extend(text_sections["sections"])
        evidence_references.extend(text_sections["evidence_references"])
        record_confidences.extend(text_sections["record_confidences"])
        masking_counter.update(text_sections["masking_counter"])
        masking_warnings.extend(text_sections["masking_warnings"])

    semantic_mapping_confidence = round(sum(record_confidences) / max(len(record_confidences), 1), 2)
    needs_review = (
        stitched_artifact.get("parse_confidence", 0.0) < 0.6
        or stitched_artifact.get("stitch_confidence", 0.0) < 0.6
        or semantic_mapping_confidence < 0.65
        or any(section["needs_review"] for section in sections)
    )

    return {
        "schema_version": "polio.neis.document.v1",
        "document_type": "neis_student_record",
        "source_file": stitched_artifact.get("source_file"),
        "page_count": stitched_artifact.get("page_count", 0),
        "parse_confidence": stitched_artifact.get("parse_confidence", 0.0),
        "stitch_confidence": stitched_artifact.get("stitch_confidence", 0.0),
        "semantic_mapping_confidence": semantic_mapping_confidence,
        "needs_review": needs_review,
        "sections": sections,
        "evidence_references": evidence_references,
        "parse_trace": {
            "route": stitched_artifact.get("trace", {}).get("route", {}),
            "raw_trace": stitched_artifact.get("trace", {}).get("raw_trace", {}),
            "stitching": stitched_artifact.get("trace", {}).get("stitching", {}),
            "section_count": len(sections),
            "record_count": sum(len(section["records"]) for section in sections),
        },
        "masking": {
            "pattern_hits": dict(masking_counter),
            "warnings": masking_warnings,
        },
    }


def parse_pdf_with_neis_pipeline(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
    odl_enabled: bool,
) -> ParsedDocumentPayload:
    route = inspect_pdf_route(file_path)
    raw_artifact, extraction_warnings = extract_raw_pdf_artifact(file_path, route=route, odl_enabled=odl_enabled)
    normalized_artifact = normalize_odl_payload(raw_artifact, source_file=file_path.name, route=route)
    stitched_artifact = stitch_neis_context(normalized_artifact)
    neis_document = map_neis_semantics(stitched_artifact)
    content_text, content_markdown, chunks, chunk_evidence_map = _build_masked_outputs(
        neis_document,
        chunk_size_chars=chunk_size_chars,
        overlap_chars=overlap_chars,
    )

    warnings = [*extraction_warnings, *neis_document.get("masking", {}).get("warnings", [])]
    actionable_warnings = [
        warning
        for warning in warnings
        if "OpenDataLoader is not installed" not in warning
        and "OpenDataLoader unavailable" not in warning
    ]
    processing_status = "parsed"
    if ((neis_document["needs_review"] and stitched_artifact.get("table_chains")) or actionable_warnings):
        processing_status = "partial"
    if not chunks:
        processing_status = "failed"

    analysis_artifact = {
        "schema_version": "student_artifact_parse.v1",
        "artifact_type": "neis_document",
        "route": route,
        "parse_confidence": neis_document["parse_confidence"],
        "stitch_confidence": neis_document["stitch_confidence"],
        "semantic_mapping_confidence": neis_document["semantic_mapping_confidence"],
        "needs_review": neis_document["needs_review"],
        "evidence_references": neis_document["evidence_references"],
        "neis_document": neis_document,
        "chunk_evidence_map": chunk_evidence_map,
    }
    metadata = {
        "filename": file_path.name,
        "parser_route": route,
        "warnings": warnings,
        "raw_parse_artifact": raw_artifact,
        "normalized_artifact": stitched_artifact,
        "student_artifact_parse": analysis_artifact,
        "masking": neis_document.get("masking", {}),
        "annotated_pdf_path": raw_artifact.get("annotated_pdf_path"),
        "table_chain_count": len(stitched_artifact.get("table_chains", [])),
    }

    return ParsedDocumentPayload(
        parser_name=str(raw_artifact.get("source", "pdfplumber")),
        source_extension=".pdf",
        page_count=int(stitched_artifact.get("page_count", 0)),
        word_count=len(content_text.split()),
        content_text=content_text,
        content_markdown=content_markdown,
        metadata=_clean_metadata(metadata),
        chunks=chunks,
        processing_status=processing_status,
        masking_status="masked" if content_text else "failed",
        warnings=warnings,
        raw_artifact=raw_artifact,
        masked_artifact={
            "schema_version": "polio.neis.masked_artifact.v1",
            "content_text": content_text,
            "content_markdown": content_markdown,
            "chunk_evidence_map": chunk_evidence_map,
        },
        analysis_artifact=analysis_artifact,
        parse_confidence=float(neis_document["parse_confidence"]),
        needs_review=bool(neis_document["needs_review"]),
    )


def _map_course_records(
    chain: dict[str, Any],
    section_type: str,
    masking_pipeline: MaskingPipeline,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    expanded_rows = chain.get("expanded_rows") or _expand_chain_rows(chain.get("rows", []))
    header_map, data_rows = _resolve_header_map(expanded_rows)
    records: list[dict[str, Any]] = []
    evidence_references: list[dict[str, Any]] = []
    carry_context = {
        "school_year": "",
        "semester": "",
        "subject_group": "",
        "subject_name": "",
        "unit_or_credit": "",
        "achievement": "",
    }

    for row_index, row in enumerate(data_rows):
        values = [_normalize_text(cell.get("text", "")) for cell in row.get("cells", [])]
        if not any(values):
            continue

        raw_record_values: dict[str, str] = {}
        for field_name, column_index in header_map.items():
            raw_record_values[field_name] = _safe_lookup(values, column_index)

        is_continuation_row = (
            bool(records)
            and not any(
                raw_record_values.get(field_name)
                for field_name in ("school_year", "semester", "subject_group", "subject_name", "unit_or_credit", "achievement")
            )
            and bool(raw_record_values.get("special_notes_text"))
        )

        if is_continuation_row:
            appended_notes = raw_record_values["special_notes_text"]
            records[-1]["special_notes_text"] = _normalize_text(f"{records[-1]['special_notes_text']} {appended_notes}")
            records[-1]["raw_text"] = _normalize_text(f"{records[-1]['raw_text']}\n{_row_text(values)}")
            records[-1]["normalized_text"] = _normalize_text(f"{records[-1]['normalized_text']} {appended_notes}")
            records[-1]["masked_text"] = masking_pipeline.apply_masking(records[-1]["normalized_text"])
            records[-1]["page_span"] = chain["page_span"]
            evidence_references[-1]["page_span"] = chain["page_span"]
            continue

        record_values = dict(raw_record_values)

        for field_name, prior_value in carry_context.items():
            if not record_values.get(field_name):
                record_values[field_name] = prior_value
            elif field_name != "special_notes_text":
                carry_context[field_name] = record_values[field_name]

        notes = record_values.get("special_notes_text", "")
        normalized_text = _normalize_text(
            " | ".join(
                part
                for part in (
                    record_values.get("school_year"),
                    record_values.get("semester"),
                    record_values.get("subject_group"),
                    record_values.get("subject_name"),
                    record_values.get("unit_or_credit"),
                    record_values.get("achievement"),
                    notes,
                )
                if part
            )
        )
        masking_result = masking_pipeline.mask_text(normalized_text)
        confidence = _score_course_record(record_values, header_map, notes)
        bbox_refs = [cell.get("bbox") for cell in row.get("cells", []) if cell.get("bbox") is not None]
        record_id = f"{chain['table_chain_id']}-course-{row_index}"
        records.append(
            {
                "record_id": record_id,
                "record_type": "NeisCourseRecord",
                "section_type": section_type,
                "school_year": record_values.get("school_year", ""),
                "semester": record_values.get("semester", ""),
                "subject_group": record_values.get("subject_group", ""),
                "subject_name": record_values.get("subject_name", ""),
                "unit_or_credit": record_values.get("unit_or_credit", ""),
                "achievement": record_values.get("achievement", ""),
                "special_notes_text": notes,
                "raw_text": _row_text(values),
                "normalized_text": normalized_text,
                "masked_text": masking_result.text,
                "bbox_refs": bbox_refs,
                "source_confidence": confidence,
                "page_span": chain["page_span"],
                "needs_review": confidence < 0.65 or not record_values.get("subject_name"),
                "masking": {
                    "pattern_hits": masking_result.pattern_hits,
                    "warnings": masking_result.warnings,
                },
            }
        )
        evidence_references.append(
            {
                "reference_id": record_id,
                "section_type": section_type,
                "page_span": chain["page_span"],
                "bbox_refs": bbox_refs,
                "table_chain_id": chain["table_chain_id"],
                "subject_name": record_values.get("subject_name", ""),
            }
        )

    return records, evidence_references


def _map_activity_records(
    chain: dict[str, Any],
    section_type: str,
    masking_pipeline: MaskingPipeline,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    expanded_rows = chain.get("expanded_rows") or _expand_chain_rows(chain.get("rows", []))
    header_map, data_rows = _resolve_header_map(expanded_rows)
    records: list[dict[str, Any]] = []
    evidence_references: list[dict[str, Any]] = []

    for row_index, row in enumerate(data_rows):
        values = [_normalize_text(cell.get("text", "")) for cell in row.get("cells", [])]
        if not any(values):
            continue

        text = _row_text(values)
        activity_name = _safe_lookup(values, header_map.get("subject_name")) or next(
            (value for value in values if value),
            section_type,
        )
        masking_result = masking_pipeline.mask_text(text)
        bbox_refs = [cell.get("bbox") for cell in row.get("cells", []) if cell.get("bbox") is not None]
        confidence = round(min(0.9, 0.6 + (0.1 if len(text) >= 20 else 0.0) + (0.1 if section_type != "미분류" else 0.0)), 2)
        record_id = f"{chain['table_chain_id']}-activity-{row_index}"
        records.append(
            {
                "record_id": record_id,
                "record_type": "NeisActivityRecord",
                "section_type": section_type,
                "activity_name": activity_name,
                "school_year": "",
                "semester": "",
                "subject_group": "",
                "subject_name": activity_name,
                "unit_or_credit": "",
                "achievement": "",
                "special_notes_text": text,
                "raw_text": text,
                "normalized_text": text,
                "masked_text": masking_result.text,
                "bbox_refs": bbox_refs,
                "source_confidence": confidence,
                "page_span": chain["page_span"],
                "needs_review": confidence < 0.65,
                "masking": {
                    "pattern_hits": masking_result.pattern_hits,
                    "warnings": masking_result.warnings,
                },
            }
        )
        evidence_references.append(
            {
                "reference_id": record_id,
                "section_type": section_type,
                "page_span": chain["page_span"],
                "bbox_refs": bbox_refs,
                "table_chain_id": chain["table_chain_id"],
                "subject_name": activity_name,
            }
        )

    return records, evidence_references


def _map_text_only_sections(
    stitched_artifact: dict[str, Any],
    masking_pipeline: MaskingPipeline,
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    evidence_references: list[dict[str, Any]] = []
    masking_counter: Counter[str] = Counter()
    masking_warnings: list[str] = []
    record_confidences: list[float] = []

    for page_number, text in sorted(_page_text_lookup(stitched_artifact).items()):
        if not text:
            continue
        section_type = _classify_section_type(text)
        masking_result = masking_pipeline.mask_text(text)
        record_confidence = 0.62 if section_type != "미분류" else 0.48
        record_confidences.append(record_confidence)
        masking_counter.update(masking_result.pattern_hits)
        masking_warnings.extend(masking_result.warnings)
        record_id = f"text-section-{page_number}"
        record = {
            "record_id": record_id,
            "record_type": "NeisActivityRecord",
            "section_type": section_type,
            "activity_name": section_type,
            "school_year": "",
            "semester": "",
            "subject_group": "",
            "subject_name": section_type,
            "unit_or_credit": "",
            "achievement": "",
            "special_notes_text": text,
            "raw_text": text,
            "normalized_text": text,
            "masked_text": masking_result.text,
            "bbox_refs": [],
            "source_confidence": record_confidence,
            "page_span": [page_number, page_number],
            "needs_review": True,
            "masking": {
                "pattern_hits": masking_result.pattern_hits,
                "warnings": masking_result.warnings,
            },
        }
        sections.append(
            {
                "section_id": record_id,
                "section_type": section_type,
                "page_span": [page_number, page_number],
                "table_chain_id": None,
                "continuation_flag": False,
                "raw_text": text,
                "normalized_text": text,
                "masked_text": masking_result.text,
                "source_confidence": record_confidence,
                "needs_review": True,
                "records": [record],
            }
        )
        evidence_references.append(
            {
                "reference_id": record_id,
                "section_type": section_type,
                "page_span": [page_number, page_number],
                "bbox_refs": [],
                "table_chain_id": None,
                "subject_name": section_type,
            }
        )

    return {
        "sections": sections,
        "evidence_references": evidence_references,
        "record_confidences": record_confidences,
        "masking_counter": masking_counter,
        "masking_warnings": masking_warnings,
    }


def _extract_pdf_with_pdfplumber(file_path: Path, *, route: dict[str, Any]) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    total_failures: list[dict[str, Any]] = []

    with pdfplumber.open(file_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            elements: list[dict[str, Any]] = []
            try:
                page_text = _normalize_text(page.extract_text(layout=True) or "")
            except Exception as exc:  # noqa: BLE001
                page_text = ""
                total_failures.append({"page_number": page_number, "message": f"text extraction failed: {exc}"})

            if page_text:
                elements.append(
                    {
                        "element_id": f"page-{page_number}-text-0",
                        "type": "text",
                        "bbox": [0.0, 0.0, float(page.width), float(page.height)],
                        "text": page_text,
                    }
                )

            try:
                tables = page.find_tables()
            except Exception as exc:  # noqa: BLE001
                tables = []
                total_failures.append({"page_number": page_number, "message": f"table detection failed: {exc}"})

            for table_index, table in enumerate(tables):
                try:
                    extracted_rows = table.extract() or []
                except Exception as exc:  # noqa: BLE001
                    total_failures.append({"page_number": page_number, "message": f"table extraction failed: {exc}"})
                    continue

                elements.append(
                    {
                        "element_id": f"page-{page_number}-table-{table_index}",
                        "type": "table",
                        "table_id": f"table-{page_number}-{table_index}",
                        "bbox": list(table.bbox) if table.bbox else None,
                        "rows": [
                            {
                                "row_index": row_index,
                                "cells": [
                                    {
                                        "text": "" if cell is None else str(cell),
                                        "row_span": 1,
                                        "column_span": 1,
                                        "bbox": None,
                                    }
                                    for cell in row
                                ],
                            }
                            for row_index, row in enumerate(extracted_rows)
                            if row
                        ],
                    }
                )

            pages.append(
                {
                    "page_number": page_number,
                    "width": float(page.width),
                    "height": float(page.height),
                    "elements": elements,
                }
            )

    return {
        "schema_version": "polio.raw_pdf.v1",
        "source": "pdfplumber",
        "parse_mode": "fallback",
        "ocr_enabled": False,
        "annotated_pdf_path": None,
        "trace": {
            "route_decision": route,
            "page_failures": total_failures,
        },
        "pages": pages,
    }


def _extract_pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    pages = payload.get("pages")
    if isinstance(pages, list):
        return [item for item in pages if isinstance(item, dict)]
    document = payload.get("document")
    if isinstance(document, dict) and isinstance(document.get("pages"), list):
        return [item for item in document["pages"] if isinstance(item, dict)]
    items = payload.get("items")
    if isinstance(items, list):
        grouped: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            if not isinstance(item, dict):
                continue
            grouped[_coerce_int(item.get("page_number") or item.get("page") or 1, fallback=1)].append(item)
        return [{"page_number": page_number, "elements": grouped[page_number]} for page_number in sorted(grouped)]
    return []


def _extract_elements(page: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("elements", "blocks", "items", "content"):
        candidate = page.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _normalize_element_type(element: dict[str, Any]) -> str:
    raw_type = str(element.get("type") or element.get("element_type") or "").lower()
    if "table" in raw_type or "grid" in raw_type or element.get("rows") or element.get("table"):
        return "table"
    if "image" in raw_type or "figure" in raw_type:
        return "image"
    return "text"


def _normalize_table_rows(raw_rows: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(raw_rows, list):
        return rows
    for row_index, raw_row in enumerate(raw_rows):
        raw_cells = raw_row.get("cells") if isinstance(raw_row, dict) else raw_row
        if not isinstance(raw_cells, list):
            continue
        cells: list[dict[str, Any]] = []
        for column_index, raw_cell in enumerate(raw_cells):
            if isinstance(raw_cell, dict):
                text = _normalize_text(str(raw_cell.get("text") or raw_cell.get("content") or raw_cell.get("raw_text") or ""))
                row_span = _coerce_int(raw_cell.get("row_span") or raw_cell.get("rowspan") or 1, fallback=1)
                column_span = _coerce_int(raw_cell.get("column_span") or raw_cell.get("col_span") or raw_cell.get("colspan") or 1, fallback=1)
                bbox = _coerce_bbox(raw_cell.get("bbox") or raw_cell.get("bounding_box") or raw_cell.get("box"))
            else:
                text = _normalize_text("" if raw_cell is None else str(raw_cell))
                row_span = 1
                column_span = 1
                bbox = None
            cells.append(
                {
                    "cell_id": f"row-{row_index}-col-{column_index}",
                    "row_index": row_index,
                    "column_index": column_index,
                    "text": text,
                    "row_span": row_span,
                    "column_span": column_span,
                    "bbox": bbox,
                }
            )
        rows.append({"row_index": row_index, "cells": cells})
    return rows


def _build_markdown_preview(elements: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for element in elements:
        if element["element_type"] == "table":
            headers = [cell["text"] for cell in element["table_rows"][0]["cells"]] if element["table_rows"] else []
            if headers:
                parts.append("| " + " | ".join(headers) + " |")
                parts.append("| " + " | ".join(["---"] * len(headers)) + " |")
                for row in element["table_rows"][1:4]:
                    parts.append("| " + " | ".join(cell["text"] for cell in row["cells"]) + " |")
        elif element["raw_text"]:
            parts.append(element["raw_text"])
    return "\n\n".join(part for part in parts if part).strip()


def _resolve_header_map(expanded_rows: list[dict[str, Any]]) -> tuple[dict[str, int | None], list[dict[str, Any]]]:
    default_map: dict[str, int | None] = {field_name: None for field_name in HEADER_ALIASES}
    if not expanded_rows:
        return default_map, []

    header_row_index = 0
    best_score = -1
    for row_index, row in enumerate(expanded_rows[:3]):
        score = 0
        texts = [_normalize_text(cell.get("text", "")) for cell in row.get("cells", [])]
        for text in texts:
            lowered = text.lower()
            if any(alias.lower() in lowered for aliases in HEADER_ALIASES.values() for alias in aliases):
                score += 1
        if score > best_score:
            header_row_index = row_index
            best_score = score

    header_cells = expanded_rows[header_row_index].get("cells", [])
    header_texts = [_normalize_text(cell.get("text", "")) for cell in header_cells]
    header_map = {field_name: None for field_name in HEADER_ALIASES}
    for column_index, text in enumerate(header_texts):
        lowered = text.lower()
        for field_name, aliases in HEADER_ALIASES.items():
            if any(alias.lower() in lowered for alias in aliases):
                header_map[field_name] = column_index
                break

    return header_map, expanded_rows[header_row_index + 1 :]


def _header_signature(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    if not rows:
        return ()
    expanded = _expand_chain_rows(rows[:1])
    if not expanded:
        return ()
    return tuple(_normalize_text(cell.get("text", "")) for cell in expanded[0].get("cells", []))


def _row_signature(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_normalize_text(cell.get("text", "")) for cell in row.get("cells", []))


def _extract_chain_context(chain: dict[str, Any]) -> dict[str, str]:
    header_map, data_rows = _resolve_header_map(chain.get("expanded_rows") or _expand_chain_rows(chain.get("rows", [])))
    first_values = [_normalize_text(cell.get("text", "")) for cell in data_rows[0].get("cells", [])] if data_rows else []
    return {
        "section_type": _classify_section_type(chain.get("raw_text", "")),
        "school_year": _safe_lookup(first_values, header_map.get("school_year")),
        "semester": _safe_lookup(first_values, header_map.get("semester")),
        "subject_name": _safe_lookup(first_values, header_map.get("subject_name")),
    }


def _looks_like_continuation_row(rows: list[dict[str, Any]]) -> bool:
    expanded_rows = _expand_chain_rows(rows[:2])
    if len(expanded_rows) < 2:
        return False
    values = [_normalize_text(cell.get("text", "")) for cell in expanded_rows[1].get("cells", [])]
    return len(values) >= 4 and not any(values[:3]) and bool(values[3])


def _classify_section_type(text: str) -> str:
    normalized = _normalize_text(text)
    for section_type, keywords in SECTION_PATTERNS.items():
        if any(keyword in normalized for keyword in keywords):
            return section_type
    return "미분류"


def _page_text_lookup(stitched_artifact: dict[str, Any]) -> dict[int, str]:
    lookup: dict[int, list[str]] = defaultdict(list)
    for element in stitched_artifact.get("elements", []):
        if element.get("element_type") == "text" and element.get("raw_text"):
            lookup[int(element["page_number"])].append(str(element["raw_text"]))
    return {page_number: _normalize_text("\n".join(parts)) for page_number, parts in lookup.items()}


def _score_course_record(record_values: dict[str, str], header_map: dict[str, int | None], notes: str) -> float:
    confidence = 0.45
    if header_map.get("subject_name") is not None:
        confidence += 0.15
    if record_values.get("subject_name"):
        confidence += 0.15
    if record_values.get("school_year"):
        confidence += 0.05
    if record_values.get("semester"):
        confidence += 0.05
    if notes:
        confidence += 0.15
    if len(notes) >= 30:
        confidence += 0.05
    return round(min(confidence, 0.95), 2)


def _build_masked_outputs(
    neis_document: dict[str, Any],
    *,
    chunk_size_chars: int,
    overlap_chars: int,
) -> tuple[str, str, list[ParsedChunkPayload], dict[str, dict[str, Any]]]:
    chunks: list[ParsedChunkPayload] = []
    chunk_evidence_map: dict[str, dict[str, Any]] = {}
    combined_parts: list[str] = []
    markdown_parts: list[str] = [f"# {Path(neis_document.get('source_file') or 'document').stem}"]
    cursor = 0
    chunk_index = 0

    for section in neis_document.get("sections", []):
        section_header = f"[{section['section_type']}]"
        combined_parts.append(section_header)
        markdown_parts.append(f"## {section['section_type']}")
        cursor += len(section_header) + 2

        for record in section.get("records", []):
            label = " / ".join(part for part in (record.get("school_year"), record.get("semester"), record.get("subject_name")) if part)
            entry_text = record.get("masked_text") or record.get("normalized_text") or record.get("raw_text") or ""
            combined_entry = f"{label}: {entry_text}" if label else entry_text
            if label:
                markdown_parts.append(f"### {label}")
            markdown_parts.append(entry_text or "_No masked text available._")
            combined_parts.append(combined_entry)
            entry_start = cursor
            cursor += len(combined_entry) + 2

            for content, local_start, local_end in _slice_text(combined_entry, chunk_size_chars, overlap_chars):
                metadata = {
                    "reference_id": record["record_id"],
                    "section_type": record["section_type"],
                    "page_span": record["page_span"],
                    "bbox_refs": record["bbox_refs"],
                    "subject_name": record.get("subject_name"),
                    "source_confidence": record["source_confidence"],
                }
                chunks.append(
                    ParsedChunkPayload(
                        chunk_index=chunk_index,
                        page_number=record["page_span"][0] if record["page_span"] else None,
                        char_start=entry_start + local_start,
                        char_end=entry_start + local_end,
                        token_estimate=_estimate_tokens(content),
                        content_text=content,
                        metadata=metadata,
                    )
                )
                chunk_evidence_map[str(chunk_index)] = metadata
                chunk_index += 1

    content_text = _normalize_text("\n\n".join(part for part in combined_parts if part))
    content_markdown = _normalize_text("\n\n".join(part for part in markdown_parts if part))
    return content_text, content_markdown, chunks, chunk_evidence_map


def _row_text(values: list[str]) -> str:
    return _normalize_text(" | ".join(value for value in values if value))


def _slice_text(text: str, chunk_size_chars: int, overlap_chars: int) -> list[tuple[str, int, int]]:
    if not text:
        return []
    step = max(chunk_size_chars - overlap_chars, 1)
    sliced: list[tuple[str, int, int]] = []
    for start in range(0, len(text), step):
        end = min(start + chunk_size_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            sliced.append((chunk, start, end))
        if end >= len(text):
            break
    return sliced


def _normalize_text(value: str) -> str:
    collapsed = value.replace("\x00", " ")
    collapsed = collapsed.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = re.sub(r"[ \t]+", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def _estimate_tokens(value: str) -> int:
    return max(1, round(len(value) / 4))


def _table_rows_to_text(rows: list[dict[str, Any]]) -> str:
    return _normalize_text("\n".join(_row_text([cell.get("text", "") for cell in row.get("cells", [])]) for row in rows))


def _coerce_bbox(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if all(key in value for key in ("x0", "top", "x1", "bottom")):
            return [float(value["x0"]), float(value["top"]), float(value["x1"]), float(value["bottom"])]
        if all(key in value for key in ("left", "top", "right", "bottom")):
            return [float(value["left"]), float(value["top"]), float(value["right"]), float(value["bottom"])]
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        try:
            return [float(value[0]), float(value[1]), float(value[2]), float(value[3])]
        except (TypeError, ValueError):
            return None
    return None


def _coerce_int(value: Any, *, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_lookup(values: list[str], index: int | None) -> str:
    if index is None or index >= len(values):
        return ""
    return values[index]


def _count_nested_pages(raw_json: dict[str, Any]) -> int:
    payload = raw_json.get("payload") if isinstance(raw_json.get("payload"), dict) else raw_json
    return len(_extract_pages(payload))


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if value not in (None, "", [], {})}
