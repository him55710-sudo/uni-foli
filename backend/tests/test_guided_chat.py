from __future__ import annotations

from pathlib import Path


GUIDED_CHAT_SERVICE_PATH = Path("backend/services/api/src/unifoli_api/services/guided_chat_service.py")


def test_guided_chat_greeting_and_limited_note_are_korean() -> None:
    source = GUIDED_CHAT_SERVICE_PATH.read_text(encoding="utf-8")
    assert 'GUIDED_CHAT_GREETING = "안녕하세요. 어떤 주제로 보고서를 써볼까요?"' in source
    assert 'LIMITED_CONTEXT_NOTE = "현재 확인 가능한 학생 맥락이 제한되어 보수적으로 제안합니다."' in source


def test_topic_suggestion_logic_keeps_three_candidates() -> None:
    source = GUIDED_CHAT_SERVICE_PATH.read_text(encoding="utf-8")
    assert "if len(normalized) < 3:" in source
    assert "normalized.extend(_build_fallback_topics" in source
    assert "return normalized[:3]" in source


def test_starter_draft_template_is_korean() -> None:
    source = GUIDED_CHAT_SERVICE_PATH.read_text(encoding="utf-8")
    assert "## 증거-안전 작성 경계" in source
    assert "## 근거 메모" in source
    assert "## 도입 문단(초안)" in source
    assert "## Evidence Memo" not in source
