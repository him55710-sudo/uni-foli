from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.user import User
from polio_api.schemas.blueprint import CurrentBlueprintRead
from polio_api.services.blueprint_service import build_current_blueprint_read, get_current_blueprint
from polio_api.services.project_service import get_project

router = APIRouter()


@router.get("/current", response_model=CurrentBlueprintRead)
def get_current_blueprint_route(
    project_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CurrentBlueprintRead:
    if project_id and get_project(db, project_id, owner_user_id=current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    blueprint = get_current_blueprint(db, project_id=project_id, owner_user_id=current_user.id)
    if blueprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No action blueprint is available yet. Run diagnosis first.",
        )
    return build_current_blueprint_read(blueprint)
