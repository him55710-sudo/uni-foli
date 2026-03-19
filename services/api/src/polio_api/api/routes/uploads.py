from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_db
from polio_api.schemas.upload_asset import UploadAssetRead
from polio_api.services.project_service import get_project
from polio_api.services.upload_service import list_uploads_for_project, store_upload

router = APIRouter()


@router.post(
    "/{project_id}/uploads",
    response_model=UploadAssetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_route(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadAssetRead:
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    upload = await store_upload(db, project_id=project_id, upload=file)
    return UploadAssetRead.model_validate(upload)


@router.get("/{project_id}/uploads", response_model=list[UploadAssetRead])
def list_uploads_route(project_id: str, db: Session = Depends(get_db)) -> list[UploadAssetRead]:
    return [UploadAssetRead.model_validate(item) for item in list_uploads_for_project(db, project_id)]
