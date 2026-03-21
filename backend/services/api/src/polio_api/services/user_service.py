from sqlalchemy.orm import Session

from polio_api.db.models.user import User


def get_user_profile(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def update_user_targets(
    db: Session,
    user: User,
    *,
    target_university: str,
    target_major: str,
) -> User:
    user.target_university = target_university.strip()
    user.target_major = target_major.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
