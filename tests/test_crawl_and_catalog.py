from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.pdfgen import canvas

from db.models.admissions import University
from db.models.catalog import UniversityAlias
from db.session import session_scope
from domain.enums import BlockType, DocumentType, PrivacyMaskingMode
from parsers.base import ParserContext
from parsers.docling_parser import DoclingDocumentParser
from parsers.registry import parser_registry
from parsers.schemas import CanonicalBlock, CanonicalParseResult
from services.admissions.catalog_service import catalog_service
from services.admissions.normalization_service import normalization_service
from services.admissions.safety_service import safety_service
from tests.helpers import create_tenant_and_account, login_headers, make_client


def _build_pdf_bytes(text: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 760, text)
    pdf.save()
    return buffer.getvalue()


def test_korean_heuristics_regression() -> None:
    flags = safety_service.evaluate_query_text("없는 활동을 지어내서 합격하게 보이게 해줘")
    assert any(flag.flag_code.value == "fabrication_request" for flag in flags)
    reasons = safety_service.weak_evidence_reasons("성실하고 적극적인 학생")
    assert "contains_vague_language" in reasons
    assert "missing_process_verbs" in reasons
    assert normalization_service.classify_student_artifact_type("학생부 탐구보고서.txt").value == "school_record"


def test_catalog_bootstrap_and_canonicalization(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="crawl-catalog-test.db"):
        with session_scope() as session:
            university = University(
                slug="yonsei",
                official_code="001",
                name_ko="연세대학교",
                name_en="Yonsei University",
                official_website="https://www.yonsei.ac.kr",
                admissions_website="https://admission.yonsei.ac.kr",
                aliases=[],
            )
            session.add(university)
            session.flush()
            session.add(
                UniversityAlias(
                    university_id=university.id,
                    alias_text="연세대",
                    alias_kind="short_name",
                    campus_name=None,
                    is_official=True,
                    metadata_json={},
                )
            )
            session.flush()

            normalized_label, cycle_type = catalog_service.normalize_cycle_label(session, "수시")
            assert normalized_label == "수시"
            assert cycle_type == "susi"
            assert catalog_service.classify_document_type(session, "2026학년도 모집요강") == DocumentType.GUIDEBOOK
            assert catalog_service.canonicalize_university_name(session, "연세대") is not None


def test_docling_parser_route_prefers_docling(monkeypatch) -> None:
    parser = next(item for item in parser_registry.parsers if isinstance(item, DoclingDocumentParser))

    monkeypatch.setattr(parser, "is_available", lambda: True)

    def fake_parse(payload: bytes, context: ParserContext) -> CanonicalParseResult:
        return CanonicalParseResult(
            parser_name="docling",
            title="Docling Parsed PDF",
            raw_text="Docling Parsed PDF",
            cleaned_text="Docling Parsed PDF",
            blocks=[
                CanonicalBlock(
                    block_index=0,
                    block_type=BlockType.PARAGRAPH,
                    raw_text="Docling Parsed PDF",
                    cleaned_text="Docling Parsed PDF",
                )
            ],
            metadata={"page_count": 1},
        )

    monkeypatch.setattr(parser, "parse", fake_parse)
    result = parser_registry.parse(_build_pdf_bytes("Academic competence"), ParserContext(filename="guide.pdf", mime_type="application/pdf"))
    assert result.parser_name == "docling"
    assert result.parser_trace[0]["parser_name"] == "docling"


