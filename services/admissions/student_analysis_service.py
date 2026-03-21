from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.audit import PolicyFlag
from db.models.student import StudentAnalysisRun, StudentArtifact, StudentFile
from domain.enums import PolicyFlagStatus, ResponseTraceKind, StudentAnalysisRunStatus
from services.admissions.provenance_service import provenance_service
from services.admissions.safety_service import safety_service


DIMENSION_KEYWORDS = {
    "academic_competence": ("수업", "교과", "탐구", "실험", "분석", "세특"),
    "self_directed_growth": ("주도", "기획", "설계", "수정", "보완"),
    "career_exploration": ("진로", "전공", "학과", "직무"),
    "major_fit": ("전공", "심화", "연계", "확장"),
    "community_contribution": ("협업", "공동체", "조율", "캠페인", "봉사"),
}


class StudentAnalysisService:
    def process_run(self, session: Session, run: StudentAnalysisRun) -> StudentAnalysisRun:
        run.status = StudentAnalysisRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        session.flush()

        if run.primary_student_file_id is None:
            run.status = StudentAnalysisRunStatus.FAILED
            run.analysis_notes = "Primary student file is required."
            session.flush()
            return run

        student_file = session.get(StudentFile, run.primary_student_file_id)
        if student_file is None or student_file.deleted_at is not None:
            run.status = StudentAnalysisRunStatus.FAILED
            run.analysis_notes = "Student file not found."
            session.flush()
            return run

        artifacts = list(
            session.scalars(
                select(StudentArtifact)
                .where(StudentArtifact.student_file_id == student_file.id)
                .where(StudentArtifact.deleted_at.is_(None))
                .order_by(StudentArtifact.artifact_index.asc())
            )
        )

        dimension_matches: dict[str, list[dict[str, object]]] = {key: [] for key in DIMENSION_KEYWORDS}
        weak_evidence_zones: list[dict[str, object]] = []
        safety_flags = []

        for artifact in artifacts:
            text = artifact.masked_text or artifact.cleaned_text
            reasons = safety_service.weak_evidence_reasons(text)
            if reasons:
                weak_evidence_zones.append(
                    {
                        "student_artifact_id": str(artifact.id),
                        "reasons": reasons,
                        "snippet": text[:160],
                    }
                )
                artifact.evidence_quality_score = max(0.0, 1.0 - len(reasons) * 0.25)
            else:
                artifact.evidence_quality_score = 0.9

            for dimension_code, keywords in DIMENSION_KEYWORDS.items():
                if any(keyword in text for keyword in keywords):
                    dimension_matches[dimension_code].append(
                        {
                            "student_artifact_id": str(artifact.id),
                            "page_start": artifact.page_start,
                            "snippet": text[:180],
                        }
                    )

            safety_flags.extend(safety_service.evaluate_query_text(text))

        run.output_summary = {
            "dimension_matches": dimension_matches,
            "weak_evidence_zones": weak_evidence_zones,
            "artifact_count": len(artifacts),
        }
        run.analysis_notes = "Analysis scaffold completed with heuristic dimension mapping."
        run.finished_at = datetime.now(UTC)
        run.status = StudentAnalysisRunStatus.SUCCEEDED if not safety_flags else StudentAnalysisRunStatus.REVIEW_REQUIRED

        trace = provenance_service.create_response_trace(
            session,
            response_kind=ResponseTraceKind.ANALYSIS,
            tenant_id=run.tenant_id,
            owner_key=run.owner_key,
            route_name="analysis.worker.process_run",
            query_text=f"student_analysis_run:{run.id}",
            prompt_template_key=run.prompt_template_key,
            model_name=run.model_name,
            retention_expires_at=run.retention_expires_at,
            retrieval_trace={"student_file_id": str(student_file.id)},
            response_payload=run.output_summary,
        )

        for artifact in artifacts[:10]:
            provenance_service.add_citation(
                session,
                tenant_id=run.tenant_id,
                response_trace_id=trace.id,
                analysis_run_id=run.id,
                student_artifact_id=artifact.id,
                citation_kind="student_artifact",
                label=artifact.title or artifact.section_label or f"Artifact {artifact.artifact_index}",
                page_number=artifact.page_start,
                locator_json={"artifact_index": artifact.artifact_index},
                quoted_text=(artifact.masked_text or artifact.cleaned_text)[:180],
            )

        for flag in safety_flags:
            session.add(
                PolicyFlag(
                    tenant_id=run.tenant_id,
                    student_analysis_run_id=run.id,
                    target_kind="student_analysis_run",
                    target_id=run.id,
                    flag_code=flag.flag_code,
                    severity_score=flag.severity_score,
                    status=PolicyFlagStatus.OPEN,
                    message=flag.message,
                    evidence_json=flag.evidence_json,
                )
            )

        session.flush()
        session.refresh(run)
        return run


student_analysis_service = StudentAnalysisService()
