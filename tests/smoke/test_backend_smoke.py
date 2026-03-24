from __future__ import annotations

from pathlib import Path

from tests.smoke.helpers import make_client


def test_backend_smoke_flow(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        create_project = client.post(
            "/api/v1/projects",
            json={
                "title": "Grounded Research Project",
                "description": "Smoke test project",
                "target_major": "Environmental Engineering",
            },
        )
        assert create_project.status_code == 201, create_project.text
        project_id = create_project.json()["id"]

        upload = client.post(
            f"/api/v1/projects/{project_id}/uploads",
            files={
                "file": (
                    "reflection.md",
                    (
                        "# Actual record\n"
                        "- The student measured fine dust levels around the school.\n"
                        "- The student compared results across two time periods.\n"
                        "- The student wrote reflections on method limits.\n"
                    ).encode("utf-8"),
                    "text/markdown",
                )
            },
        )
        assert upload.status_code == 201, upload.text
        assert upload.json()["status"] == "parsed"

        diagnosis = client.post(f"/api/v1/projects/{project_id}/diagnose")
        assert diagnosis.status_code == 200, diagnosis.text
        diagnosis_payload = diagnosis.json()
        assert "overall" in diagnosis_payload
        assert "summary" in diagnosis_payload["overall"]
        assert "prescription" in diagnosis_payload

        blueprint = client.get(
            "/api/v1/blueprints/current",
            params={"project_id": project_id},
        )
        assert blueprint.status_code == 200, blueprint.text
        blueprint_payload = blueprint.json()
        assert blueprint_payload["project_id"] == project_id
        assert blueprint_payload["priority_quests"]
        assert blueprint_payload["subject_groups"]
        assert blueprint_payload["expected_record_effects"]

        top_quest_id = blueprint_payload["priority_quests"][0]["id"]
        start_quest = client.post(f"/api/v1/quests/{top_quest_id}/start")
        assert start_quest.status_code == 200, start_quest.text
        start_payload = start_quest.json()
        assert start_payload["project_id"] == project_id
        assert start_payload["status"] == "IN_PROGRESS"
        assert start_payload["starter_choices_seed"]
        assert start_payload["document_seed_markdown"].startswith("#")

        draft = client.post(
            f"/api/v1/projects/{project_id}/drafts",
            json={
                "title": "Grounded Draft",
                "content_markdown": "# Draft\nThis paragraph stays tied to the uploaded record.",
            },
        )
        assert draft.status_code == 201, draft.text
        draft_payload = draft.json()
        assert draft_payload["project_id"] == project_id

        export = client.post(
            f"/api/v1/projects/{project_id}/export",
            json={
                "content_markdown": "# Export\nOnly grounded content is exported in this smoke test.",
            },
        )
        assert export.status_code == 200, export.text
        assert export.headers["content-type"].startswith("application/vnd.hancom.hwpx")
