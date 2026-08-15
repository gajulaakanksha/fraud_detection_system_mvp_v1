"""Admin config endpoints (blueprint Section 5.6): retune rules/thresholds
without a redeploy (FR5). band_resolver.py and rules_engine.py already read
both tables fresh on every scoring request -- a PATCH here takes effect on
the very next transaction scored, no cache to invalidate.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db.session import get_db
from app.models.decision_threshold import DecisionThreshold
from app.models.rule import Rule
from app.models.user import User
from app.schemas.admin import DecisionThresholdOut, DecisionThresholdUpdateRequest, RuleOut, RuleUpdateRequest

router = APIRouter(tags=["admin"])


@router.get("/rules", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> list[RuleOut]:
    return db.query(Rule).order_by(Rule.rule_code).all()


@router.patch("/rules/{rule_code}", response_model=RuleOut)
def update_rule(
    rule_code: str, payload: RuleUpdateRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> RuleOut:
    rule = db.query(Rule).filter(Rule.rule_code == rule_code).one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": f"No rule {rule_code}"}},
        )
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.severity is not None:
        rule.severity = payload.severity
    if payload.config is not None:
        rule.config = payload.config
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/decision-thresholds", response_model=list[DecisionThresholdOut])
def list_thresholds(db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> list[DecisionThresholdOut]:
    return db.query(DecisionThreshold).order_by(DecisionThreshold.min_score).all()


@router.patch("/decision-thresholds/{band}", response_model=DecisionThresholdOut)
def update_threshold(
    band: str, payload: DecisionThresholdUpdateRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> DecisionThresholdOut:
    threshold = db.query(DecisionThreshold).filter(DecisionThreshold.band == band).one_or_none()
    if threshold is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": f"No decision threshold for band {band}"}},
        )
    new_min = payload.min_score if payload.min_score is not None else float(threshold.min_score)
    new_max = payload.max_score if payload.max_score is not None else float(threshold.max_score)
    if new_min >= new_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "invalid_range", "message": "min_score must be less than max_score"}},
        )
    # NOTE: this endpoint does not enforce contiguity across the other 3
    # bands -- retuning one band's edges without adjusting its neighbors can
    # open a gap or overlap. Left as the admin's responsibility to match the
    # blueprint's literal per-band PATCH interface (Section 5.6); a stricter
    # implementation would accept all 4 cutoffs atomically instead.
    threshold.min_score = new_min
    threshold.max_score = new_max
    if payload.recommended_action is not None:
        threshold.recommended_action = payload.recommended_action
    db.commit()
    db.refresh(threshold)
    return threshold
