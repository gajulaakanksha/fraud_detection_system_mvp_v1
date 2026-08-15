"""Backing service for the Overview dashboard (blueprint Section 5.5)."""
from datetime import date, timedelta

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.rule import Rule
from app.models.rule_hit import RuleHit


def get_summary(db: Session) -> dict:
    row = db.query(
        func.count(Decision.id),
        func.avg(Decision.risk_score),
        func.avg(Decision.processing_time_ms),
        func.count(Decision.id).filter(Decision.decision_band.in_(("decline", "manual_review"))),
    ).one()
    total, avg_risk, avg_time, decline_hold_count = row
    return {
        "transactions_analyzed": total or 0,
        "decline_hold_rate": (decline_hold_count / total) if total else 0.0,
        "avg_risk_score": float(avg_risk) if avg_risk is not None else 0.0,
        "avg_processing_time_ms": float(avg_time) if avg_time is not None else 0.0,
    }


def get_decision_distribution(db: Session) -> dict[str, int]:
    rows = db.query(Decision.decision_band, func.count(Decision.id)).group_by(Decision.decision_band).all()
    return {band: count for band, count in rows}


def get_risk_trend(db: Session, days: int) -> list[dict]:
    # On-demand refresh (blueprint: "nightly + on-demand refresh") -- fine at
    # this data volume; a real deployment should move this to a scheduled
    # worker task instead of refreshing synchronously on every request.
    db.execute(text("REFRESH MATERIALIZED VIEW mv_overview_daily"))
    db.commit()

    since = date.today() - timedelta(days=days)
    rows = db.execute(text(
        "SELECT day::date, avg_risk_score, transactions_analyzed FROM mv_overview_daily "
        "WHERE day >= :since ORDER BY day"
    ), {"since": since}).all()

    by_day = {r[0]: (float(r[1] or 0), int(r[2] or 0)) for r in rows}
    return [
        {
            "day": since + timedelta(days=i),
            "avg_risk_score": by_day.get(since + timedelta(days=i), (0.0, 0))[0],
            "transactions": by_day.get(since + timedelta(days=i), (0.0, 0))[1],
        }
        for i in range((date.today() - since).days + 1)
    ]


def get_top_rules(db: Session, limit: int) -> list[dict]:
    rows = (
        db.query(Rule.rule_code, func.count(RuleHit.id).label("hit_count"))
        .join(RuleHit, RuleHit.rule_id == Rule.id)
        .group_by(Rule.rule_code)
        .order_by(func.count(RuleHit.id).desc())
        .limit(limit)
        .all()
    )
    return [{"rule_code": code, "hit_count": count} for code, count in rows]
