from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from polio_api.core.database import SessionLocal
from polio_api.db.models.user import User

security = HTTPBearer()


@lru_cache(maxsize=1)
def get_firebase_auth_client():
    """Initializes the Firebase Admin SDK client once."""
    try:
        import firebase_admin
        from firebase_admin import auth
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "firebase-admin is not installed. "
                "Run setup-local again to install backend dependencies."
            ),
        ) from exc

    if not firebase_admin._apps:
        # Defaults to ADC or GOOGLE_APPLICATION_CREDENTIALS path
        firebase_admin.initialize_app()

    return auth


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> User:
    """
    Verify the Firebase bearer token and extract user information.
    Syncs the user to the local database if they do not exist.
    """
    from polio_api.core.config import get_settings
    settings = get_settings()

    if not credentials:
        if settings.app_env == "local":
            # Mock user for local development
            test_uid = "test-user-id"
            user = db.query(User).filter(User.firebase_uid == test_uid).first()
            if not user:
                user = User(
                    firebase_uid=test_uid, 
                    email="test@example.com", 
                    name="Test Admin"
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            return user
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    auth_client = get_firebase_auth_client()
    try:
        # verify_id_token includes validation of the issuer, expiry, and signature
        decoded_token = auth_client.verify_id_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email")
    name = decoded_token.get("name")

    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing uid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Lookup user by firebase_uid
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()

    # Automatic sync/signup if not found
    if not user:
        user = User(
            firebase_uid=firebase_uid, 
            email=email, 
            name=name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if user.email != email or user.name != name:
            user.email = email
            user.name = name
            db.commit()
            db.refresh(user)

    return user
