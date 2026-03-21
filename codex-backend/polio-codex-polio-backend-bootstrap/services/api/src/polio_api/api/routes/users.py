from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.user import User
from polio_api.schemas.user import UserProfileRead, UserTargetUpdate
from polio_api.services.user_service import update_user_targets

router = APIRouter()


@router.get("/me", response_model=UserProfileRead)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserProfileRead:
    return UserProfileRead.model_validate(current_user)


@router.patch("/me/targets", response_model=UserProfileRead)
def update_my_targets(
    payload: UserTargetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileRead:
    user = update_user_targets(
        db,
        current_user,
        target_university=payload.target_university,
        target_major=payload.target_major,
    )
    return UserProfileRead.model_validate(user)
