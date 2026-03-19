from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import firebase_admin
from firebase_admin import auth

from polio_api.core.database import SessionLocal
from polio_api.db.models.user import User

security = HTTPBearer()

def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Verify the Firebase bearer token and extract user information.
    Syncs the user to the local database if they do not exist.
    """
    token = credentials.credentials
    try:
        # Assuming firebase_admin.initialize_app() is called elsewhere
        decoded_token = auth.verify_id_token(token)
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
        
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    
    if not user:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
    return user

