from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status


_RATE_LIMIT_BUCKETS: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = Lock()


def rate_limit(
    *, 
    bucket: str, 
    limit: int, 
    window_seconds: int,
    guest_limit: int | None = None,
    guest_window_seconds: int | None = None
):
    def dependency(request: Request) -> None:
        actual_limit = limit
        actual_window = window_seconds
        
        # Check if user is a guest (anonymous in Firebase)
        is_guest = False
        claims = getattr(request.state, "auth_claims", {})
        if claims and claims.get("firebase", {}).get("sign_in_provider") == "anonymous":
            is_guest = True
        elif not getattr(request.state, "current_user_id", None):
            # Not authenticated at all, treat as guest for rate limiting
            is_guest = True
            
        if is_guest and guest_limit is not None:
            actual_limit = guest_limit
            actual_window = guest_window_seconds if guest_window_seconds is not None else window_seconds

        _enforce_rate_limit(
            request=request,
            bucket=bucket,
            limit=actual_limit,
            window_seconds=actual_window,
        )

    return dependency


def _enforce_rate_limit(*, request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    now = monotonic()
    actor_key = _resolve_actor_key(request)
    bucket_key = (bucket, actor_key)

    with _RATE_LIMIT_LOCK:
        timestamps = _RATE_LIMIT_BUCKETS[bucket_key]
        while timestamps and now - timestamps[0] >= window_seconds:
            timestamps.popleft()

        if len(timestamps) >= limit:
            retry_after = max(1, int(window_seconds - (now - timestamps[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please retry later.",
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)


def _resolve_actor_key(request: Request) -> str:
    user_id = getattr(request.state, "current_user_id", None)
    if user_id:
        return f"user:{user_id}"
        
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for.strip():
        return forwarded_for.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
