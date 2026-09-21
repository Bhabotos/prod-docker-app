from fastapi import APIRouter, Depends, HTTPException, Request, Response

from bmi_dashboard.config import bmi_settings
from bmi_dashboard.deps import COOKIE_NAME, Principal, check_origin, get_limiter, require_auth
from bmi_dashboard.repository import SUBJECT
from bmi_dashboard.schemas import LoginIn
from bmi_dashboard.security import RateLimiter, create_session_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    # nginx sets X-Real-IP; the API container has no published port, so this header is trustworthy.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def _cookie_path(request: Request) -> str:
    return request.scope.get("root_path") or "/"  # "/api" behind nginx: cookie is not sent to static pages


@router.post("/login", dependencies=[Depends(check_origin)])
def login(body: LoginIn, request: Request, response: Response, limiter: RateLimiter = Depends(get_limiter)) -> dict:
    ip = _client_ip(request)
    wait = limiter.retry_after(ip)
    if wait:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.", headers={"Retry-After": str(wait)})
    if not verify_password(body.password, bmi_settings.dashboard_password_hash):
        limiter.register_failure(ip)
        raise HTTPException(status_code=401, detail="Incorrect password.")
    limiter.reset(ip)
    ttl = bmi_settings.session_ttl_hours * 3600
    response.set_cookie(
        COOKIE_NAME, create_session_token(bmi_settings.session_secret, SUBJECT, ttl), max_age=ttl,
        httponly=True, secure=bmi_settings.cookie_secure, samesite="strict", path=_cookie_path(request),
    )
    return {"authenticated": True}


@router.post("/logout", dependencies=[Depends(check_origin)])
def logout(request: Request, response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path=_cookie_path(request))
    return {"authenticated": False}


@router.get("/me")
def me(_: Principal = Depends(require_auth)) -> dict:
    return {"authenticated": True}
