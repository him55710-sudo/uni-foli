from __future__ import annotations

import json
from pathlib import Path

import pytest

from polio_ingest.neis_pipeline import map_neis_semantics, normalize_odl_payload, stitch_neis_context


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "neis_odl"


def _fixture_cases() -> list[Path]:
    return sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir())


@pytest.mark.parametrize("case_dir", _fixture_cases(), ids=lambda path: path.name)
def test_neis_golden_cases(case_dir: Path) -> None:
    raw_payload = json.loads((case_dir / "raw.json").read_text(encoding="utf-8"))
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))

    normalized = normalize_odl_payload(raw_payload, source_file="fixture.pdf")
    stitched = stitch_neis_context(normalized)
    neis_document = map_neis_semantics(stitched)

    assert len(stitched["table_chains"]) == expected["expected_chain_count"]
    assert stitched["table_chains"][0]["page_span"] == expected["expected_page_span"]

    section = neis_document["sections"][0]
    assert section["section_type"] == expected["expected_section_type"]
    assert len(section["records"]) == expected["expected_record_count"]

    record = section["records"][0]
    assert record["school_year"] == expected["expected_school_year"]
    assert record["semester"] == expected["expected_semester"]
    assert record["subject_name"] == expected["expected_subject_name"]
    assert record["page_span"] == expected["expected_page_span"]
    for snippet in expected["expected_special_notes_contains"]:
        assert snippet in record["special_notes_text"]

    assert section["records"][0]["needs_review"] is False
    assert neis_document["semantic_mapping_confidence"] >= 0.65
    assert neis_document["parse_trace"]["record_count"] == expected["expected_record_count"]
    assert neis_document["evidence_references"][0]["page_span"] == expected["expected_page_span"]
