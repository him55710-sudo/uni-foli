from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from polio_api.services.prompt_registry import get_prompt_registry
from tests.smoke.helpers import make_client


def _create_project_with_record(client) -> str:
    project = client.post(
        "/api/v1/projects",
        json={
            "title": "Concept Inquiry Project",
            "description": "Guided diagnosis smoke coverage",
            "target_major": "Mathematics Education",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    upload = client.post(
        f"/api/v1/projects/{project_id}/uploads",
        files={
            "file": (
                "record.md",
                (
                    "# Math record\n"
                    "- The student applied statistics to a school lunch survey.\n"
                    "- The student focused on practical recommendations for cafeteria service.\n"
                    "- The reflection mentioned that the underlying concept explanation stayed shallow.\n"
                    "- The record did not include a second follow-up inquiry.\n"
                    "- The write-up mentioned method limits but lacked a stronger principle explanation.\n"
                ).encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    return project_id


def _run_diagnosis(client, project_id: str) -> dict:
    response = client.post(
        "/api/v1/diagnosis/run?wait_for_completion=true",
        json={"project_id": project_id},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["result_payload"] is not None
    return payload


def test_guided_diagnosis_returns_structured_choices(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        format_catalog = client.get("/api/v1/render-jobs/formats")
        assert format_catalog.status_code == 200, format_catalog.text
        format_defaults = {item["format"]: item["default_template_id"] for item in format_catalog.json()}
        assert format_defaults["pdf"] == "clean_report_basic"
        assert format_defaults["pptx"] == "presentation_minimal"
        assert format_defaults["hwpx"] == "activity_summary_school"

        project_id = _create_project_with_record(client)
        diagnosis = _run_diagnosis(client, project_id)
        result = diagnosis["result_payload"]

        assert result["diagnosis_summary"]["overview"]
        assert result["diagnosis_summary"]["authenticity_note"]
        assert 2 <= len(result["recommended_directions"]) <= 5
        assert result["recommended_default_action"]

        axis_keys = {axis["key"] for axis in result["gap_axes"]}
        assert {
            "conceptual_depth",
            "inquiry_continuity",
            "evidence_density",
            "process_explanation",
            "subject_major_alignment",
        }.issubset(axis_keys)

        first_direction = result["recommended_directions"][0]
        assert first_direction["topic_candidates"]
        assert first_direction["page_count_options"]
        assert all(option["page_count"] >= 5 for option in first_direction["page_count_options"])
        assert first_direction["format_recommendations"]
        assert first_direction["template_candidates"]
        assert result["recommended_default_action"]["page_count"] >= 5
        default_direction = next(
            direction
            for direction in result["recommended_directions"]
            if direction["id"] == result["recommended_default_action"]["direction_id"]
        )
        assert result["recommended_default_action"]["topic_id"] in {
            topic["id"] for topic in default_direction["topic_candidates"]
        }

        template_catalog = client.get("/api/v1/render-jobs/templates", params={"render_format": "pdf"})
        assert template_catalog.status_code == 200, template_catalog.text
        template_ids = {item["id"] for item in template_catalog.json()}
        assert "clean_report_basic" in template_ids
        assert "academic_report_evidence" in template_ids
        assert "presentation_visual_focus" not in {
            item["id"] for item in client.get("/api/v1/render-jobs/templates", params={"render_format": "hwpx"}).json()
        }


def test_guided_plan_template_render_flow(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        project_id = _create_project_with_record(client)
        diagnosis = _run_diagnosis(client, project_id)
        result = diagnosis["result_payload"]
        direction = result["recommended_directions"][0]
        format_choice = next(
            (item for item in direction["format_recommendations"] if item["format"] == "pdf"),
            direction["format_recommendations"][0],
        )
        template_choice = next(
            (item for item in direction["template_candidates"] if "pdf" in item["supported_formats"]),
            direction["template_candidates"][0],
        )

        guided_plan = client.post(
            f"/api/v1/diagnosis/{diagnosis['id']}/guided-plan",
            json={
                "direction_id": direction["id"],
                "topic_id": direction["topic_candidates"][0]["id"],
                "page_count": direction["page_count_options"][0]["page_count"],
                "export_format": format_choice["format"],
                "template_id": template_choice["id"],
                "include_provenance_appendix": True,
                "hide_internal_provenance_on_final_export": True,
            },
        )
        assert guided_plan.status_code == 200, guided_plan.text
        plan_payload = guided_plan.json()
        outline = plan_payload["outline"]
        assert outline["draft_id"]
        assert outline["sections"]
        assert outline["template_id"] == template_choice["id"]
        assert outline["include_provenance_appendix"] is True
        assert outline["page_count"] >= 5

        render_job = client.post(
            "/api/v1/render-jobs",
            json={
                "project_id": project_id,
                "draft_id": outline["draft_id"],
                "render_format": outline["export_format"],
                "template_id": outline["template_id"],
                "include_provenance_appendix": True,
                "hide_internal_provenance_on_final_export": True,
            },
        )
        assert render_job.status_code == 201, render_job.text
        render_payload = render_job.json()
        assert render_payload["template_id"] == outline["template_id"]
        assert render_payload["include_provenance_appendix"] is True
        assert render_payload["hide_internal_provenance_on_final_export"] is True

        processed = client.post(f"/api/v1/render-jobs/{render_payload['id']}/process")
        assert processed.status_code == 200, processed.text
        processed_payload = processed.json()
        assert processed_payload["status"] == "completed"
        assert processed_payload["download_url"]

        download = client.get(processed_payload["download_url"])
        assert download.status_code == 200, download.text
        assert download.content
        pdf_reader = PdfReader(BytesIO(download.content))
        assert len(pdf_reader.pages) >= 5


def test_guided_plan_rejects_choices_outside_structured_options(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        project_id = _create_project_with_record(client)
        diagnosis = _run_diagnosis(client, project_id)
        result = diagnosis["result_payload"]
        direction = result["recommended_directions"][0]

        invalid_pages = client.post(
            f"/api/v1/diagnosis/{diagnosis['id']}/guided-plan",
            json={
                "direction_id": direction["id"],
                "topic_id": direction["topic_candidates"][0]["id"],
                "page_count": 17,
                "export_format": direction["format_recommendations"][0]["format"],
                "template_id": direction["template_candidates"][0]["id"],
            },
        )
        assert invalid_pages.status_code == 422, invalid_pages.text

        invalid_template = client.post(
            f"/api/v1/diagnosis/{diagnosis['id']}/guided-plan",
            json={
                "direction_id": direction["id"],
                "topic_id": direction["topic_candidates"][0]["id"],
                "page_count": direction["page_count_options"][0]["page_count"],
                "export_format": "hwpx",
                "template_id": "presentation_visual_focus",
            },
        )
        assert invalid_template.status_code == 422, invalid_template.text


def test_diagnosis_report_delivery_pipeline_auto_and_manual_paths(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        project_id = _create_project_with_record(client)
        diagnosis = _run_diagnosis(client, project_id)
        diagnosis_id = diagnosis["id"]

        status_response = client.get(f"/api/v1/diagnosis/{diagnosis_id}")
        assert status_response.status_code == 200, status_response.text
        status_payload = status_response.json()
        assert status_payload["report_status"] in {
            "AUTO_STARTING",
            "QUEUED",
            "RUNNING",
            "RETRYING",
            "READY",
            "FAILED",
        }

        first_report = client.post(
            f"/api/v1/diagnosis/{diagnosis_id}/report",
            json={
                "report_mode": "premium_10p",
                "include_appendix": True,
                "include_citations": True,
                "force_regenerate": False,
            },
        )
        assert first_report.status_code == 200, first_report.text
        first_payload = first_report.json()
        assert first_payload["status"] in {"READY", "FAILED"}

        second_report = client.post(
            f"/api/v1/diagnosis/{diagnosis_id}/report",
            json={
                "report_mode": "premium_10p",
                "include_appendix": True,
                "include_citations": True,
                "force_regenerate": False,
            },
        )
        assert second_report.status_code == 200, second_report.text
        second_payload = second_report.json()

        if first_payload["status"] == "READY":
            assert second_payload["id"] == first_payload["id"]
            assert second_payload["version"] == first_payload["version"]

        regenerated = client.post(
            f"/api/v1/diagnosis/{diagnosis_id}/report",
            json={
                "report_mode": "premium_10p",
                "include_appendix": True,
                "include_citations": True,
                "force_regenerate": True,
            },
        )
        assert regenerated.status_code == 200, regenerated.text
        regenerated_payload = regenerated.json()
        assert regenerated_payload["version"] >= first_payload["version"]


def test_guided_diagnosis_prompt_assets_are_registered() -> None:
    get_prompt_registry.cache_clear()
    registry = get_prompt_registry()

    asset_names = {
        "chat.guided-diagnosis-orchestration",
        "chat.topic-candidate-generator",
        "chat.page-count-selector",
        "chat.template-recommender",
    }
    for asset_name in asset_names:
        asset = registry.get_asset(asset_name)
        assert asset.body

    composed = registry.compose_prompt("diagnosis.grounded-analysis")
    assert "Do not behave like a passive chatbot." in composed
    assert "recommended_default_action" in composed
    assert "template_candidates" in composed
