from __future__ import annotations

from fastapi.testclient import TestClient

from polio_api.core.config import Settings
from polio_api.core.llm import OllamaClient, get_llm_client
from polio_api.main import app
from polio_api.schemas.guided_chat import TopicSuggestion
from backend.tests.auth_helpers import auth_headers

FIXED_GREETING = "안녕하세요. 어떤 주제의 보고서를 써볼까요?"


class _FakeGuidedChatLLM:
    def __init__(self, suggestion_count: int = 3):
        self.suggestion_count = suggestion_count

    async def generate_json(self, prompt, response_model, system_instruction=None, temperature=0.2):  # noqa: ANN001
        suggestions = [
            TopicSuggestion(
                id=f"topic-{index + 1}",
                title=f"테스트 주제 {index + 1}",
                why_fit_student="확인된 맥락 범위 안에서 안전하게 진행 가능한 주제입니다.",
                link_to_record_flow="기록 흐름과 연결 가능한 범위에서 제안드립니다.",
                link_to_target_major_or_university=None,
                novelty_point="기존 흐름을 보수적으로 확장합니다.",
                caution_note=None,
            )
            for index in range(self.suggestion_count)
        ]
        return response_model(
            greeting=FIXED_GREETING,
            subject="수학",
            suggestions=suggestions,
            evidence_gap_note=None,
        )


class _FailingGuidedChatLLM:
    async def generate_json(self, prompt, response_model, system_instruction=None, temperature=0.2):  # noqa: ANN001
        raise RuntimeError("forced failure")


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "Guided Chat Test Project", "target_major": "수학"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_local_env_without_gemini_key_falls_back_to_ollama(monkeypatch) -> None:
    settings = Settings(
        app_env="local",
        llm_provider="gemini",
        gemini_api_key=None,
        ollama_model="gemma",
    )
    monkeypatch.setattr("polio_api.core.llm.get_settings", lambda: settings)

    client = get_llm_client()

    assert isinstance(client, OllamaClient)
    assert client.model == "gemma"


def test_guided_chat_start_uses_exact_fixed_greeting() -> None:
    headers = auth_headers("guided-chat-start-user")
    with TestClient(app) as client:
        project_id = _create_project(client, headers)
        response = client.post(
            "/api/v1/guided-chat/start",
            headers=headers,
            json={"project_id": project_id},
        )

    assert response.status_code == 200
    assert response.json()["greeting"] == FIXED_GREETING


def test_topic_suggestions_always_return_exactly_three_items(monkeypatch) -> None:
    monkeypatch.setattr("polio_api.services.guided_chat_service.get_llm_client", lambda: _FakeGuidedChatLLM(suggestion_count=2))

    headers = auth_headers("guided-chat-suggestions-user")
    with TestClient(app) as client:
        project_id = _create_project(client, headers)
        response = client.post(
            "/api/v1/guided-chat/topic-suggestions",
            headers=headers,
            json={"project_id": project_id, "subject": "수학"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["greeting"] == FIXED_GREETING
    assert len(payload["suggestions"]) == 3


def test_missing_diagnosis_data_returns_limited_context_note(monkeypatch) -> None:
    monkeypatch.setattr("polio_api.services.guided_chat_service.get_llm_client", lambda: _FailingGuidedChatLLM())

    headers = auth_headers("guided-chat-limited-context-user")
    with TestClient(app) as client:
        project_id = _create_project(client, headers)
        response = client.post(
            "/api/v1/guided-chat/topic-suggestions",
            headers=headers,
            json={"project_id": project_id, "subject": "수학"},
        )

    assert response.status_code == 200
    payload = response.json()
    note = payload.get("evidence_gap_note") or ""
    assert note
    assert ("제한" in note) or ("부족" in note)
    assert len(payload["suggestions"]) == 3


def test_topic_selection_returns_richer_starter_draft(monkeypatch) -> None:
    monkeypatch.setattr("polio_api.services.guided_chat_service.get_llm_client", lambda: _FakeGuidedChatLLM(suggestion_count=3))

    headers = auth_headers("guided-chat-selection-user")
    with TestClient(app) as client:
        project_id = _create_project(client, headers)
        suggestions_response = client.post(
            "/api/v1/guided-chat/topic-suggestions",
            headers=headers,
            json={"project_id": project_id, "subject": "수학"},
        )
        assert suggestions_response.status_code == 200
        suggestions_payload = suggestions_response.json()
        selected_id = suggestions_payload["suggestions"][0]["id"]

        selection_response = client.post(
            "/api/v1/guided-chat/topic-selection",
            headers=headers,
            json={
                "project_id": project_id,
                "selected_topic_id": selected_id,
                "subject": "수학",
                "suggestions": suggestions_payload["suggestions"],
            },
        )

    assert selection_response.status_code == 200
    payload = selection_response.json()
    starter = payload["starter_draft_markdown"]
    assert "## 증거-안전 작성 경계" in starter
    assert "## Evidence Memo" in starter
    assert "## 도입 문단(초안)" in starter
    assert isinstance(payload.get("state_summary"), dict)
