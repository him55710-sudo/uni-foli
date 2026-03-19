from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_db, get_current_user
from polio_api.schemas.project import ProjectCreate, ProjectRead
from polio_api.services.project_service import create_project, get_project, list_projects
from pydantic import BaseModel

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
    current_user: dict = Depends(get_current_user)
) -> UserStats:
    # Use real count of projects/drafts in the future
    projects = list_projects(db)
    report_count = len(projects)
    
    # Simple leveling logic based on reports count
    level_map = ["탐구의 시작 🐣", "성장하는 잎새 🌱", "열매 맺는 나무 🌳"]
    level_index = min(report_count, len(level_map) - 1)
    
    return UserStats(
        report_count=report_count,
        level=level_map[level_index],
        completion_rate=min(100, report_count * 33)
    )
