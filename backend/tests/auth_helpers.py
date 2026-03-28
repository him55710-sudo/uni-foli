from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from polio_api.api.deps import LOCAL_DEV_JWT_SECRET
from polio_api.core.config import get_settings


def auth_headers(subject: str) -> dict[str, str]:
    settings = get_settings()
    if not settings.auth_jwt_secret:
        settings.auth_jwt_secret = LOCAL_DEV_JWT_SECRET

    token = jwt.encode(
        {
            "sub": subject,
            "email": f"{subject}@example.com",
            "name": subject.replace(":", " ").title(),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}
