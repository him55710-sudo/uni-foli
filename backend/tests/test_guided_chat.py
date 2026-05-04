from __future__ import annotations

import sys
from pathlib import Path


GUIDED_CHAT_SERVICE_PATH = Path("backend/services/api/src/unifoli_api/services/guided_chat_service.py")
GUIDED_CHAT_SCHEMA_PATH = Path("backend/services/api/src/unifoli_api/schemas/guided_chat.py")
API_SRC_PATH = Path("backend/services/api/src")


def test_guided_chat_start_prompt_keeps_proactive_questioning() -> None:
    source = GUIDED_CHAT_SERVICE_PATH.read_text(encoding="utf-8")
    assert "어떤 과목의 탐구보고서를 준비하고 계신가요?" in source
    assert "특별히 생각해둔 주제가 있나요?" in source
    assert "다음으로 무엇을 할까요?" in source


def test_guided_chat_state_summary_exposes_resume_payload() -> None:
    source = GUIDED_CHAT_SERVICE_PATH.read_text(encoding="utf-8")
    assert '"suggestions": [item.model_dump(mode="json") for item in suggestions]' in source
    assert '"recommended_page_ranges": [item.model_dump(mode="json") for item in page_ranges]' in source
    assert '"structure_options": [item.model_dump(mode="json") for item in structure_options]' in source


def test_guided_chat_schema_contains_phase_machine_contract() -> None:
    source = GUIDED_CHAT_SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"subject_input"' in source
    assert '"specific_topic_check"' in source
    assert '"topic_selection"' in source
    assert '"page_range_selection"' in source
    assert '"structure_selection"' in source
    assert '"drafting_next_step"' in source


def test_guided_chat_topic_generation_uses_guided_chat_concern() -> None:
    source = GUIDED_CHAT_SERVICE_PATH.read_text(encoding="utf-8")
    assert 'get_llm_client(profile="fast", concern="guided_chat")' in source
    assert 'get_llm_temperature(profile="fast", concern="guided_chat")' in source


def test_guided_chat_topic_generation_expands_to_300_candidates() -> None:
    source = GUIDED_CHAT_SERVICE_PATH.read_text(encoding="utf-8")
    assert "TOPIC_SUGGESTION_TARGET_COUNT = 300" in source
    assert "target_count=TOPIC_SUGGESTION_TARGET_COUNT" in source
    assert "추천 탐구 주제 {len(normalized)}개" in source


def test_topic_library_and_search_have_at_least_300_quality_candidates() -> None:
    sys.path.insert(0, str(API_SRC_PATH.resolve()))
    from unifoli_api.services.topic_library import TOPIC_LIBRARY
    from unifoli_api.services.topic_search_service import TopicSearchService

    labels = [topic["label"] for topic in TOPIC_LIBRARY]
    assert len(TOPIC_LIBRARY) >= 300
    assert len(set(labels)) == len(labels)
    assert any("윤리" in label or "의사결정" in label for label in labels)
    assert any("오차" in label or "한계" in label for label in labels)

    service = TopicSearchService(pool_path="__missing_topics_pool__.json")
    results = service.search("수학 데이터사이언스 탐구", limit=300)
    assert len(results) >= 300
    assert len({item["label"] for item in results}) == len(results)
