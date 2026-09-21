from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bmi_dashboard import repository as repo
from bmi_dashboard import schemas as S
from bmi_dashboard.deps import get_session, require_profile
from bmi_dashboard.models import Profile

from datetime import datetime, timezone

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=S.ProfileOut)
def read_profile(profile: Profile = Depends(require_profile)):
    return profile


@router.post("", response_model=S.ProfileOut, status_code=201)
def create_profile(body: S.ProfileCreate, session: Session = Depends(get_session)):
    if repo.get_profile(session) is not None:
        raise HTTPException(status_code=409, detail="A profile already exists. Use PUT /profile to change it.")
    profile = repo.create_profile(
        session, age_years=body.age_years, sex=body.sex, height_cm=body.height_cm, activity_level=body.activity_level
    )
    recorded_on = body.recorded_on or datetime.now(timezone.utc).date()
    repo.upsert_weight(session, profile, recorded_on=recorded_on, weight_kg=body.weight_kg, note=None)
    session.commit()
    return profile


@router.put("", response_model=S.ProfileOut)
def update_profile(body: S.ProfileUpdate, profile: Profile = Depends(require_profile), session: Session = Depends(get_session)):
    repo.update_profile(
        session, profile, age_years=body.age_years, sex=body.sex, height_cm=body.height_cm, activity_level=body.activity_level
    )
    session.commit()
    return profile
