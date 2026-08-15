from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.dependencies import Caller, get_current_caller
from app.db.session import get_db
from app.schemas.report import TransactionListResponse
from app.services import report_service

router = APIRouter(prefix="/transactions", tags=["report"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    decision: str | None = Query(default=None, description="monitor|step_up_auth|manual_review|decline"),
    risk_level: str | None = Query(default=None, description="low|medium|high|critical"),
    q: str | None = Query(default=None, description="Free-text search over transaction/customer/merchant ID"),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_current_caller),
) -> TransactionListResponse:
    results, total = report_service.list_transactions(db, decision, risk_level, q, from_, to, page, page_size)
    return TransactionListResponse(results=results, page=page, page_size=page_size, total=total)


@router.get("/export")
def export_transactions(
    decision: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    q: str | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_current_caller),
) -> Response:
    csv_text = report_service.export_transactions_csv(db, decision, risk_level, q, from_, to)
    return Response(
        content=csv_text, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions_export.csv"},
    )
