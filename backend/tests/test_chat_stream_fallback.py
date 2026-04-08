from __future__ import annotations

from fastapi.testclient import TestClient

from polio_api.core.llm import LLMRequestError
from polio_api.main import app
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


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "Fallback Project", "target_major": "Computer Science"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_drafts_chat_stream_fallback_returns_meta_and_done(monkeypatch) -> None:
    monkeypatch.setattr("polio_api.api.routes.drafts.get_llm_client", lambda profile="standard": _FailingStreamLLM())

    headers = auth_headers("drafts-fallback-user")
    with TestClient(app) as client:
        project_id = _create_project(client, headers)

        response = client.post(
            "/api/v1/drafts/chat/stream",
            headers=headers,
            json={"project_id": project_id, "message": "근거를 정리해줘", "reference_materials": []},
        )

    assert response.status_code == 200
    body = response.text
    assert '"limited_mode": true' in body
    assert '"limited_reason": "ollama_timeout"' in body
    assert '"status": "DONE"' in body


def test_workshop_chat_stream_fallback_returns_meta_and_done(monkeypatch) -> None:
    monkeypatch.setattr("polio_api.api.routes.workshops.get_llm_client", lambda profile="standard": _FailingStreamLLM())

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
            json={"message": "개요를 보강해줘"},
        )

    assert response.status_code == 200
    body = response.text
    assert '"limited_mode": true' in body
    assert '"limited_reason": "ollama_timeout"' in body
    assert '"status": "DONE"' in body
