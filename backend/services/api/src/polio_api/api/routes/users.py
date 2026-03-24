from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.user import User
from polio_api.schemas.user import UserProfileRead, UserProfileUpdate, UserGoalsUpdate
from polio_api.services.user_service import update_user_profile, update_user_goals

router = APIRouter()


@router.get("/me", response_model=UserProfileRead)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserProfileRead:
    return UserProfileRead.model_validate(current_user)


@router.post("/onboarding/profile", response_model=UserProfileRead)
def onboarding_my_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileRead:
    user = update_user_profile(
        db,
        current_user,
        grade=payload.grade,
        track=payload.track,
        career=payload.career,
    )
    return UserProfileRead.model_validate(user)


@router.post("/onboarding/goals", response_model=UserProfileRead)
def onboarding_my_goals(
    payload: UserGoalsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileRead:
    user = update_user_goals(
        db,
        current_user,
        target_university=payload.target_university,
        target_major=payload.target_major,
        admission_type=payload.admission_type,
    )
    return UserProfileRead.model_validate(user)
