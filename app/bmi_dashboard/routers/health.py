from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from bmi_dashboard import repository as repo
from bmi_dashboard import schemas as S
from bmi_dashboard.deps import get_session, require_profile
from bmi_dashboard.models import Profile
from bmi_dashboard.services import health_service as svc

# NOTE: the app's own liveness probe is GET /health (in main.py). The routes here are /health/<something>.
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/limits")
def limits() -> dict:
    return svc.limits_payload()


@router.get("/summary", response_model=S.SummaryOut)
def summary(profile: Profile = Depends(require_profile), session: Session = Depends(get_session)):
    return svc.build_summary(profile, repo.latest_entry(session, profile), repo.get_goal(session, profile))


@router.get("/history", response_model=S.HistoryOut)
def history(
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    limit: int = Query(365, ge=1, le=2000),
    profile: Profile = Depends(require_profile),
    session: Session = Depends(get_session),
):
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="'from' must not be after 'to'.")
    return svc.build_history(repo.list_entries(session, profile, start=start, end=end, limit=limit))


@router.get("/monthly", response_model=S.MonthlyOut)
def monthly(months: int = Query(12, ge=1, le=60), profile: Profile = Depends(require_profile), session: Session = Depends(get_session)):
    today = datetime.now(timezone.utc).date()
    year, month = today.year, today.month - (months - 1)
    while month < 1:
        year, month = year - 1, month + 12
    return svc.build_monthly(repo.list_entries(session, profile, start=date(year, month, 1), limit=5000))


@router.post("/weight", response_model=S.WeightEntryOut, status_code=201)
def record_weight(body: S.WeightIn, response: Response, profile: Profile = Depends(require_profile), session: Session = Depends(get_session)):
    recorded_on = body.recorded_on or datetime.now(timezone.utc).date()
    entry, created = repo.upsert_weight(session, profile, recorded_on=recorded_on, weight_kg=body.weight_kg, note=body.note)
    session.commit()
    if not created:
        response.status_code = 200  # same date already had an entry: it was updated, not duplicated
    return svc.entry_out(entry)


@router.delete("/weight/{entry_id}", status_code=204)
def delete_weight(entry_id: int, profile: Profile = Depends(require_profile), session: Session = Depends(get_session)):
    entry = repo.get_entry(session, profile, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Weight entry not found.")
    repo.delete_entry(session, entry)
    session.commit()
    return Response(status_code=204)
