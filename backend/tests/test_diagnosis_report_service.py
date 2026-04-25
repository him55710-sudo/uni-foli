from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from unifoli_api.schemas.diagnosis import ConsultantDiagnosisReport, DiagnosisResultPayload
from unifoli_api.services import diagnosis_report_service as report_service
from unifoli_domain.enums import RenderFormat
from unifoli_render.diagnosis_report_design_contract import get_diagnosis_report_design_contract
from unifoli_render.diagnosis_report_pdf_renderer import render_consultant_diagnosis_pdf
from unifoli_render.template_registry import get_template


def _result_payload() -> DiagnosisResultPayload:
    return DiagnosisResultPayload.model_validate(
        {
            "headline": "진단 헤드라인",
            "strengths": ["근거 연결 강점"],
            "gaps": ["과정 설명 보완 필요"],
            "recommended_focus": "근거 밀도 보강",
            "risk_level": "warning",
            "next_actions": ["핵심 주장별 근거 앵커 정리"],
            "recommended_topics": ["비교 실험 기반 보고서", "설계 적용형 보고서", "심화 분석형 보고서"],
            "admission_axes": [
                {
                    "key": "universal_rigor",
                    "label": "학업 및 근거 엄밀성",
                    "score": 72,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "기본 엄밀성은 확보됨",
                    "evidence_hints": [],
                },
                {
                    "key": "universal_specificity",
                    "label": "구체성 및 증거성",
                    "score": 64,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "정량 근거 보강 필요",
                    "evidence_hints": [],
                },
                {
                    "key": "relational_narrative",
                    "label": "서사 연결성",
                    "score": 68,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "서사 축은 존재",
                    "evidence_hints": [],
                },
                {
                    "key": "relational_continuity",
                    "label": "연속성",
                    "score": 66,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "연속성은 부분 확인",
                    "evidence_hints": [],
                },
                {
                    "key": "cluster_depth",
                    "label": "심화도",
                    "score": 70,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "심화 단서 존재",
                    "evidence_hints": [],
                },
                {
                    "key": "cluster_suitability",
                    "label": "전공 적합성",
                    "score": 74,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "전공 연결 양호",
                    "evidence_hints": [],
                },
                {
                    "key": "authenticity_risk",
                    "label": "진정성·과장 위험",
                    "score": 38,
                    "band": "watch",
                    "severity": "medium",
                    "rationale": "일부 구간 추가 검증 필요",
                    "evidence_hints": [],
                },
            ],
        }
    )


def _document_structure(*, contradiction_passed: bool = True) -> dict[str, object]:
    return {
        "coverage_check": {
            "coverage_score": 0.58,
            "reanalysis_required": True,
            "required_sections": ["교과학습발달상황", "세특", "창체", "진로"],
            "missing_required_sections": ["독서", "행동특성"],
        },
        "contradiction_check": {"passed": contradiction_passed, "items": [] if contradiction_passed else [{"section": "독서"}]},
        "weak_sections": ["독서", "행동특성"],
        "timeline_signals": ["2학년 탐구 확장"],
        "subject_major_alignment_signals": ["건축 전공 연결 활동"],
        "continuity_signals": ["학년 간 주제 심화"],
        "process_reflection_signals": ["실험 한계 반영"],
        "section_density": {"교과학습발달상황": 0.72, "세특": 0.64, "독서": 0.22},
        "uncertain_items": ["독서 활동 원문 누락"],
    }


def _evidence_bank() -> list[dict[str, object]]:
    return [
        {"anchor_id": "A1", "page": 1, "quote": "교과 활동 근거", "section": "교과학습발달상황"},
        {"anchor_id": "A2", "page": 2, "quote": "세특 탐구 근거", "section": "세특"},
        {"anchor_id": "A3", "page": 3, "quote": "창체 활동 근거", "section": "창체"},
        {"anchor_id": "A4", "page": 4, "quote": "진로 활동 근거", "section": "진로"},
    ]


def test_score_groups_keep_required_top_level_groups_and_add_consultant_axes() -> None:
    score_groups = report_service._build_score_groups(
        result=_result_payload(),
        document_structure=_document_structure(),
        evidence_items=[],
        evidence_bank=_evidence_bank(),
    )

    assert {group.group for group in score_groups} == {"student_evaluation", "system_quality"}
    student_group = next(group for group in score_groups if group.group == "student_evaluation")
    system_group = next(group for group in score_groups if group.group == "system_quality")

    student_keys = {block.key for block in student_group.blocks}
    assert "academic_rigor" in student_keys
    assert "inquiry_depth" in student_keys
    assert "major_fit_alignment" in student_keys
    assert "interview_explainability" in student_keys
    assert "diagnosis_confidence_gate" in {block.key for block in system_group.blocks}


