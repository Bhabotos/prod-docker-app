"""Assembles the BMI routers with uniform protection.

Every route except POST /auth/login and POST /auth/logout requires a valid
session cookie; every route answers 503 when the feature is not configured;
every response is marked no-store; state-changing requests get the Origin check.
tests/bmi/test_route_protection.py fails if a new route slips past this.
"""
from fastapi import APIRouter, Depends

from bmi_dashboard.deps import check_origin, no_store, require_auth, require_enabled
from bmi_dashboard.routers import auth, goals, health, profile

router = APIRouter(dependencies=[Depends(require_enabled), Depends(no_store)])
router.include_router(auth.router)  # login/logout are open by design; /auth/me checks the cookie itself
for _r in (profile.router, health.router, goals.router):
    router.include_router(_r, dependencies=[Depends(require_auth), Depends(check_origin)])
