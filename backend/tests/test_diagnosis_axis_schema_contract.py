from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from unifoli_api.api.routes import diagnosis as diagnosis_route
from unifoli_api.services.diagnosis_axis_schema import POSITIVE_AXIS_KEYS
from unifoli_api.services.diagnosis_service import DiagnosisResult, build_grounded_diagnosis_result, evaluate_student_record


def _assert_default_action_references_existing_payload_ids(result: DiagnosisResult) -> None:
    default_action = result.recommended_default_action
    assert default_action is not None

    direction = next((item for item in result.recommended_directions if item.id == default_action.direction_id), None)
    assert direction is not None
    assert any(item.id == default_action.topic_id for item in direction.topic_candidates)
    assert any(item.page_count == default_action.page_count for item in direction.page_count_options)
    assert any(item.format == default_action.export_format for item in direction.format_recommendations)
    assert any(
        item.id == default_action.template_id and default_action.export_format in item.supported_formats
        for item in direction.template_candidates
    )


def test_build_grounded_diagnosis_result_returns_canonical_gap_axes_without_validation_error() -> None:
    result = build_grounded_diagnosis_result(
        project_title="Axis contract check",
        target_major="Computer Science",
        target_university="Example University",
        career_direction="AI engineering",
        document_count=1,
        full_text=(
            "Compared two sensor calibration methods, measured error rates over three iterations, "
            "and reflected on method limits and next-step evidence collection."
        ),
    )

    assert len(result.gap_axes) == len(POSITIVE_AXIS_KEYS)
    assert {axis.key for axis in result.gap_axes} == set(POSITIVE_AXIS_KEYS)
    _assert_default_action_references_existing_payload_ids(result)


def test_evaluate_student_record_success_path_returns_guided_contract(monkeypatch) -> None:
    class _SuccessfulDiagnosisLLM:
        async def generate_json(self, **kwargs):  # noqa: ANN003
            response_model = kwargs["response_model"]
            grounded = build_grounded_diagnosis_result(
                project_title="Success contract check",
                target_major="Computer Science",
                target_university="Example University",
                career_direction="AI engineering",
                document_count=1,
                full_text=kwargs.get("prompt", ""),
            )
            return response_model.model_validate(grounded.model_dump())

    monkeypatch.setattr("unifoli_api.services.diagnosis_service.get_llm_client", lambda: _SuccessfulDiagnosisLLM())
    monkeypatch.setattr("unifoli_api.services.diagnosis_service.fetch_cached_response", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("unifoli_api.services.diagnosis_service.store_cached_response", lambda *_args, **_kwargs: None)

    result = asyncio.run(
        evaluate_student_record(
            user_major="Computer Science",
            masked_text=(
                "Built a robotics notebook and measured drift before and after calibration. "
                "Compared outcomes and documented method limits."
            ),
            target_university="Example University",
            target_major="Computer Science",
            career_direction="AI engineering",
            project_title="Success contract check",
            scope_key=f"axis-success:{uuid4()}",
            evidence_keys=["doc:axis-success"],
        )
    )

    assert result.headline
    assert len(result.gap_axes) == len(POSITIVE_AXIS_KEYS)
    assert {axis.key for axis in result.gap_axes} == set(POSITIVE_AXIS_KEYS)
    _assert_default_action_references_existing_payload_ids(result)


def test_evaluate_student_record_fallback_path_returns_guided_contract(monkeypatch) -> None:
    class _FailingDiagnosisLLM:
        async def generate_json(self, **kwargs):  # noqa: ANN003
            del kwargs
            raise RuntimeError("forced diagnosis llm failure")

    monkeypatch.setattr("unifoli_api.services.diagnosis_service.get_llm_client", lambda: _FailingDiagnosisLLM())
    monkeypatch.setattr("unifoli_api.services.diagnosis_service.fetch_cached_response", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("unifoli_api.services.diagnosis_service.store_cached_response", lambda *_args, **_kwargs: None)

    result = asyncio.run(
        evaluate_student_record(
            user_major="Computer Science",
            masked_text=(
                "Built a robotics notebook and measured drift before and after calibration. "
                "Compared outcomes and documented method limits."
            ),
            target_university="Example University",
            target_major="Computer Science",
            career_direction="AI engineering",
            project_title="Fallback contract check",
            scope_key=f"axis-fallback:{uuid4()}",
            evidence_keys=["doc:axis-fallback"],
        )
    )

    assert "fallback" in result.headline.lower()
    assert len(result.gap_axes) == len(POSITIVE_AXIS_KEYS)
    assert {axis.key for axis in result.gap_axes} == set(POSITIVE_AXIS_KEYS)
    _assert_default_action_references_existing_payload_ids(result)


def test_legacy_axis_keys_are_normalized_for_backward_compatibility() -> None:
    payload = {
        "headline": "Legacy payload compatibility",
        "strengths": ["Grounded starting point"],
        "gaps": ["Needs clearer follow-up"],
        "recommended_focus": "Repair weakest axis first",
        "risk_level": "warning",
        "gap_axes": [
            {
                "key": "conceptual_depth",
                "label": "Legacy conceptual axis",
                "score": 62,
                "severity": "watch",
                "rationale": "Legacy rationale",
                "evidence_hint": "Legacy hint",
            }
        ],
        "recommended_directions": [
            {
                "id": "subject_major_alignment",
                "label": "Legacy direction",
                "summary": "Legacy summary",
                "why_now": "Legacy why now",
                "complexity": "lighter",
                "related_axes": ["subject_major_alignment"],
            }
        ],
        "recommended_default_action": {
            "direction_id": "subject_major_alignment",
            "topic_id": "legacy-topic",
            "page_count": 5,
            "export_format": "pdf",
            "template_id": "legacy-template",
            "rationale": "Legacy default action",
        },
    }

    result = DiagnosisResult.model_validate(payload)

    assert result.gap_axes[0].key == "universal_rigor"
    assert result.recommended_directions[0].id == "cluster_suitability"
    assert result.recommended_directions[0].related_axes == ["cluster_suitability"]
    assert result.recommended_default_action is not None
    assert result.recommended_default_action.direction_id == "cluster_suitability"


def test_diagnosis_route_response_serializes_grounded_payload(monkeypatch) -> None:
    result = build_grounded_diagnosis_result(
        project_title="Route serialization check",
        target_major="Computer Science",
        target_university="Example University",
        career_direction="Software engineering",
        document_count=1,
        full_text=(
            "Observed differences between two algorithm choices, measured runtime changes, "
            "and documented constraints with follow-up questions."
        ),
    )
    run = SimpleNamespace(
        id="run-axis-contract",
        project_id="project-axis-contract",
        status="COMPLETED",
        result_payload=result.model_dump_json(),
        error_message=None,
        review_tasks=[],
        policy_flags=[],
        response_traces=[],
    )

    monkeypatch.setattr(diagnosis_route, "latest_response_trace", lambda _run: None)
    monkeypatch.setattr(diagnosis_route, "get_latest_job_for_resource", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(diagnosis_route, "get_latest_report_artifact_for_run", lambda *_args, **_kwargs: None)

    response = diagnosis_route._build_run_response(SimpleNamespace(), run)

    assert response.result_payload is not None
    assert len(response.result_payload.gap_axes) == len(POSITIVE_AXIS_KEYS)
    assert {axis.key for axis in response.result_payload.gap_axes} == set(POSITIVE_AXIS_KEYS)
    _assert_default_action_references_existing_payload_ids(response.result_payload)
