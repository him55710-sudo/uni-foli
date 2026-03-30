from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import uuid
import logging

from polio_api.api.deps import get_db, get_current_user
from polio_api.core.rate_limit import rate_limit
from polio_api.db.models.user import User
from polio_api.schemas.project import ProjectCreate, ProjectRead
from polio_api.services.blueprint_service import create_blueprint_from_project_diagnosis
from polio_api.services.document_service import list_documents_for_project
from polio_api.services.project_service import create_project, get_project, list_project_discussion_log, list_projects
from pydantic import BaseModel, Field

# Try to import from the render service
try:
    from polio_render.formats.hwpx_renderer import HwpxRenderer
    from polio_render.models import RenderBuildContext
    from polio_domain.enums import RenderFormat
except ImportError:
    # Path setup for local dev
    import sys
    from polio_shared.paths import find_project_root

    root = find_project_root()
    sys.path.append(str(root / "services" / "render" / "src"))
    sys.path.append(str(root / "packages" / "domain" / "src"))

    from polio_render.formats.hwpx_renderer import HwpxRenderer
    from polio_render.models import RenderBuildContext
    from polio_domain.enums import RenderFormat

router = APIRouter()
logger = logging.getLogger("polio.api.projects")


class DiagnosisOverall(BaseModel):
    score: int
    summary: str


class DiagnosisSubject(BaseModel):
    name: str
    status: str
    feedback: str


class DiagnosisPrescription(BaseModel):
    message: str
    recommendedTopic: str


class ProjectDiagnosisResponse(BaseModel):
    overall: DiagnosisOverall
    subjects: list[DiagnosisSubject]
    prescription: DiagnosisPrescription


def _build_grounded_diagnosis(
    *,
    project_title: str,
    target_major: str | None,
    document_count: int,
    total_words: int,
    combined_text: str,
) -> ProjectDiagnosisResponse:
    major_label = target_major or "the selected major"
    lowered = combined_text.lower()

    has_measurement = any(token in lowered for token in ["measure", "experiment", "data", "analysis", "survey"])
    has_comparison = any(token in lowered for token in ["compare", "difference", "before", "after", "trend"])
    has_reflection = any(token in lowered for token in ["reflect", "limit", "improve", "lesson", "feedback"])

    evidence_score = 40
    if document_count >= 1:
        evidence_score += 10
    if total_words >= 150:
        evidence_score += 10
    if has_measurement:
        evidence_score += 10
    if has_comparison:
        evidence_score += 10
    if has_reflection:
        evidence_score += 10
    evidence_score = min(evidence_score, 90)

    subjects = [
        DiagnosisSubject(
            name="Recorded evidence",
            status="safe" if document_count >= 1 and total_words >= 120 else "warning",
            feedback=(
                "The uploaded record contains enough grounded text to continue to workshop drafting."
                if document_count >= 1 and total_words >= 120
                else "The uploaded record is thin. Add more real evidence before expanding claims."
            ),
        ),
        DiagnosisSubject(
            name="Inquiry trace",
            status="safe" if has_measurement or has_comparison else "warning",
            feedback=(
                "The document shows concrete inquiry actions such as measuring, comparing, or analyzing."
                if has_measurement or has_comparison
                else "The document does not yet show a clear inquiry process. Keep the next activity evidence-focused."
            ),
        ),
        DiagnosisSubject(
            name="Reflection quality",
            status="safe" if has_reflection else "warning",
            feedback=(
                "The record includes reflection on limits or improvements, which is safer for later drafting."
                if has_reflection
                else "Reflection is not obvious in the current record. Add method limits and next-step reflections."
            ),
        ),
    ]

    summary = (
        f"Based only on {document_count} uploaded record(s) for {project_title}, the current evidence is "
        f"{'grounded enough to continue' if evidence_score >= 70 else 'still incomplete'} for {major_label}. "
        f"Use the next step to deepen real inquiry evidence rather than expanding claims."
    )

    recommendation_focus = (
        f"{major_label} inquiry that extends the uploaded evidence with one follow-up comparison, one explicit method limit, "
        "and one concrete reflection."
    )

    return ProjectDiagnosisResponse(
        overall=DiagnosisOverall(score=evidence_score, summary=summary),
        subjects=subjects,
        prescription=DiagnosisPrescription(
            message="Stay grounded in uploaded evidence and improve the next activity with clearer inquiry traces.",
            recommendedTopic=recommendation_focus,
        ),
    )

