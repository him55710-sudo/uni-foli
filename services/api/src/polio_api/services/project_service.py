from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.db.models.project import Project
from polio_api.schemas.project import ProjectCreate


def create_project(db: Session, payload: ProjectCreate) -> Project:
    project = Project(
        title=payload.title,
        description=payload.description,
        target_university=payload.target_university,
        target_major=payload.target_major,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


def get_project(db: Session, project_id: str) -> Project | None:
    return db.get(Project, project_id)
