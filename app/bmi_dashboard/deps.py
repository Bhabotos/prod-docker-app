"""FastAPI dependencies: feature flag, authentication, CSRF origin check, headers."""
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

import redis_client as _redis_module
from bmi_dashboard import db
from bmi_dashboard.config import bmi_settings
from bmi_dashboard.models import Profile
from bmi_dashboard.repository import SUBJECT, get_profile
from bmi_dashboard.security import RateLimiter, verify_session_token

COOKIE_NAME = "bmi_session"

# Resolve the Redis client at call time (not import time) so tests can swap it.
_limiter = RateLimiter(lambda: _redis_module.redis_client, bmi_settings.login_max_attempts, bmi_settings.login_window_seconds)


def get_limiter() -> RateLimiter:
    return _limiter


@dataclass(frozen=True)
class Principal:
    subject: str


def require_enabled() -> None:
    if not bmi_settings.enabled:
        raise HTTPException(status_code=503, detail="The BMI dashboard is not configured on this server.")


def no_store(response: Response) -> None:
    """Personal data must never be cached by browsers or proxies."""
    response.headers["Cache-Control"] = "no-store"


def check_origin(request: Request) -> None:
    """CSRF defence in depth for state-changing requests (SameSite=Strict is the main one).

    A browser always sends Origin on cross-site POST/PUT/DELETE; if present its
    host must be the host we were addressed as.
    """
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if origin is None:
        return
    host = (request.headers.get("host") or "").split(":")[0]
    if urlparse(origin).hostname != host:
        raise HTTPException(status_code=403, detail="Cross-origin request rejected.")


def require_auth(request: Request) -> Principal:
    token = request.cookies.get(COOKIE_NAME)
    subject = verify_session_token(bmi_settings.session_secret, token) if token else None
    if subject != SUBJECT:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return Principal(subject)


def get_session() -> Session:  # thin re-export so routers depend on one place
    yield from db.get_session()


def require_profile(session: Session = Depends(get_session)) -> Profile:
    profile = get_profile(session)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not set up yet.")
    return profile
