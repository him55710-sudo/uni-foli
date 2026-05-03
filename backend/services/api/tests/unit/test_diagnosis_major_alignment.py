from __future__ import annotations

from types import SimpleNamespace

from unifoli_api.services.diagnosis_scoring_service import build_diagnosis_scoring_sheet
from unifoli_api.services.diagnosis_report_service import (
    _build_major_direction_validation,
    _is_architecture_evidence_context,
)
from unifoli_api.services.student_record_feature_service import extract_student_record_features


def test_architecture_target_with_mechanical_computer_record_is_flagged_as_mismatch() -> None:
    student_record_text = """
    1학년 진로희망은 기계·전자공학 분야로, 전동화 기술과 배터리 열관리 자료를 조사하였다.
    컴퓨터 하드웨어 연구원 직업을 탐색하며 센서와 제어 회로의 작동 원리를 발표하였다.
    반도체 공정과 자동차 모빌리티 기술을 비교하고, 프로그래밍 활동에서 알고리즘을 구현하였다.
    3학년 희망 분야도 기계·컴퓨터 계열로 정리되어 있다.
    """
    document = SimpleNamespace(
        content_text=student_record_text,
        content_markdown="",
        parse_metadata={"parse_confidence": 0.9},
    )

    features = extract_student_record_features(
        documents=[document],
        full_text=student_record_text,
        target_major="건축학부",
        career_direction=None,
    )

    assert features.target_major_track == "architecture"
    assert features.dominant_major_track == "mechanical_computer"
    assert features.target_major_alignment_level == "mismatch"
    assert features.target_major_alignment_note is not None
    assert "기계·컴퓨터" in features.target_major_alignment_note


def test_major_mismatch_caps_major_fit_and_recommends_bridge_topics() -> None:
    student_record_text = """
    기계공학, 전자공학, 컴퓨터 하드웨어, 전동화 기술, 배터리 열관리, 반도체 공정,
    센서 제어와 프로그래밍 활동이 반복적으로 기록되어 있다.
    """
    document = SimpleNamespace(
        content_text=student_record_text,
        content_markdown="",
        parse_metadata={"parse_confidence": 0.9},
    )
    features = extract_student_record_features(
        documents=[document],
        full_text=student_record_text,
        target_major="건축학부",
        career_direction=None,
    )

    sheet = build_diagnosis_scoring_sheet(
        features=features,
        project_title="전공 적합성 검증",
        target_major="건축학부",
        target_university=None,
    )

    major_fit = next(axis for axis in sheet.admission_axes if axis.key == "cluster_suitability")

    assert major_fit.score <= 58
    assert any("스마트빌딩" in topic or "건축물 안전" in topic for topic in sheet.recommended_topics)
    assert any("기계·컴퓨터" in gap for gap in sheet.gap_candidates)


def test_architecture_report_mode_requires_architecture_evidence_not_only_target_text() -> None:
    evidence_bank = [
        {"quote": "컴퓨터 하드웨어 연구원 직업을 탐색하고 센서 제어 회로를 발표함."},
        {"quote": "전동화 기술과 반도체 공정에 대한 자료를 비교 분석함."},
    ]

    assert _is_architecture_evidence_context("목표 전공: 건축학부", evidence_bank) is False

    validation = _build_major_direction_validation(
        target_context="목표 전공: 건축학부",
        evidence_bank=evidence_bank,
    )

    assert validation["alignment"] == "mismatch"
    assert validation["dominant_record_track"] == "기계·컴퓨터"
    assert "전공 연결 근거가 부족" in validation["judgement"]
