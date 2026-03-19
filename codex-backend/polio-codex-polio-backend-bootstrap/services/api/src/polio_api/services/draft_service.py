from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.db.models.draft import Draft
from polio_api.schemas.draft import DraftCreate


def create_draft(db: Session, project_id: str, payload: DraftCreate) -> Draft:
    draft = Draft(
        project_id=project_id,
        source_document_id=payload.source_document_id,
        title=payload.title,
        content_markdown=payload.content_markdown,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def list_drafts_for_project(db: Session, project_id: str) -> list[Draft]:
    stmt = select(Draft).where(Draft.project_id == project_id).order_by(Draft.updated_at.desc())
    return list(db.scalars(stmt))


def get_draft(db: Session, draft_id: str) -> Draft | None:
    return db.get(Draft, draft_id)
