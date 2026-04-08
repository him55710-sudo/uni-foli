from __future__ import annotations

from typing import Any
from pydantic import BaseModel

from polio_api.services.student_record_page_classifier_service import PageCategory, PageClassification


class StudentRecordSection(BaseModel):
    section_type: PageCategory
    start_page: int
    end_page: int
    pages: list[int]
    raw_text: str
    elements: list[dict[str, Any]]
    tables: list[dict[str, Any]]


class StudentRecordSectionParserService:
    """
    Compatibility wrapper used by StudentRecordPipelineService.
    """

    def parse_sections(self, classifications: list[PageClassification]) -> list[StudentRecordSection]:
        if not classifications:
            return []

        sorted_items = sorted(classifications, key=lambda item: item.page_number)
        sections: list[StudentRecordSection] = []
        current: StudentRecordSection | None = None

        for cls in sorted_items:
            if current is None:
                current = StudentRecordSection(
                    section_type=cls.category,
                    start_page=cls.page_number,
                    end_page=cls.page_number,
                    pages=[cls.page_number],
                    raw_text="",
                    elements=[],
                    tables=[],
                )
                continue

            is_same_section = cls.category == current.section_type or cls.is_continuation
            if is_same_section:
                current.end_page = cls.page_number
                current.pages.append(cls.page_number)
                continue

            sections.append(current)
            current = StudentRecordSection(
                section_type=cls.category,
                start_page=cls.page_number,
                end_page=cls.page_number,
                pages=[cls.page_number],
                raw_text="",
                elements=[],
                tables=[],
            )

        if current is not None:
            sections.append(current)
        return sections


def segment_sections(
    pages: list[dict[str, Any]],
    classifications: list[PageClassification],
    elements: list[dict[str, Any]],
    tables: list[dict[str, Any]]
) -> list[StudentRecordSection]:
    """
    Segments the document into logical sections based on page classifications.
    Handles sections that span across multiple pages.
    """
    sections: list[StudentRecordSection] = []
    
    if not pages or not classifications:
        return sections

    # Create a mapping of page number to elements/tables for efficient lookup
    page_to_elements = {}
    for element in elements:
        p_num = element.get("page_number")
        if p_num not in page_to_elements:
            page_to_elements[p_num] = []
        page_to_elements[p_num].append(element)
        
    page_to_tables = {}
    for table in tables:
        p_num = table.get("page_number")
        if p_num not in page_to_tables:
            page_to_tables[p_num] = []
        page_to_tables[p_num].append(table)

    current_section: dict[str, Any] | None = None
    
    for i, cls in enumerate(classifications):
        # Determine if this page starts a new section or continues the current one
        is_new_section = False
        if current_section is None:
            is_new_section = True
        elif cls.category != PageCategory.UNKNOWN and cls.category != current_section["section_type"]:
            # If the category is different and not a continuation marker
            if not cls.is_continuation:
                is_new_section = True
        
        if is_new_section:
            # Finalize previous section
            if current_section:
                sections.append(StudentRecordSection(**current_section))
            
            # Start new section
            current_section = {
                "section_type": cls.category if cls.category != PageCategory.UNKNOWN else PageCategory.UNKNOWN,
                "start_page": cls.page_number,
                "end_page": cls.page_number,
                "pages": [cls.page_number],
                "raw_text": _get_page_text(pages, cls.page_number),
                "elements": page_to_elements.get(cls.page_number, []),
                "tables": page_to_tables.get(cls.page_number, []),
            }
        else:
            # Continue current section
            if current_section:
                current_section["end_page"] = cls.page_number
                current_section["pages"].append(cls.page_number)
                current_section["raw_text"] += "\n" + _get_page_text(pages, cls.page_number)
                current_section["elements"].extend(page_to_elements.get(cls.page_number, []))
                current_section["tables"].extend(page_to_tables.get(cls.page_number, []))
                
                # Update section type if current was UNKNOWN and we found a match
                if current_section["section_type"] == PageCategory.UNKNOWN and cls.category != PageCategory.UNKNOWN:
                    current_section["section_type"] = cls.category

    # Finalize last section
    if current_section:
        sections.append(StudentRecordSection(**current_section))

    return sections


def _get_page_text(pages: list[dict[str, Any]], page_number: int) -> str:
    for page in pages:
        if page.get("page_number") == page_number:
            return page.get("text") or page.get("raw_text") or ""
    return ""
