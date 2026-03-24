from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.core.logging import JsonLogFormatter
from app.core.redaction import redact_text_for_logs
from domain.enums import PrivacyMaskingMode
from services.admissions import privacy_service as privacy_service_module
from tests.helpers import create_tenant_and_account, login_headers, make_client


def test_student_routes_require_auth(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="auth-privacy.db") as client:
        response = client.get("/api/v1/student-files")
        assert response.status_code == 401


def test_tenant_isolation_for_student_files_and_analysis_runs(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="auth-privacy.db") as client:
        create_tenant_and_account(
            slug="school-b",
            name="School B",
            email="member2@school-b.test",
            masking_mode=PrivacyMaskingMode.MASK_FOR_INDEX,
        )
        member_a = login_headers(client)
        member_b = login_headers(client, email="member2@school-b.test")

        upload_response = client.post(
            "/api/v1/student-files",
            files={"file": ("record.txt", "학생부 수업 탐구 기록".encode("utf-8"), "text/plain")},
            data={"artifact_type": "school_record"},
            headers=member_a,
        )
        assert upload_response.status_code == 201
        student_file_id = upload_response.json()["id"]

        run_response = client.post(
            "/api/v1/analysis/runs",
            json={"run_type": "evidence_quality", "primary_student_file_id": student_file_id, "input_snapshot": {}},
            headers=member_a,
        )
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]

        forbidden_file = client.get(f"/api/v1/student-files/{student_file_id}", headers=member_b)
        assert forbidden_file.status_code == 403

        forbidden_run = client.get(f"/api/v1/analysis/runs/{run_id}", headers=member_b)
        assert forbidden_run.status_code == 403

        list_response = client.get("/api/v1/student-files", headers=member_b)
        assert list_response.status_code == 200
        assert list_response.json() == []


def test_privacy_masking_pipeline_and_admin_scan_visibility(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="auth-privacy.db") as client:
        member = login_headers(client)
        admin = login_headers(client, email="admin@local.polio")

        upload_response = client.post(
            "/api/v1/student-files",
            files={
                "file": (
                    "pii.txt",
                    "연락처는 010-1234-5678이고 이메일은 polio@example.com 입니다.".encode("utf-8"),
                    "text/plain",
                )
            },
            data={"artifact_type": "reflection_note"},
            headers=member,
        )
        assert upload_response.status_code == 201
        payload = upload_response.json()
        assert payload["pii_detected"] is True
        assert "<PHONE_NUMBER>" in payload["artifacts"][0]["cleaned_text"]
        assert "<EMAIL_ADDRESS>" in payload["artifacts"][0]["cleaned_text"]

        scans_response = client.get(
            "/api/v1/admin/privacy-scans",
            params={"student_file_id": payload["id"]},
            headers=admin,
        )
        assert scans_response.status_code == 200
        scans = scans_response.json()
        assert scans
        assert scans[0]["pii_detected"] is True
        findings = scans[0]["findings_json"]["findings"]
        assert findings[0].get("match_preview")


def test_privacy_helper_subprocess_path(tmp_path: Path, monkeypatch) -> None:
    helper_root = tmp_path / "helper-root"
    scripts_dir = helper_root / "scripts"
    scripts_dir.mkdir(parents=True)
    helper_script = scripts_dir / "presidio_masking_helper.py"
    helper_script.write_text(
        "import json, sys\n"
        "payload = json.loads(sys.stdin.read())\n"
        "sys.stdout.write(json.dumps({'masked_text': '<EMAIL_ADDRESS>', 'findings': [{'entity_type': 'EMAIL_ADDRESS', 'start': 0, 'end': 5, 'score': 0.9, 'text': 'a@b.c'}]}))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(privacy_service_module, "PROJECT_ROOT", helper_root)
    with make_client(
        tmp_path,
        database_name="auth-privacy-helper.db",
        extra_env={
            "PRESIDIO_ENABLED": "true",
            "PRESIDIO_HELPER_PYTHON": sys.executable,
            "PRESIDIO_ALLOW_REGEX_FALLBACK": "false",
        },
    ) as client:
        member = login_headers(client)
        upload_response = client.post(
            "/api/v1/student-files",
            files={"file": ("pii.txt", "polio@example.com".encode("utf-8"), "text/plain")},
            data={"artifact_type": "reflection_note"},
            headers=member,
        )
        assert upload_response.status_code == 201
        artifact = upload_response.json()["artifacts"][0]
        assert artifact["cleaned_text"] == "<EMAIL_ADDRESS>"


def test_deletion_workflow_soft_delete(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="auth-privacy.db") as client:
        member = login_headers(client)
        admin = login_headers(client, email="admin@local.polio")

        upload_response = client.post(
            "/api/v1/student-files",
            files={"file": ("delete-me.txt", "학생부 삭제 테스트".encode("utf-8"), "text/plain")},
            data={"artifact_type": "school_record"},
            headers=member,
        )
        assert upload_response.status_code == 201
        student_file_id = upload_response.json()["id"]

        request_response = client.post(
            f"/api/v1/student-files/{student_file_id}/deletion-requests",
            json={
                "target_kind": "student_file",
                "target_id": student_file_id,
                "deletion_mode": "soft_delete",
                "reason": "remove test data",
            },
            headers=member,
        )
        assert request_response.status_code == 201
        deletion_request_id = request_response.json()["id"]

        execute_response = client.post(f"/api/v1/admin/deletion-requests/{deletion_request_id}/execute", headers=admin)
        assert execute_response.status_code == 200
        assert execute_response.json()["status"] == "completed"

        get_response = client.get(f"/api/v1/student-files/{student_file_id}", headers=member)
        assert get_response.status_code == 404

        events_response = client.get("/api/v1/admin/deletion-events", headers=admin)
        assert events_response.status_code == 200
        assert any(event["target_kind"] == "student_file" for event in events_response.json())


def test_redacted_logging_behavior() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="polio.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="student email polio@example.com phone 010-1234-5678",
        args=(),
        exc_info=None,
    )
    record.cleaned_text = "민감 정보 polio@example.com"
    record.access_token = "secret-token"
    payload = formatter.format(record)
    assert "polio@example.com" not in payload
    assert "010-1234-5678" not in payload
    assert "<REDACTED>" in payload
    assert "<EMAIL>" in payload
    assert redact_text_for_logs("010-1234-5678") == "<PHONE_NUMBER>"
