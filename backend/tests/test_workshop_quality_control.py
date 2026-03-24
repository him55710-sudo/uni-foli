from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from polio_api.main import app
from polio_api.services.quality_control import (
    QUALITY_CONTROL_SCHEMA_VERSION,
    build_quality_control_metadata,
    resolve_advanced_features,
)
from polio_api.services.safety_guard import SafetyFlag, run_safety_check
from polio_api.services.workshop_render_service import _build_safe_artifact


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "title": f"Workshop QC {uuid4()}",
            "description": "Workshop quality-control test project.",
            "target_university": "Quality University",
            "target_major": "Education",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _post_long_message(client: TestClient, workshop_id: str, index: int) -> None:
    message = (
        f"{index}번째 워크샵 입력입니다. 학생이 실제로 해본 활동과 교과 개념 연결을 길게 설명해서 "
        f"현재 수준에서 가능한 탐구 맥락을 충분히 확보합니다. "
        f"수행 가능성, 관찰 포인트, 기록 문장 후보를 모두 정리하려는 목적입니다."
    )
    response = client.post(
        f"/api/v1/workshops/{workshop_id}/messages",
        json={"message": message},
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


def test_workshop_quality_level_changes_choices_and_requirements() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client)

        create_response = client.post(
            "/api/v1/workshops",
            json={"project_id": project_id, "quality_level": "low"},
        )
        assert create_response.status_code == 201
        create_payload = create_response.json()
        assert create_payload["session"]["quality_level"] == "low"
        assert create_payload["quality_level_info"]["label"] == "안전형"
        assert create_payload["render_requirements"]["minimum_reference_count"] == 0
        assert any(choice["label"] == "핵심 개념부터 정리" for choice in create_payload["starter_choices"])

        workshop_id = create_payload["session"]["id"]
        update_response = client.patch(
            f"/api/v1/workshops/{workshop_id}/quality-level",
            json={"quality_level": "high"},
        )
        assert update_response.status_code == 200
        update_payload = update_response.json()
        assert update_payload["session"]["quality_level"] == "high"
        assert update_payload["quality_level_info"]["label"] == "심화형"
        assert update_payload["render_requirements"]["minimum_reference_count"] == 1
        assert any(choice["label"] == "심화 질문 좁히기" for choice in update_payload["starter_choices"])


def test_high_quality_render_requires_reference_before_rendering() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client)
        workshop_response = client.post(
            "/api/v1/workshops",
            json={"project_id": project_id, "quality_level": "high"},
        )
        assert workshop_response.status_code == 201
        workshop_id = workshop_response.json()["session"]["id"]

        for index in range(5):
            _post_long_message(client, workshop_id, index)

        render_response = client.post(f"/api/v1/workshops/{workshop_id}/render", json={"force": False})
        assert render_response.status_code == 422
        detail = render_response.json()["detail"]
        assert detail["minimum_reference_count"] == 1
        assert "참고자료" in " ".join(detail["missing"])


def test_workshop_render_persists_quality_control_metadata() -> None:
    with TestClient(app) as client:
        project_id = _create_project(client)
        workshop_response = client.post(
            "/api/v1/workshops",
            json={"project_id": project_id, "quality_level": "mid"},
        )
        assert workshop_response.status_code == 201
        workshop_id = workshop_response.json()["session"]["id"]

        for index in range(4):
            _post_long_message(client, workshop_id, index)

        render_response = client.post(f"/api/v1/workshops/{workshop_id}/render", json={"force": False})
        assert render_response.status_code == 200
        artifact_id = render_response.json()["artifact_id"]

        token_response = client.post(f"/api/v1/workshops/{workshop_id}/stream-token")
        assert token_response.status_code == 200
        stream_token = token_response.json()["stream_token"]

        stream_response = client.get(
            f"/api/v1/workshops/{workshop_id}/events",
            params={"stream_token": stream_token, "artifact_id": artifact_id},
        )
        assert stream_response.status_code == 200
        assert "event: artifact.ready" in stream_response.text

        artifact_payload = _extract_event_payload(stream_response.text, "artifact.ready")
        assert artifact_payload["report_markdown"].startswith("## 탐구 보고서")
        assert artifact_payload["quality_control"]["requested_level"] == "mid"
        assert artifact_payload["quality_control"]["applied_level"] in {"low", "mid"}

        workshop_state = client.get(f"/api/v1/workshops/{workshop_id}")
        assert workshop_state.status_code == 200
        latest_artifact = workshop_state.json()["latest_artifact"]
        assert latest_artifact["quality_control_meta"]["requested_level"] == "mid"
        assert latest_artifact["quality_control_meta"]["checks"]


