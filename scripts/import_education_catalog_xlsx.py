from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"main": MAIN_NS}

UNIVERSITY_HEADERS = {
    "\ub300\ud559",
    "\ub300\ud559\uad50",
    "\ub300\ud559\uba85",
    "\ud559\uad50",
    "\ud559\uad50\uba85",
    "\uc9c0\uc6d0\ub300\ud559",
    "university",
    "school",
}

MAJOR_HEADERS = {
    "학과",
    "학과명",
    "전공",
    "전공명",
    "학부",
    "학부학과",
    "학부과전공",
    "학부과전공명",
    "모집단위",
    "모집단위명",
    "major",
    "department",
}

FILTER_HEADERS = {
    "대학구분": "university_category",
    "학교구분": "school_type",
    "학과상태": "major_status",
    "학위과정": "degree_process",
}


def normalize_header(value: str) -> str:
    return re.sub(r"[\s\-_./()[\]{}·]+", "", value).lower()


def load_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        text = "".join(node.text or "" for node in item.iterfind(f".//{{{MAIN_NS}}}t"))
        strings.append(text)
    return strings


def column_index(cell_reference: str) -> int:
    match = re.match(r"[A-Z]+", cell_reference)
    if match is None:
        raise ValueError(f"Could not parse cell reference: {cell_reference}")

    value = 0
    for char in match.group(0):
        value = value * 26 + (ord(char) - 64)
    return value - 1


def read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find(f"{{{MAIN_NS}}}v")

    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iterfind(f".//{{{MAIN_NS}}}t")).strip()

    if value_node is None or value_node.text is None:
        return ""

    value = value_node.text.strip()
    if cell_type == "s":
        return shared_strings[int(value)].strip()
    return value


def get_sheet_paths(workbook: zipfile.ZipFile) -> dict[str, str]:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))

    relationship_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
    }

    sheet_paths: dict[str, str] = {}
    for sheet in workbook_root.findall("main:sheets/main:sheet", NS):
        name = sheet.attrib["name"]
        relationship_id = sheet.attrib[f"{{{DOC_REL_NS}}}id"]
        target = relationship_map[relationship_id].lstrip("/")
        sheet_paths[name] = target if target.startswith("xl/") else f"xl/{target}"
    return sheet_paths


def load_sheet_rows(
    workbook: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[list[str]]:
    root = ET.fromstring(workbook.read(sheet_path))
    rows: list[list[str]] = []

    for row in root.findall(".//main:sheetData/main:row", NS):
        cells: dict[int, str] = {}
        for cell in row.findall("main:c", NS):
            reference = cell.attrib.get("r")
            if reference is None:
                continue
            cells[column_index(reference)] = read_cell_value(cell, shared_strings)

        if not cells:
            continue

        max_index = max(cells.keys())
        rows.append([cells.get(index, "").strip() for index in range(max_index + 1)])

    return rows


def detect_columns(rows: list[list[str]]) -> tuple[int, int, int, dict[str, int]]:
    for row_index, row in enumerate(rows[:10]):
        university_index: int | None = None
        major_index: int | None = None
        filter_indices: dict[str, int] = {}

        for index, value in enumerate(row):
            normalized = normalize_header(value)
            raw_value = value.strip()
            if not normalized and not raw_value:
                continue

            if university_index is None and (
                normalized in UNIVERSITY_HEADERS
                or normalized.endswith("대학명")
                or normalized.endswith("학교명")
            ):
                university_index = index

            if major_index is None and (
                normalized in MAJOR_HEADERS
                or normalized.endswith("학과명")
                or normalized.endswith("전공명")
                or normalized.endswith("모집단위명")
            ):
                major_index = index

            for header_name, key in FILTER_HEADERS.items():
                if raw_value == header_name or normalized == normalize_header(header_name):
                    filter_indices[key] = index

        if university_index is not None and major_index is not None:
            return row_index, university_index, major_index, filter_indices

    raise RuntimeError("Could not detect university and major columns in the workbook.")


def build_catalog(
    rows: list[list[str]],
    university_index: int,
    major_index: int,
    filter_indices: dict[str, int],
    header_index: int,
) -> dict[str, object]:
    majors_by_university: dict[str, set[str]] = defaultdict(set)
    total_rows = 0
    skipped_by_filter = 0
    
    # Filter config
    ALLOWED_CATEGORIES = {"대학", "전문대학"}
    ALLOWED_PROCESSES = {"학사", "전문학사", "학석사통합"}

    for row in rows[header_index + 1 :]:
        total_rows += 1
        university = row[university_index].strip() if university_index < len(row) else ""
        major = row[major_index].strip() if major_index < len(row) else ""

        if not university:
            continue

        # Content filtering
        if filter_indices:
            status = row[filter_indices["major_status"]].strip() if "major_status" in filter_indices and filter_indices["major_status"] < len(row) else ""
            if "폐지" in status:
                skipped_by_filter += 1
                continue
            
            degree = row[filter_indices["degree_process"]].strip() if "degree_process" in filter_indices and filter_indices["degree_process"] < len(row) else ""
            if degree and degree not in ALLOWED_PROCESSES:
                skipped_by_filter += 1
                continue
                
            category = row[filter_indices["university_category"]].strip() if "university_category" in filter_indices and filter_indices["university_category"] < len(row) else ""
            if category and category not in ALLOWED_CATEGORIES:
                skipped_by_filter += 1
                continue

        if major:
            majors_by_university[university].add(major)
        else:
            majors_by_university.setdefault(university, set())

    universities = [
        {
            "name": university,
            "majors": sorted(majors),
        }
        for university, majors in sorted(majors_by_university.items())
        if majors # Only include universities with departments after filtering
    ]

    all_majors = sorted({major for majors in majors_by_university.values() for major in majors})
    
    return {
        "universities": universities,
        "all_majors": all_majors,
        "metadata": {
            "university_count": len(universities),
            "major_count": len(all_majors),
            "filters": {
                "exclude_obsolete": True,
                "degree_processes": list(ALLOWED_PROCESSES),
                "university_categories": list(ALLOWED_CATEGORIES),
            },
            "stats": {
                "total_rows_processed": total_rows,
                "rows_skipped_by_filter": skipped_by_filter,
            }
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a university/major XLSX sheet into the frontend catalog JSON."
    )
    parser.add_argument("source", help="Path to the XLSX file")
    parser.add_argument("--sheet-name", help="Optional Excel sheet name")
    parser.add_argument(
        "--output",
        default="frontend/src/data/education-catalog.generated.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    with zipfile.ZipFile(source) as workbook:
        shared_strings = load_shared_strings(workbook)
        sheet_paths = get_sheet_paths(workbook)

        if args.sheet_name:
            if args.sheet_name not in sheet_paths:
                available = ", ".join(sheet_paths.keys())
                raise RuntimeError(
                    f"Sheet '{args.sheet_name}' was not found. Available sheets: {available}"
                )
            sheet_name = args.sheet_name
        else:
            sheet_name = next(iter(sheet_paths))

        rows = load_sheet_rows(workbook, sheet_paths[sheet_name], shared_strings)

    header_index, university_index, major_index, filter_indices = detect_columns(rows)
    catalog = build_catalog(rows, university_index, major_index, filter_indices, header_index)
    payload = {
        "generated_at": datetime.fromtimestamp(source.stat().st_mtime).isoformat(),
        "source_file": str(source),
        **catalog,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Imported {len(payload['universities'])} universities into {output}")


if __name__ == "__main__":
    main()
