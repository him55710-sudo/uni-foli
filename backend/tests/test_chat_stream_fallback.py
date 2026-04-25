from __future__ import annotations

from fastapi.testclient import TestClient

from unifoli_api.core.llm import LLMRequestError
from unifoli_api.main import app
from backend.tests.auth_helpers import auth_headers


class _FailingStreamLLM:
    async def stream_chat(self, prompt, system_instruction=None, temperature=0.5):  # noqa: ANN001
        raise LLMRequestError(
            "fallback required",
            limited_reason="ollama_timeout",
            provider="ollama",
            profile="standard",
        )
        if False:  # pragma: no cover - keeps this as an async generator contract.
            yield ""


class _ContextEchoStreamLLM:
    async def stream_chat(self, prompt, system_instruction=None, temperature=0.5):  # noqa: ANN001
        yield "[문서 근거 사용 원칙]\n- 문서 근거 범위를 벗어나는 사실은 단정하지 않습니다.\n"
        yield "[세션 목표 모드]\n- 모드: planning\n- DRAFT_PATCH JSON 예시: {}"


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "Fallback Project", "target_major": "Computer Science"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_drafts_chat_stream_fallback_returns_meta_and_done(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_get_llm_client(*, profile: str = "standard", concern: str = "default") -> _FailingStreamLLM:
        calls.append({"profile": profile, "concern": concern})
        return _FailingStreamLLM()

    monkeypatch.setattr("unifoli_api.api.routes.drafts.get_llm_client", fake_get_llm_client)

    headers = auth_headers("drafts-fallback-user")
    with TestClient(app) as client:
        project_id = _create_project(client, headers)

        response = client.post(
            "/api/v1/drafts/chat/stream",
            headers=headers,
            json={"project_id": project_id, "message": "draft fallback prompt", "reference_materials": []},
        )

    assert response.status_code == 200
    body = response.text
    assert '"limited_mode": true' in body
    assert '"limited_reason": "ollama_timeout"' in body
    assert '"status": "DONE"' in body
    assert calls == [{"profile": "standard", "concern": "guided_chat"}]


def test_workshop_chat_stream_suppresses_context_echo(monkeypatch) -> None:
    def fake_get_llm_client(*, profile: str = "standard", concern: str = "default") -> _ContextEchoStreamLLM:
        return _ContextEchoStreamLLM()

    monkeypatch.setattr("unifoli_api.api.routes.workshops.get_llm_client", fake_get_llm_client)

    headers = auth_headers("workshop-context-echo-user")
    with TestClient(app) as client:
        project_id = _create_project(client, headers)
        workshop = client.post(
            "/api/v1/workshops",
            headers=headers,
            json={"project_id": project_id, "quality_level": "mid"},
        )
        assert workshop.status_code == 201
        workshop_id = workshop.json()["session"]["id"]

        response = client.post(
            f"/api/v1/workshops/{workshop_id}/chat/stream",
            headers=headers,
            json={"message": "what should I do next?"},
        )

    assert response.status_code == 200
    body = response.text
    assert '"limited_mode": true' in body
    assert '"limited_reason": "llm_context_echo"' in body
    assert "문서 근거 사용 원칙" not in body
    assert "DRAFT_PATCH JSON 예시" not in body
    assert '"status": "DONE"' in body


def test_workshop_chat_stream_fallback_returns_meta_and_done(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_get_llm_client(*, profile: str = "standard", concern: str = "default") -> _FailingStreamLLM:
        calls.append({"profile": profile, "concern": concern})
        return _FailingStreamLLM()

    monkeypatch.setattr("unifoli_api.api.routes.workshops.get_llm_client", fake_get_llm_client)

    headers = auth_headers("workshop-fallback-user")
    with TestClient(app) as client:
        project_id = _create_project(client, headers)
        workshop = client.post(
            "/api/v1/workshops",
            headers=headers,
            json={"project_id": project_id, "quality_level": "mid"},
        )
        assert workshop.status_code == 201
        workshop_id = workshop.json()["session"]["id"]

        response = client.post(
            f"/api/v1/workshops/{workshop_id}/chat/stream",
            headers=headers,
            json={"message": "workshop fallback prompt"},
        )

    assert response.status_code == 200
    body = response.text
    assert '"limited_mode": true' in body
    assert '"limited_reason": "ollama_timeout"' in body
    assert '"status": "DONE"' in body
    assert calls == [{"profile": "standard", "concern": "guided_chat"}]
