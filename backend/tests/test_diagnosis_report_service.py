from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from polio_api.schemas.diagnosis import DiagnosisResultPayload
from polio_api.services import diagnosis_report_service as report_service


def _build_minimal_result_payload() -> DiagnosisResultPayload:
    return DiagnosisResultPayload.model_validate(
        {
            "headline": "기초 진단 헤드라인",
            "strengths": ["탐구 주제의 일관성이 보입니다."],
            "gaps": ["근거 문장과 인용 연결을 더 명확히 해야 합니다."],
            "recommended_focus": "근거-주장 매핑 강화",
            "risk_level": "warning",
            "next_actions": ["핵심 주장 3개에 근거 출처를 연결하세요."],
            "recommended_topics": ["전공 연계 탐구 심화"],
            "citations": [
                {
                    "source_label": "학생부 기록",
                    "page_number": 2,
                    "excerpt": "탐구 활동의 과정과 결과가 정리됨",
                    "relevance_score": 1.7,
                }
            ],
        }
    )


def test_build_consultant_report_payload_contains_expected_sections(monkeypatch) -> None:
    async def fake_narratives(**kwargs):  # noqa: ANN003
        return report_service._ConsultantNarrativePayload(
            executive_summary="요약 문장",
            final_consultant_memo="최종 메모 문장",
        )

    monkeypatch.setattr(report_service, "_generate_narratives", fake_narratives)

    run = SimpleNamespace(id="run-1")
    project = SimpleNamespace(
        id="project-1",
        title="테스트 프로젝트",
        target_university="서울대학교",
        target_major="컴퓨터공학",
    )
    result = _build_minimal_result_payload()
    documents = [
        SimpleNamespace(
            parse_metadata={
                "student_record_structure": {
                    "section_density": {"세특": 0.8, "창체": 0.4},
                    "weak_sections": ["진로"],
                    "timeline_signals": ["2학년", "3학년"],
                    "activity_clusters": ["탐구/실험"],
                    "subject_major_alignment_signals": ["전공 연계 문장 확인"],
                    "continuity_signals": ["후속 탐구 계획"],
                    "process_reflection_signals": ["한계와 개선점"],
                    "uncertain_items": [],
                }
            }
        )
    ]

    report = asyncio.run(
        report_service.build_consultant_report_payload(
            run=run,
            project=project,
            result=result,
            report_mode="premium_10p",
            template_id="consultant_diagnosis_premium_10p",
            include_appendix=True,
            include_citations=True,
            documents=documents,
        )
    )

    section_ids = {section.id for section in report.sections}
    assert "executive_summary" in section_ids
    assert "section_level_diagnosis" in section_ids
    assert "final_memo" in section_ids
    assert report.render_hints["minimum_pages"] == 10
    assert len(report.roadmap) == 3
    assert report.citations


def test_generate_consultant_report_artifact_requires_completed_diagnosis(monkeypatch) -> None:
    monkeypatch.setattr(report_service, "get_latest_report_artifact_for_run", lambda *args, **kwargs: None)

    run = SimpleNamespace(id="run-2", result_payload=None)
    project = SimpleNamespace(
        id="project-2",
        title="진단 미완료 프로젝트",
        target_university=None,
        target_major=None,
    )

    with pytest.raises(ValueError, match="Diagnosis is not complete yet"):
        asyncio.run(
            report_service.generate_consultant_report_artifact(
                SimpleNamespace(),
                run=run,
                project=project,
                report_mode="compact",
                template_id=None,
                include_appendix=True,
                include_citations=True,
                force_regenerate=False,
            )
        )


def test_generate_consultant_report_artifact_fallbacks_to_failed_status(monkeypatch) -> None:
    class FakeDB:
        def __init__(self) -> None:
            self.added = []

        def add(self, obj) -> None:  # noqa: ANN001
            self.added.append(obj)

        def commit(self) -> None:
            return None

        def refresh(self, obj) -> None:  # noqa: ANN001
            return None

    async def failing_payload_builder(**kwargs):  # noqa: ANN003
        raise RuntimeError("payload generation failure")

    monkeypatch.setattr(report_service, "get_latest_report_artifact_for_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(report_service, "build_consultant_report_payload", failing_payload_builder)
    monkeypatch.setattr(report_service, "list_documents_for_project", lambda *args, **kwargs: [])

    db = FakeDB()
    run = SimpleNamespace(
        id="run-3",
        result_payload=_build_minimal_result_payload().model_dump_json(),
    )
    project = SimpleNamespace(
        id="project-3",
        title="실패 폴백 프로젝트",
        target_university="연세대학교",
        target_major="전기전자공학",
    )

    artifact = asyncio.run(
        report_service.generate_consultant_report_artifact(
            db,
            run=run,
            project=project,
            report_mode="compact",
            template_id=None,
            include_appendix=True,
            include_citations=True,
            force_regenerate=False,
        )
    )

    assert artifact.status == "FAILED"
    assert artifact.error_message
    assert db.added
