from __future__ import annotations

from unifoli_api.schemas.diagnosis import ConsultantDiagnosisSection, ConsultantRecordNetwork
from unifoli_api.services.diagnosis_report_quality_service import build_report_quality_gates


def test_report_quality_gates_are_reanalysis_sensitive() -> None:
    gates = build_report_quality_gates(
        report_mode="premium",
        mode_spec={"label": "Premium Report", "min_pages": 18, "max_pages": 24},
        evidence_bank=[
            {"anchor_id": "A1", "page": 1},
            {"anchor_id": "A2", "page": 1},
        ],
        subject_analyses=[],
        record_network=ConsultantRecordNetwork(central_theme="테마", nodes=[], edges=[]),
        research_topics=[],
        interview_questions=[],
        sections=[
            ConsultantDiagnosisSection(
                id="s1",
                title="섹션",
                body_markdown=(
                    "로봇 센서 오차 비교 활동의 한계를 설명해야 합니다. "
                    "로봇 센서 오차 비교 활동의 한계를 설명해야 합니다. "
                    "로봇 센서 오차 비교 활동의 한계를 설명해야 합니다."
                ),
            )
        ],
        reanalysis_required=True,
    )

    by_key = {gate.key: gate for gate in gates}

    assert by_key["page_count"].passed is True
    assert by_key["evidence"].passed is False
    assert by_key["topics"].passed is False
    assert by_key["interview"].passed is False
    assert by_key["repetition"].passed is False
