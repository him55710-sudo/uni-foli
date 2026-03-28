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
    interest_universities: list[str] | None = None,
) -> User:
    if grade is not None:
        user.grade = grade.strip()
    if track is not None:
        user.track = track.strip()
    if career is not None:
        user.career = career.strip()
    if interest_universities is not None:
        user.interest_universities = _normalize_interest_universities(interest_universities, user.target_university)
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
    interest_universities: list[str] | None = None,
) -> User:
    if target_university is not None:
        user.target_university = target_university.strip()
    if target_major is not None:
        user.target_major = target_major.strip()
    if admission_type is not None:
        user.admission_type = admission_type.strip()
    if interest_universities is not None:
        user.interest_universities = _normalize_interest_universities(interest_universities, user.target_university)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _normalize_interest_universities(names: list[str], target_university: str | None) -> list[str]:
    # Deduplicate, trim, remove empty, limit to 20, exclude target_university
    seen = set()
    result = []
    target_norm = target_university.strip() if target_university else None
    
    for name in names:
        if not name:
            continue
        trimmed = name.strip()
        if not trimmed:
            continue
        if trimmed == target_norm:
            continue
        if trimmed not in seen:
            seen.add(trimmed)
            result.append(trimmed)
            if len(result) >= 20:
                break
    return result
