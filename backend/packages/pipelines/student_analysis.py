from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StudentAnalysisStage:
    name: str
    runner_kind: str
    description: str


STUDENT_ANALYSIS_STAGES = [
    StudentAnalysisStage("ingest_uploaded_file", "sync_api", "Store uploaded student file and create a traceable file object."),
    StudentAnalysisStage("parse_student_artifacts", "async_worker", "Parse document sections and preserve evidence boundaries."),
    StudentAnalysisStage("classify_artifact_type", "async_worker", "Normalize into school-record, inquiry-report, or related artifact types."),
    StudentAnalysisStage("map_to_dimensions", "async_worker", "Map authentic evidence to evaluation dimensions."),
    StudentAnalysisStage("detect_weak_evidence", "async_worker", "Flag vague, repetitive, unsupported, or low-specificity segments."),
    StudentAnalysisStage("prepare_analysis_response", "async_worker", "Package explainable outputs with citations."),
]
