import json

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


def append_project_discussion_log(db: Session, project: Project, prompt: str) -> Project:
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        return project

    try:
        existing = json.loads(project.discussion_log or "[]")
        discussion_log = existing if isinstance(existing, list) else []
    except json.JSONDecodeError:
        discussion_log = []

    discussion_log.append(normalized_prompt[:280])
    project.discussion_log = json.dumps(discussion_log[-6:], ensure_ascii=False)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_project_discussion_log(project: Project) -> list[str]:
    try:
        data = json.loads(project.discussion_log or "[]")
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    normalized_logs: list[str] = []
    for item in data[-3:]:
        if isinstance(item, str) and item.strip():
            normalized_logs.append(item.strip())
    return normalized_logs