def test_uncertainty_notes_stay_populated_for_weak_evidence() -> None:
    notes = report_service._build_uncertainty_notes(
        result=_result_payload(),
        document_structure=_document_structure(),
        evidence_items=[],
        evidence_bank=_evidence_bank(),
    )

    assert notes
    assert any("reference-only" in note for note in notes)
    assert any("검증 원칙" in note for note in notes)


def test_contradiction_gate_marks_system_group_blocked() -> None:
    score_groups = report_service._build_score_groups(
        result=_result_payload(),
        document_structure=_document_structure(contradiction_passed=False),
        evidence_items=[],
        evidence_bank=_evidence_bank(),
    )

    system_group = next(group for group in score_groups if group.group == "system_quality")
    assert system_group.gating_status == "blocked"
    contradiction_block = next(block for block in system_group.blocks if block.key == "contradiction_check")
    assert contradiction_block.score == 0


def test_schema_backward_compatibility_allows_old_payload_without_new_fields() -> None:
    legacy_payload = {
        "diagnosis_run_id": "run-1",
        "project_id": "project-1",
        "report_mode": "premium_10p",
        "template_id": "consultant_diagnosis_premium_10p",
        "title": "Legacy payload",
        "subtitle": "legacy",
        "student_target_context": "ctx",
        "generated_at": datetime.now(timezone.utc),
        "score_blocks": [
            {
                "key": "legacy",
                "label": "legacy",
                "score": 60,
                "band": "watch",
                "interpretation": "legacy interpretation",
            }
        ],
        "score_groups": [],
        "sections": [],
        "roadmap": [],
        "citations": [],
        "uncertainty_notes": [],
        "final_consultant_memo": "memo",
        "appendix_notes": [],
        "render_hints": {},
    }

    parsed = ConsultantDiagnosisReport.model_validate(legacy_payload)
    assert parsed.diagnosis_intelligence == {}
    assert parsed.score_blocks[0].evidence_summary is None
    assert parsed.score_blocks[0].missing_evidence is None
    assert parsed.score_blocks[0].next_best_action is None


def test_topic_recommendation_block_is_grounded_and_conservative() -> None:
    intelligence = report_service._build_diagnosis_intelligence(
        result=_result_payload(),
        document_structure=_document_structure(),
        evidence_bank=_evidence_bank(),
        evidence_items=[],
    )

    recommended = intelligence.get("recommended_report_directions")
    avoid = intelligence.get("avoid_report_directions")
    assert isinstance(recommended, list)
    assert isinstance(avoid, list)
    assert len(recommended) >= 3
    assert len(avoid) >= 2
    assert all("overclaim_guardrail" in item for item in recommended if isinstance(item, dict))
    assert any(
        ("합격" in str(item.get("overclaim_guardrail", "")) or "단정" in str(item.get("overclaim_guardrail", "")))
        for item in recommended
        if isinstance(item, dict)
    )


def test_design_contract_and_templates_keep_modes_and_ids_with_new_section_flow() -> None:
    compact_template = get_template("consultant_diagnosis_compact", render_format=RenderFormat.PDF)
    premium_template = get_template("consultant_diagnosis_premium_10p", render_format=RenderFormat.PDF)

    assert compact_template.id == "consultant_diagnosis_compact"
    assert premium_template.id == "consultant_diagnosis_premium_10p"
    assert "recommended_report_direction" in compact_template.section_schema
    assert "consulting_priority_brief" in compact_template.section_schema
    assert "admissions_positioning_snapshot" in premium_template.section_schema
    assert "consulting_priority_map" in premium_template.section_schema
    assert "student_evaluation_matrix" in premium_template.section_schema
    assert "student_record_upgrade_blueprint" in premium_template.section_schema
    assert "uncertainty_verification_note" in premium_template.section_schema

    premium_contract = get_diagnosis_report_design_contract(
        report_mode="premium_10p",
        template_id="consultant_diagnosis_premium_10p",
        template_section_schema=premium_template.section_schema,
    )
    compact_contract = get_diagnosis_report_design_contract(
        report_mode="compact",
        template_id="consultant_diagnosis_compact",
        template_section_schema=compact_template.section_schema,
    )

    assert "recommended_report_directions" in premium_contract["section_hierarchy"]["required_order"]
    assert "admissions_positioning_snapshot" in premium_contract["section_hierarchy"]["required_order"]
    assert "student_record_upgrade_blueprint" in premium_contract["section_hierarchy"]["required_order"]
    assert "citation_appendix" in premium_contract["section_hierarchy"]["required_order"]
    assert "uncertainty_verification_note" in compact_contract["section_hierarchy"]["required_order"]
    assert "consulting_priority_brief" in compact_contract["section_hierarchy"]["required_order"]
    assert "risk_analysis" in compact_contract["section_hierarchy"]["required_order"]


