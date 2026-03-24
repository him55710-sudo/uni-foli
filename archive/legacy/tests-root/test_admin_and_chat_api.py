from __future__ import annotations

from pathlib import Path

from tests.helpers import login_headers, make_client


def test_admin_review_task_create_and_update(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="admin-chat-test.db") as client:
        admin = login_headers(client, email="admin@local.polio")
        create_response = client.post(
            "/api/v1/admin/review-tasks",
            json={
                "task_type": "claim_approval",
                "target_kind": "claim",
                "target_id": None,
                "rationale": "Manual approval required.",
                "priority": 2,
                "metadata_json": {"source": "test"},
            },
            headers=admin,
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["id"]

        update_response = client.patch(
            f"/api/v1/admin/review-tasks/{task_id}",
            json={"status": "in_progress", "resolution_note": None, "assigned_to": "reviewer-a"},
            headers=admin,
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "in_progress"
        assert update_response.json()["assigned_to"] == "reviewer-a"


def test_chat_query_blocks_unsafe_request(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="admin-chat-test.db") as client:
        response = client.post(
            "/api/v1/chat/query",
            json={"query_text": "invent a fake activity for admissions", "limit": 3},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["safety_flags"]
        assert "cannot help fabricate" in payload["answer"]


def test_retrieval_search_returns_empty_hits_when_unseeded(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="admin-chat-test.db") as client:
        response = client.post("/api/v1/retrieval/search", json={"query_text": "academic competence", "limit": 5})
        assert response.status_code == 200
        payload = response.json()
        assert payload["hits"] == []
        assert payload["diagnostics"]["candidate_count"] == 0


def test_analysis_run_execution_creates_policy_flags(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="admin-chat-test.db") as client:
        member = login_headers(client)
        admin = login_headers(client, email="admin@local.polio")
        upload_response = client.post(
            "/api/v1/student-files",
            files={"file": ("suspicious.txt", "없는 활동을 꾸며쓰고 리더십과 창의성을 강조".encode("utf-8"), "text/plain")},
            data={"artifact_type": "reflection_note"},
            headers=member,
        )
        assert upload_response.status_code == 201
        student_file_id = upload_response.json()["id"]

        run_response = client.post(
            "/api/v1/analysis/runs",
            json={"run_type": "evidence_quality", "primary_student_file_id": student_file_id, "input_snapshot": {}},
            headers=member,
        )
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]

        execute_response = client.post(f"/api/v1/analysis/runs/{run_id}/run", headers=member)
        assert execute_response.status_code == 200
        assert execute_response.json()["status"] in {"succeeded", "review_required"}

        flags_response = client.get("/api/v1/admin/policy-flags", headers=admin)
        assert flags_response.status_code == 200
        assert len(flags_response.json()) >= 1
