from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Any
import uuid

from polio_api.api.deps import get_db, get_current_user
from polio_api.schemas.project import ProjectCreate, ProjectRead
from polio_api.services.project_service import create_project, get_project, list_project_discussion_log, list_projects
from pydantic import BaseModel

# Try to import from the render service
try:
    from polio_render.formats.hwpx_renderer import HwpxRenderer
    from polio_render.models import RenderBuildContext
    from polio_domain.enums import RenderFormat
except ImportError:
    # Path setup for local dev
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[5] # Adjusted path
    sys.path.append(str(root / "services" / "render" / "src"))
    sys.path.append(str(root / "shared" / "domain" / "src")) # For Enums
    
    from polio_render.formats.hwpx_renderer import HwpxRenderer
    from polio_render.models import RenderBuildContext
    from polio_domain.enums import RenderFormat

router = APIRouter()

@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project_route(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    project = create_project(db, payload)
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
def list_projects_route(db: Session = Depends(get_db)) -> list[ProjectRead]:
    return [ProjectRead.model_validate(item) for item in list_projects(db)]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project_route(project_id: str, db: Session = Depends(get_db)) -> ProjectRead:
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return ProjectRead.model_validate(project)

class UserStats(BaseModel):
    report_count: int
    level: str
    completion_rate: int

@router.get("/user/stats", response_model=UserStats)
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
) -> UserStats:
    projects = list_projects(db)
    report_count = len(projects)
    level_map = ["탐구의 시작 🐣", "성장하는 잎새 🌱", "열매 맺는 나무 🌳"]
    level_index = min(report_count, len(level_map) - 1)
    
    return UserStats(
        report_count=report_count,
        level=level_map[level_index],
        completion_rate=min(100, report_count * 33)
    )

class ExportRequest(BaseModel):
    content_markdown: str

@router.post("/{project_id}/export")
def export_project_hwpx(
    project_id: str,
    payload: ExportRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    project = get_project(db, project_id)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
