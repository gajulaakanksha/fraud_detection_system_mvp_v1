from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import Caller, get_current_caller
from app.db.session import get_db
from app.schemas.overview import OverviewSummary, RiskTrendPoint, TopRule
from app.services import overview_service

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/summary", response_model=OverviewSummary)
def summary(db: Session = Depends(get_db), caller: Caller = Depends(get_current_caller)) -> OverviewSummary:
    return OverviewSummary(**overview_service.get_summary(db))


@router.get("/decision-distribution")
def decision_distribution(db: Session = Depends(get_db), caller: Caller = Depends(get_current_caller)) -> dict[str, int]:
    return overview_service.get_decision_distribution(db)


@router.get("/risk-trend", response_model=list[RiskTrendPoint])
def risk_trend(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_current_caller),
) -> list[RiskTrendPoint]:
    return [RiskTrendPoint(**p) for p in overview_service.get_risk_trend(db, days)]


@router.get("/top-rules", response_model=list[TopRule])
def top_rules(
    limit: int = Query(default=6, ge=1, le=50),
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_current_caller),
) -> list[TopRule]:
    return [TopRule(**r) for r in overview_service.get_top_rules(db, limit)]
