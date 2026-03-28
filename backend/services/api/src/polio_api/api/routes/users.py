from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.user import User
from polio_api.schemas.user import UserProfileRead, UserProfileUpdate, UserGoalsUpdate
from polio_api.services.user_service import update_user_profile, update_user_goals

router = APIRouter()


@router.get("/me", response_model=UserProfileRead)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserProfileRead:
    return UserProfileRead.model_validate(current_user)


@router.patch("/me/targets", response_model=UserProfileRead)
def update_my_targets(
    payload: UserGoalsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileRead:
    # Trace save attempt
    with open("backend_trace.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] update_my_targets for user {current_user.id}\nPayload: {payload.model_dump()}\n")
    
    try:
        user = update_user_goals(
            db,
            current_user,
            target_university=payload.target_university,
            target_major=payload.target_major,
            admission_type=payload.admission_type,
            interest_universities=payload.interest_universities,
        )
        with open("backend_trace.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] SUCCESS! Saved: {user.target_university}, {user.target_major}\n\n")
        return UserProfileRead.model_validate(user)
    except Exception as e:
        import traceback
        with open("backend_trace.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] ERROR in update_my_targets:\n")
            traceback.print_exc(file=f)
            f.write("\n")
        raise


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
        interest_universities=payload.interest_universities,
    )
    return UserProfileRead.model_validate(user)


@router.post("/onboarding/goals", response_model=UserProfileRead)
def onboarding_my_goals(
    payload: UserGoalsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileRead:
    with open("backend_trace.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] onboarding_my_goals for user {current_user.id}\nPayload: {payload.model_dump()}\n")
    
    try:
        user = update_user_goals(
            db,
            current_user,
            target_university=payload.target_university,
            target_major=payload.target_major,
            admission_type=payload.admission_type,
            interest_universities=payload.interest_universities,
        )
        with open("backend_trace.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] SUCCESS! onboarding Saved: {user.target_university}, {user.target_major}\n\n")
        return UserProfileRead.model_validate(user)
    except Exception as e:
        import traceback
        with open("backend_trace.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] ERROR in onboarding_my_goals:\n")
            traceback.print_exc(file=f)
            f.write("\n")
        raise
