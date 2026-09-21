from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bmi_dashboard import repository as repo
from bmi_dashboard import schemas as S
from bmi_dashboard.deps import get_session, require_profile
from bmi_dashboard.models import Profile
from bmi_dashboard.services import health_service as svc

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=S.GoalOut)
def read_goal(profile: Profile = Depends(require_profile), session: Session = Depends(get_session)):
    goal = repo.get_goal(session, profile)
    if goal is None:
        raise HTTPException(status_code=404, detail="No goal set yet.")
    return svc.build_goal(goal, profile, repo.latest_entry(session, profile))


@router.post("", response_model=S.GoalOut, status_code=201)
def create_goal(body: S.GoalCreate, profile: Profile = Depends(require_profile), session: Session = Depends(get_session)):
    if repo.get_goal(session, profile) is not None:
        raise HTTPException(status_code=409, detail="A goal already exists. Use PUT /goals to change it.")
    latest = repo.latest_entry(session, profile)
    start = body.starting_weight_kg if body.starting_weight_kg is not None else (latest.weight_kg if latest else None)
    if start is None:
        raise HTTPException(status_code=422, detail="Record a weight first, or provide starting_weight_kg.")
    goal = repo.create_goal(
        session, profile, target_weight_kg=body.target_weight_kg, starting_weight_kg=start,
        started_on=datetime.now(timezone.utc).date(), daily_calorie_target=body.daily_calorie_target,
    )
    session.commit()
    return svc.build_goal(goal, profile, latest)


@router.put("", response_model=S.GoalOut)
def update_goal(body: S.GoalUpdate, profile: Profile = Depends(require_profile), session: Session = Depends(get_session)):
    goal = repo.get_goal(session, profile)
    if goal is None:
        raise HTTPException(status_code=404, detail="No goal set yet.")
    latest = repo.latest_entry(session, profile)
    values = {"target_weight_kg": body.target_weight_kg, "daily_calorie_target": body.daily_calorie_target}
    if body.restart_progress:
        if latest is None:
            raise HTTPException(status_code=422, detail="Record a weight before restarting progress.")
        values.update(starting_weight_kg=latest.weight_kg, started_on=datetime.now(timezone.utc).date())
    repo.update_goal(session, goal, **values)
    session.commit()
    return svc.build_goal(goal, profile, latest)
