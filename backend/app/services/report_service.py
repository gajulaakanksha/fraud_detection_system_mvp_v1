"""Backing service for the Report screen: filtered/paginated transaction
history and CSV export. Both share one query-builder so the exported CSV
always matches exactly what the filtered list view showed -- a common bug
class is export silently using different filter logic than the list.
"""
import csv
import io
from datetime import date, datetime

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Query, Session

from app.decision_engine.risk_level import RISK_LEVEL_CUTOFFS
from app.models.decision import Decision
from app.models.transaction import Transaction

# Risk level is a pure score-descriptive banding, independent of decision_band
# (which is action-oriented and also folds in rule overrides) -- the blueprint's
# Report screen filters on both separately (Section 5.4). Built from the same
# cutoffs risk_level.risk_level_from_score() uses, not a second hardcoded copy.
_LOW, _MEDIUM, _HIGH = RISK_LEVEL_CUTOFFS
RISK_LEVEL_CASE = case(
    (Decision.risk_score < _LOW, "low"),
    (Decision.risk_score < _MEDIUM, "medium"),
    (Decision.risk_score < _HIGH, "high"),
    else_="critical",
)


def _base_query(db: Session, decision: str | None, risk_level: str | None, q: str | None,
                 from_: datetime | None, to: datetime | None) -> Query:
    query = db.query(Transaction, Decision, RISK_LEVEL_CASE.label("risk_level")).join(
        Decision, Decision.transaction_id == Transaction.transaction_id
    )
    filters = []
    if decision:
        filters.append(Decision.decision_band == decision)
    if risk_level:
        filters.append(RISK_LEVEL_CASE == risk_level)
    if q:
        like = f"%{q}%"
        filters.append(or_(
            Transaction.transaction_id.ilike(like),
            Transaction.customer_id.ilike(like),
            Transaction.merchant_id.ilike(like),
        ))
    if from_:
        filters.append(Decision.decided_at >= from_)
    if to:
        filters.append(Decision.decided_at <= to)
    if filters:
        query = query.filter(and_(*filters))
    return query.order_by(Decision.decided_at.desc())


def list_transactions(
    db: Session, decision: str | None, risk_level: str | None, q: str | None,
    from_: datetime | None, to: datetime | None, page: int, page_size: int,
) -> tuple[list[dict], int]:
    query = _base_query(db, decision, risk_level, q, from_, to)
    total = query.order_by(None).count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    results = [
        {
            "transaction_id": tx.transaction_id, "time": decision_row.decided_at,
            "customer_id": tx.customer_id, "merchant_id": tx.merchant_id,
            "amount": float(tx.amount), "currency": tx.currency,
            "decision_band": decision_row.decision_band, "risk_level": rlevel,
        }
        for tx, decision_row, rlevel in rows
    ]
    return results, total


def export_transactions_csv(
    db: Session, decision: str | None, risk_level: str | None, q: str | None,
    from_: datetime | None, to: datetime | None,
) -> str:
    query = _base_query(db, decision, risk_level, q, from_, to)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["transaction_id", "time", "customer_id", "merchant_id", "amount", "currency", "decision_band", "risk_level"])
    for tx, decision_row, rlevel in query.all():
        writer.writerow([
            tx.transaction_id, decision_row.decided_at.isoformat(), tx.customer_id, tx.merchant_id,
            tx.amount, tx.currency, decision_row.decision_band, rlevel,
        ])
    return buf.getvalue()
