from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import firebase_admin
from firebase_admin import auth

from polio_api.core.database import SessionLocal

security = HTTPBearer()

def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify the Firebase bearer token and extract user information.
    """
    token = credentials.credentials
    try:
        # Assuming firebase_admin.initialize_app() is called elsewhere (e.g., main.py)
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
