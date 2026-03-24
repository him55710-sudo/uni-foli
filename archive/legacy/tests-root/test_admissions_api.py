from __future__ import annotations

from pathlib import Path

from tests.helpers import login_headers, make_client


def test_health_endpoint(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="admissions-test.db") as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["app"]


def test_source_registration_round_trip(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="admissions-test.db") as client:
        create_response = client.post(
            "/api/v1/sources",
            json={
                "name": "교육부",
                "organization_name": "교육부",
                "base_url": "https://www.moe.go.kr",
                "source_tier": "tier_1_official",
                "source_category": "ministry",
                "is_official": True,
                "allow_crawl": True,
                "freshness_days": 14,
                "crawl_policy": {"allowed_paths": ["/"]},
            },
        )
        assert create_response.status_code == 201
        source_id = create_response.json()["id"]

        list_response = client.get("/api/v1/sources")
        assert list_response.status_code == 200
        assert any(item["id"] == source_id for item in list_response.json())


def test_student_file_upload_parses_text(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="admissions-test.db") as client:
        headers = login_headers(client)
        upload_response = client.post(
            "/api/v1/student-files",
            files={"file": ("reflection.txt", "생기부 탐구\n수업 활동 분석".encode("utf-8"), "text/plain")},
            data={"artifact_type": "reflection_note"},
            headers=headers,
        )
        assert upload_response.status_code == 201
        payload = upload_response.json()
        assert payload["status"] in {"parsed", "review_required"}
        assert payload["upload_filename"] == "reflection.txt"
        assert payload["tenant_id"]