def test_section_semantics_map_covers_both_modes() -> None:
    premium = report_service._build_section_semantics(report_mode="premium_10p")
    compact = report_service._build_section_semantics(report_mode="compact")

    assert premium["system_quality_reliability"] == "verified"
    assert premium["consulting_priority_map"] == "action"
    assert premium["uncertainty_verification_note"] == "uncertainty"
    assert compact["consulting_priority_brief"] == "action"
    assert compact["recommended_report_direction"] == "action"
    assert compact["risk_analysis"] == "uncertainty"


def test_pdf_renderer_smoke_renders_both_modes(tmp_path) -> None:
    for mode, template_id in (
        ("compact", "consultant_diagnosis_compact"),
        ("premium_10p", "consultant_diagnosis_premium_10p"),
    ):
        template = get_template(template_id, render_format=RenderFormat.PDF)
        design_contract = get_diagnosis_report_design_contract(
            report_mode=mode,
            template_id=template_id,
            template_section_schema=template.section_schema,
        )
        sections = [
            {
                "id": section_id,
                "title": section_id,
                "subtitle": "test",
                "body_markdown": "- 테스트 본문",
                "evidence_items": [],
                "unsupported_claims": [],
                "additional_verification_needed": [],
            }
            for section_id in template.section_schema
        ]
        payload = {
            "title": "진단 리포트 테스트",
            "subtitle": "render smoke",
            "student_target_context": "학생: test",
            "sections": sections,
            "score_blocks": [],
            "score_groups": [],
            "roadmap": [],
            "citations": [],
            "uncertainty_notes": ["테스트 불확실성"],
            "appendix_notes": ["테스트 부록"],
            "render_hints": {
                "design_contract": design_contract,
                "analysis_confidence_score": 0.5,
                "one_line_verdict": "테스트 판정",
                "public_appendix_enabled": True,
                "public_citations_enabled": True,
            },
        }
        output_path = tmp_path / f"smoke-{mode}.pdf"
        render_consultant_diagnosis_pdf(
            report_payload=payload,
            output_path=output_path,
            report_mode=mode,
            template_id=template_id,
            include_appendix=True,
            include_citations=True,
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0


def test_report_generation_failure_keeps_diagnosis_payload_usable(monkeypatch) -> None:
    class _FakeDb:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, obj: object) -> None:
            self.added.append(obj)

        def commit(self) -> None:
            return None

        def refresh(self, _obj: object) -> None:
            return None

    async def _raise_build_failure(**kwargs):  # noqa: ANN003, ARG001
        raise RuntimeError("forced report build failure")

    payload_json = _result_payload().model_dump_json()
    run = SimpleNamespace(id="run-1", project_id="project-1", result_payload=payload_json)
    project = SimpleNamespace(id="project-1", title="테스트 프로젝트")
    db = _FakeDb()

    monkeypatch.setattr(
        report_service,
        "get_settings",
        lambda: SimpleNamespace(llm_provider="gemini", ollama_render_model=None, ollama_model="gemma4"),
    )
    monkeypatch.setattr(report_service, "get_storage_provider", lambda _settings: SimpleNamespace(exists=lambda _key: False))
    monkeypatch.setattr(report_service, "get_storage_provider_name", lambda _storage: "memory")
    monkeypatch.setattr(report_service, "resolve_consultant_report_template_id", lambda **kwargs: "template-compact")
    monkeypatch.setattr(report_service, "get_latest_report_artifact_for_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(report_service, "list_documents_for_project", lambda *args, **kwargs: [])
    monkeypatch.setattr(report_service, "build_consultant_report_payload", _raise_build_failure)

    artifact = asyncio.run(
        report_service.generate_consultant_report_artifact(
            db,
            run=run,
            project=project,
            report_mode="compact",
            template_id=None,
            include_appendix=False,
            include_citations=False,
            force_regenerate=True,
        )
    )

    assert artifact.status == "FAILED"
    assert run.result_payload == payload_json
    assert DiagnosisResultPayload.model_validate_json(run.result_payload).headline == "진단 헤드라인"
    metadata = json.loads(artifact.execution_metadata_json or "{}")
    assert metadata["fallback_used"] is True
    assert "forced report build failure" in artifact.error_message
