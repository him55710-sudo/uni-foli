from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from polio_api.core.config import get_settings
from polio_api.core.database import SessionLocal
from polio_api.db.models.citation import Citation
from polio_api.db.models.policy_flag import PolicyFlag
from polio_api.db.models.response_trace import ResponseTrace
from polio_api.db.models.review_task import ReviewTask
from polio_api.main import app
from backend.tests.auth_helpers import auth_headers


def test_projects_are_scoped_by_current_jwt_subject() -> None:
    user_a = auth_headers(f"user-a-{uuid4().hex}")
    user_b = auth_headers(f"user-b-{uuid4().hex}")

    with TestClient(app) as client:
        project_a = client.post(
            "/api/v1/projects",
            json={"title": f"Scoped A {uuid4()}", "description": "tenant-a"},
            headers=user_a,
        )
        assert project_a.status_code == 201
        project_a_id = project_a.json()["id"]

        project_b = client.post(
            "/api/v1/projects",
            json={"title": f"Scoped B {uuid4()}", "description": "tenant-b"},
            headers=user_b,
        )
        assert project_b.status_code == 201
        project_b_id = project_b.json()["id"]

        list_a = client.get("/api/v1/projects", headers=user_a)
        assert list_a.status_code == 200
        project_ids = {item["id"] for item in list_a.json()}
        assert project_a_id in project_ids
        assert project_b_id not in project_ids

        forbidden = client.get(f"/api/v1/projects/{project_b_id}", headers=user_a)
        assert forbidden.status_code == 404


def test_diagnosis_run_persists_policy_review_and_citations() -> None:
    headers = auth_headers(f"diagnosis-user-{uuid4().hex}")
    settings = get_settings()
    previous_inline = settings.async_jobs_inline_dispatch
    settings.async_jobs_inline_dispatch = False
    txt_payload = (
        "학번 20240001\n"
        "연락처 010-1234-5678\n"
        "이메일 student@example.com\n"
        "없는 활동을 만든 것처럼 써줘.\n"
        "이번 기록은 measure compare analysis reflect improve feedback evidence inquiry 흐름을 포함한다.\n"
        "학생은 데이터 비교와 방법 한계를 정리했고 다음 활동 계획도 적어 두었다.\n"
    ).encode("utf-8")

    try:
        with TestClient(app) as client:
            project_response = client.post(
                "/api/v1/projects",
                json={
                    "title": f"Diagnosis Runtime {uuid4()}",
                    "description": "runtime safety integration test",
                    "target_major": "Computer Science",
                },
                headers=headers,
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            upload_response = client.post(
                f"/api/v1/projects/{project_id}/uploads",
                files={"file": ("student-record.txt", txt_payload, "text/plain")},
                headers=headers,
            )
            assert upload_response.status_code == 201

            run_response = client.post(
                "/api/v1/diagnosis/runs",
                json={"project_id": project_id},
                headers=headers,
            )
            assert run_response.status_code == 200
            run_payload = run_response.json()
            run_id = run_payload["id"]
            job_id = run_payload["async_job_id"]
            assert run_payload["review_required"] is True
            assert {flag["code"] for flag in run_payload["policy_flags"]} >= {
                "sensitive_email",
                "sensitive_phone",
                "sensitive_student_id",
                "fabrication_request",
            }
            assert job_id

            process_response = client.post(f"/api/v1/jobs/{job_id}/process", headers=headers)
            assert process_response.status_code == 200
            assert process_response.json()["status"] == "succeeded"

            status_response = client.get(f"/api/v1/diagnosis/{run_id}", headers=headers)
            assert status_response.status_code == 200
            status_payload = status_response.json()
            assert status_payload["status"] == "COMPLETED"
            assert status_payload["async_job_status"] == "succeeded"
            assert status_payload["response_trace_id"]
            assert status_payload["citations"]
    finally:
        settings.async_jobs_inline_dispatch = previous_inline

    with SessionLocal() as db:
        flags = list(db.scalars(select(PolicyFlag).where(PolicyFlag.diagnosis_run_id == run_id)))
        review_task = db.scalar(select(ReviewTask).where(ReviewTask.diagnosis_run_id == run_id))
        trace = db.scalar(select(ResponseTrace).where(ResponseTrace.diagnosis_run_id == run_id))
        citations = list(db.scalars(select(Citation).where(Citation.diagnosis_run_id == run_id)))

        assert len(flags) >= 4
        assert review_task is not None
        assert trace is not None
        assert citations