def test_safety_guard_detects_ungrounded_high_risk_output() -> None:
    result = run_safety_check(
        report_markdown=(
            "양자역학 개념을 활용해 직접 실험을 진행했고, 200명 설문 결과 83%가 긍정적이었다고 정리했다."
        ),
        teacher_summary="학생이 대학 연구실 수준의 실험과 대규모 설문을 수행한 것으로 보이게 작성했다.",
        requested_level="high",
        turn_count=1,
        reference_count=0,
        turns_text="학생은 관심 주제를 정하고 싶다고만 말했다.",
        references_text="",
    )

    assert result.downgraded is True
    assert result.recommended_level == "low"
    assert SafetyFlag.FABRICATION_RISK.value in result.flags
    assert SafetyFlag.FEASIBILITY_RISK.value in result.flags
    assert result.checks["fabrication"].unsupported_count >= 2


def test_quality_control_schema_tracks_guardrail_and_advanced_metadata() -> None:
    metadata = build_quality_control_metadata(
        requested_level="high",
        applied_level="mid",
        turn_count=4,
        reference_count=1,
        safety_score=72,
        downgraded=True,
        summary="안전성 기준에 따라 수준을 조정했습니다.",
        advanced_features_requested=True,
        advanced_features_applied=False,
        advanced_features_reason="안전 재작성 과정에서 고급 확장을 제거했습니다.",
    )

    assert metadata["schema_version"] == QUALITY_CONTROL_SCHEMA_VERSION
    assert metadata["requested_level"] == "high"
    assert metadata["applied_level"] == "mid"
    assert metadata["safety_posture"]
    assert metadata["authenticity_policy"]
    assert metadata["hallucination_guardrail"]
    assert metadata["advanced_features_requested"] is True
    assert metadata["advanced_features_applied"] is False


def test_same_context_renders_different_depth_by_quality_level() -> None:
    turns = [
        SimpleNamespace(
            id="turn-1",
            turn_type="message",
            query="학교 수업 시간에 미세먼지 주제를 조사하며 지역별 수치를 비교해 봤다.",
            action_payload=None,
        )
    ]
    references = [
        SimpleNamespace(
            id="ref-1",
            source_type="manual_note",
            text_content="환경부 공개 자료에서 지역별 미세먼지 농도 비교 표를 확인했다.",
        )
    ]

    low = _build_safe_artifact(
        turns=turns,
        references=references,
        target_major="환경공학",
        target_university="Quality University",
        quality_level="low",
    )
    mid = _build_safe_artifact(
        turns=turns,
        references=references,
        target_major="환경공학",
        target_university="Quality University",
        quality_level="mid",
    )
    high = _build_safe_artifact(
        turns=turns,
        references=references,
        target_major="환경공학",
        target_university="Quality University",
        quality_level="high",
    )

    assert "이번 학기 안에 가능한 수행" in low["report_markdown"]
    assert "간단한 해석과 다음 단계" in mid["report_markdown"]
    assert "실제 맥락 기반 심화 질문" in high["report_markdown"]
    assert low["report_markdown"] != mid["report_markdown"] != high["report_markdown"]


def test_advanced_features_require_high_level_and_reference_support() -> None:
    enabled, reason = resolve_advanced_features(requested=True, quality_level="mid", reference_count=3)
    assert enabled is False
    assert "표준형" in reason

    enabled, reason = resolve_advanced_features(requested=True, quality_level="high", reference_count=0)
    assert enabled is False
    assert "참고자료 1개 이상" in reason

    enabled, reason = resolve_advanced_features(requested=True, quality_level="high", reference_count=2)
    assert enabled is True
    assert "고급 확장" in reason
