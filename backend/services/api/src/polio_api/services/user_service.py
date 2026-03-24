from sqlalchemy.orm import Session

from polio_api.db.models.user import User


def get_user_profile(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def update_user_profile(
    db: Session,
    user: User,
    *,
    grade: str | None,
    track: str | None,
    career: str | None,
) -> User:
    if grade is not None:
        user.grade = grade.strip()
    if track is not None:
        user.track = track.strip()
    if career is not None:
        user.career = career.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_goals(
    db: Session,
    user: User,
    *,
    target_university: str | None,
    target_major: str | None,
    admission_type: str | None,
) -> User:
    if target_university is not None:
        user.target_university = target_university.strip()
    if target_major is not None:
        user.target_major = target_major.strip()
    if admission_type is not None:
        user.admission_type = admission_type.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