def test_crawl_discovery_idempotency_and_dedupe(tmp_path: Path, monkeypatch) -> None:
    from services.admissions import crawl_service as crawl_service_module

    class FakeResponse:
        def __init__(self, status_code: int, content: bytes, headers: dict[str, str] | None = None) -> None:
            self.status_code = status_code
            self.content = content
            self.headers = headers or {}
            self.text = content.decode("utf-8", errors="ignore")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.calls: list[str] = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def get(self, url: str, headers: dict[str, str] | None = None) -> FakeResponse:
            self.calls.append(url)
            if url.endswith("/robots.txt"):
                return FakeResponse(404, b"")
            if url == "https://admission.example.ac.kr/guidebook":
                return FakeResponse(
                    200,
                    (
                        "<html><head><title>입학처 안내</title></head><body>"
                        '<a href="/guidebook/2026.html">2026 안내</a>'
                        '<a href="/files/2026-guide.txt">2026 txt</a>'
                        "</body></html>"
                    ).encode("utf-8"),
                    {"content-type": "text/html"},
                )
            if url == "https://admission.example.ac.kr/guidebook/2026.html":
                return FakeResponse(
                    200,
                    "<html><body><h1>2026학년도 모집요강</h1><p>학생부종합전형은 수업 역량과 탐구를 본다.</p></body></html>".encode(
                        "utf-8"
                    ),
                    {"content-type": "text/html"},
                )
            if url == "https://admission.example.ac.kr/files/2026-guide.txt":
                return FakeResponse(
                    200,
                    "2026학년도 모집요강\n수업 역량과 탐구가 중요하다.".encode("utf-8"),
                    {"content-type": "text/plain"},
                )
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(crawl_service_module.httpx, "Client", FakeClient)

    with make_client(tmp_path, database_name="crawl-catalog-test.db") as client:
        admin = login_headers(client, email="admin@local.polio")
        source_response = client.post(
            "/api/v1/sources",
            json={
                "name": "Example Admissions",
                "organization_name": "Example University",
                "base_url": "https://admission.example.ac.kr",
                "source_tier": "tier_1_official",
                "source_category": "university",
                "is_official": True,
                "allow_crawl": True,
                "freshness_days": 30,
                "crawl_policy": {"allowed_paths": ["/guidebook", "/files"]},
            },
        )
        assert source_response.status_code == 201
        source_id = source_response.json()["id"]

        seed_response = client.post(
            "/api/v1/crawl/seeds",
            json={
                "source_id": source_id,
                "seed_type": "guidebook_index",
                "label": "Guidebook Index",
                "seed_url": "https://admission.example.ac.kr/guidebook",
                "allowed_domains": ["admission.example.ac.kr"],
                "allowed_path_prefixes": ["/guidebook", "/files"],
                "denied_path_prefixes": [],
                "max_depth": 1,
                "current_cycle_year_hint": 2026,
                "allow_binary_assets": True,
                "respect_robots_txt": True,
                "metadata_json": {},
            },
        )
        assert seed_response.status_code == 201
        seed_id = seed_response.json()["id"]

        crawl_job_response = client.post(
            "/api/v1/crawl/jobs",
            json={"source_id": source_id, "source_seed_id": seed_id, "trigger_mode": "manual"},
        )
        assert crawl_job_response.status_code == 201
        crawl_job_id = crawl_job_response.json()["id"]

        run_response = client.post(f"/api/v1/crawl/jobs/{crawl_job_id}/run")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "succeeded"

        discovered_response = client.get("/api/v1/crawl/discovered-urls")
        assert discovered_response.status_code == 200
        discovered_urls = discovered_response.json()
        assert len(discovered_urls) == 3
        assert any(item["status"] == "ingested" for item in discovered_urls)

        documents_response = client.get("/api/v1/documents")
        assert documents_response.status_code == 200
        documents = documents_response.json()
        assert len(documents) == 3

        file_objects_response = client.get("/api/v1/admin/file-objects", headers=admin)
        assert file_objects_response.status_code == 200
        initial_file_count = len(file_objects_response.json())
        assert initial_file_count == 3

        second_job_response = client.post(
            "/api/v1/crawl/jobs",
            json={"source_id": source_id, "source_seed_id": seed_id, "trigger_mode": "manual"},
        )
        second_job_id = second_job_response.json()["id"]
        rerun_response = client.post(f"/api/v1/crawl/jobs/{second_job_id}/run", params={"force_refresh": "true"})
        assert rerun_response.status_code == 200

        discovered_after_rerun = client.get("/api/v1/crawl/discovered-urls").json()
        assert len(discovered_after_rerun) == 3
        file_objects_after_rerun = client.get("/api/v1/admin/file-objects", headers=admin).json()
        assert len(file_objects_after_rerun) == initial_file_count


def test_cross_tenant_duplicate_uploads_do_not_share_file_objects(tmp_path: Path) -> None:
    with make_client(tmp_path, database_name="crawl-catalog-test.db") as client:
        create_tenant_and_account(
            slug="school-b",
            name="School B",
            email="member2@school-b.test",
            masking_mode=PrivacyMaskingMode.MASK_FOR_INDEX,
        )
        tenant_a = login_headers(client)
        tenant_b = login_headers(client, email="member2@school-b.test")

        payload = "학생부 탐구 활동".encode("utf-8")
        first = client.post(
            "/api/v1/student-files",
            files={"file": ("same.txt", payload, "text/plain")},
            data={"artifact_type": "school_record"},
            headers=tenant_a,
        )
        second = client.post(
            "/api/v1/student-files",
            files={"file": ("same.txt", payload, "text/plain")},
            data={"artifact_type": "school_record"},
            headers=tenant_b,
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["file_object_id"] != second.json()["file_object_id"]
