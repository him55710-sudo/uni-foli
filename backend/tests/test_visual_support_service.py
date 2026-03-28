from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from polio_api.main import app
from polio_api.services.visual_support_service import build_visual_support_plan, rank_external_image_candidates
from backend.tests.auth_helpers import auth_headers


def _create_project(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "title": f"Visual Support {uuid4()}",
            "description": "Visual support planner test project.",
            "target_university": "Visual University",
            "target_major": "Environmental Engineering",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def _post_message(client: TestClient, workshop_id: str, text: str, headers: dict[str, str]) -> None:
    response = client.post(
        f"/api/v1/workshops/{workshop_id}/messages",
        json={"message": text},
        headers=headers,
    )
    assert response.status_code == 200


def _extract_event_payload(raw_stream: str, event_name: str) -> dict[str, object]:
    for block in raw_stream.split("\n\n"):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines or lines[0] != f"event: {event_name}":
            continue
        data_line = next((line for line in lines if line.startswith("data: ")), None)
        if data_line is None:
            continue
        return json.loads(data_line.removeprefix("data: "))
    raise AssertionError(f"Event not found: {event_name}")


def test_visual_planner_returns_no_visual_when_context_is_weak() -> None:
    plan = build_visual_support_plan(
        report_markdown="## Reflection\n학생은 추가 실험 설계를 고민하고 있다.",
        evidence_map={},
        student_submission_note="",
        turns=[],
        references=[],
        advanced_mode=True,
        target_major="Biology",
    )

    assert plan["visual_specs"] == []
    assert plan["math_expressions"] == []


def test_visual_planner_prefers_table_for_comparison_sections() -> None:
    plan = build_visual_support_plan(
        report_markdown=(
            "## Comparison of methods\n"
            "- Soil sensor: captures repeated moisture changes quickly.\n"
            "- Manual observation: preserves smell, texture, and human context.\n"
            "- Hybrid logging: combines both without claiming extra precision.\n"
        ),
        evidence_map={"claim-1": {"source": "reference:ref-1"}},
        student_submission_note="",
        turns=[SimpleNamespace(id="turn-1", query="The student compared two observation methods.")],
        references=[SimpleNamespace(id="ref-1", text_content="Official lab note comparing soil sensor and manual observation.")],
        advanced_mode=True,
        target_major="Environmental Engineering",
    )

    assert plan["visual_specs"]
    assert plan["visual_specs"][0]["type"] == "table"
    assert plan["visual_specs"][0]["provenance"]["evidence_refs"] == ["reference:ref-1"]


def test_visual_planner_builds_chart_only_for_grounded_numbers() -> None:
    plan = build_visual_support_plan(
        report_markdown=(
            "## Greenhouse data trend\n"
            "- Moisture: 35%\n"
            "- Light: 62%\n"
            "- pH: 6.1\n"
        ),
        evidence_map={"claim-1": {"source": "reference:ref-1"}},
        student_submission_note="Check the official greenhouse log before export.",
        turns=[SimpleNamespace(id="turn-1", query="The student recorded greenhouse observations.")],
        references=[
            SimpleNamespace(
                id="ref-1",
                text_content="Official greenhouse log: Moisture 35%, Light 62%, pH 6.1 during the lettuce observation.",
            )
        ],
        advanced_mode=True,
        target_major="Environmental Engineering",
    )

    assert plan["visual_specs"]
    chart = plan["visual_specs"][0]
    assert chart["type"] == "chart"
    assert [item["value"] for item in chart["chart_spec"]["data"]] == [35.0, 62.0, 6.1]


def test_visual_planner_rejects_ungrounded_chart_numbers() -> None:
    plan = build_visual_support_plan(
        report_markdown=(
            "## Greenhouse data trend\n"
            "- Moisture: 88%\n"
            "- Light: 91%\n"
        ),
        evidence_map={},
        student_submission_note="",
        turns=[SimpleNamespace(id="turn-1", query="The student only described the greenhouse setup, not exact numbers.")],
        references=[SimpleNamespace(id="ref-1", text_content="Official note: the setup method was discussed without final numeric values.")],
        advanced_mode=True,
        target_major="Environmental Engineering",
    )

    assert not any(spec["type"] == "chart" for spec in plan["visual_specs"])


def test_external_image_ranking_rejects_low_relevance_candidates() -> None:
    ranked = rank_external_image_candidates(
        section_title="Hydroponic nutrient flow",
        section_text="This paragraph explains the nutrient circulation process for a lettuce hydroponic setup.",
        candidates=[
            {
                "image_url": "https://example.com/campus.jpg",
                "source_url": "https://example.com/campus",
                "source_title": "Happy students on campus lawn",
                "caption": "Campus brochure hero shot",
                "trust_rank": 400,
                "source_type": "OFFICIAL_SOURCE",
            }
        ],
        target_major="Environmental Engineering",
    )

    assert ranked == []


def test_workshop_render_persists_visual_specs_and_replays_them(monkeypatch) -> None:
    def fake_safe_artifact(**_: object) -> dict[str, object]:
        return {
            "report_markdown": (
                "## Greenhouse data trend\n"
                "- Moisture: 35%\n"
                "- Light: 62%\n"
                "- pH: 6.1\n"
            ),
            "teacher_record_summary_500": "Teacher summary",
            "student_submission_note": "Verify the official greenhouse log before final export.",
            "evidence_map": {"claim-1": {"source": "reference:ref-1"}},
            "visual_specs": [
                {
                    "type": "chart",
                    "chart_spec": {
                        "title": "Ungrounded draft chart",
                        "type": "bar",
                        "data": [{"name": "Unsupported", "value": 99}],
                    },
                }
            ],
            "math_expressions": [],
        }

    monkeypatch.setattr("polio_api.services.workshop_render_service._build_safe_artifact", fake_safe_artifact)

    with TestClient(app) as client:
        headers = auth_headers(f"visual-support-{uuid4().hex}")
        project_id = _create_project(client, headers)

        workshop_response = client.post(
            "/api/v1/workshops",
            json={"project_id": project_id, "quality_level": "high"},
            headers=headers,
        )
        assert workshop_response.status_code == 201
        workshop_id = workshop_response.json()["session"]["id"]

        for index in range(5):
            _post_message(
                client,
                workshop_id,
                (
                    f"Turn {index}: the student observed the greenhouse setup and documented nutrient flow, "
                    "measurement discipline, and safety limits."
                ),
                headers,
            )

        pin_response = client.post(
            f"/api/v1/workshops/{workshop_id}/references/pin",
            json={
                "text_content": "Official greenhouse log: Moisture 35%, Light 62%, pH 6.1 during the lettuce observation.",
                "source_type": "official_note",
            },
            headers=headers,
        )
        assert pin_response.status_code == 200

        render_response = client.post(
            f"/api/v1/workshops/{workshop_id}/render",
            json={"force": False, "advanced_mode": True},
            headers=headers,
        )
        assert render_response.status_code == 200
        artifact_id = render_response.json()["artifact_id"]

        token_response = client.post(f"/api/v1/workshops/{workshop_id}/stream-token", headers=headers)
        assert token_response.status_code == 200
        stream_response = client.get(
            f"/api/v1/workshops/{workshop_id}/events",
            params={
                "stream_token": token_response.json()["stream_token"],
                "artifact_id": artifact_id,
                "advanced_mode": True,
            },
        )
        assert stream_response.status_code == 200
        payload = _extract_event_payload(stream_response.text, "artifact.ready")
        assert payload["visual_specs"]
        assert payload["visual_specs"][0]["type"] == "chart"
        assert payload["visual_specs"][0]["chart_spec"]["data"][0]["value"] == 35.0

        workshop_state = client.get(f"/api/v1/workshops/{workshop_id}", headers=headers)
        assert workshop_state.status_code == 200
        latest_artifact = workshop_state.json()["latest_artifact"]
        assert latest_artifact["visual_specs"]
        assert latest_artifact["visual_specs"][0]["chart_spec"]["data"][0]["value"] == 35.0

        replay_token_response = client.post(f"/api/v1/workshops/{workshop_id}/stream-token", headers=headers)
        assert replay_token_response.status_code == 200
        replay_response = client.get(
            f"/api/v1/workshops/{workshop_id}/events",
            params={
                "stream_token": replay_token_response.json()["stream_token"],
                "artifact_id": artifact_id,
                "advanced_mode": True,
            },
        )
        assert replay_response.status_code == 200
        replay_payload = _extract_event_payload(replay_response.text, "artifact.ready")
        assert replay_payload["visual_specs"] == latest_artifact["visual_specs"]