@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project_route(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    project = create_project(db, payload, owner_user_id=current_user.id)
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
def list_projects_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProjectRead]:
    return [ProjectRead.model_validate(item) for item in list_projects(db, owner_user_id=current_user.id)]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project_route(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return ProjectRead.model_validate(project)


@router.post("/{project_id}/diagnose", response_model=ProjectDiagnosisResponse)
def diagnose_project_route(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDiagnosisResponse:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    documents = list_documents_for_project(db, project_id)
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload and parse a real document before running diagnosis.",
        )

    text_blocks = [
        (document.content_text or document.content_markdown or "").strip()
        for document in documents
        if document.content_text or document.content_markdown
    ]
    combined_text = "\n\n".join(block for block in text_blocks if block).strip()
    if not combined_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parsed document content is empty. Re-run parsing before diagnosis.",
        )

    total_words = sum(document.word_count for document in documents)
    diagnosis_response = _build_grounded_diagnosis(
        project_title=project.title,
        target_major=project.target_major or getattr(current_user, "target_major", None),
        document_count=len(documents),
        total_words=total_words,
        combined_text=combined_text,
    )
    strengths = [subject.feedback for subject in diagnosis_response.subjects if subject.status == "safe"]
    gaps = [subject.feedback for subject in diagnosis_response.subjects if subject.status != "safe"]

    create_blueprint_from_project_diagnosis(
        db,
        project=project,
        headline=diagnosis_response.overall.summary,
        strengths=strengths,
        gaps=gaps,
        risk_level="safe" if diagnosis_response.overall.score >= 75 else "warning" if diagnosis_response.overall.score >= 55 else "danger",
        recommended_focus=diagnosis_response.prescription.recommendedTopic,
    )
    return diagnosis_response

class UserStats(BaseModel):
    report_count: int
    level: str
    completion_rate: int

@router.get("/user/stats", response_model=UserStats)
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> UserStats:
    projects = list_projects(db, owner_user_id=current_user.id)
    report_count = len(projects)
    level_map = ["탐구의 시작 🐣", "성장하는 잎새 🌱", "열매 맺는 나무 🌳"]
    level_index = min(report_count, len(level_map) - 1)
    
    return UserStats(
        report_count=report_count,
        level=level_map[level_index],
        completion_rate=min(100, report_count * 33)
    )

class ExportRequest(BaseModel):
    content_markdown: str = Field(min_length=1, max_length=100000)

@router.post("/{project_id}/export")
def export_project_hwpx(
    project_id: str,
    payload: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="project_export", limit=10, window_seconds=300, guest_limit=2)),
):
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    renderer = HwpxRenderer()
    context = RenderBuildContext(
        project_id=project_id,
        project_title=project.title,
        draft_id=str(uuid.uuid4()),
        draft_title=f"{project.target_major or 'General'} Research Report",
        render_format=RenderFormat.HWPX,
        content_markdown=payload.content_markdown,
        requested_by=current_user.name,
        job_id=str(uuid.uuid4()),
        authenticity_log_lines=list_project_discussion_log(project),
    )

    try:
        artifact = renderer.render(context)
        return FileResponse(
            path=artifact.absolute_path,
            filename=f"Research_Report_{project_id}.hwpx",
            media_type="application/vnd.hancom.hwpx"
        )
    except Exception as exc:
        logger.exception("Project export failed: %s", project_id)
        raise HTTPException(
            status_code=500,
            detail="Export failed. Review the draft content and retry.",
        ) from exc
