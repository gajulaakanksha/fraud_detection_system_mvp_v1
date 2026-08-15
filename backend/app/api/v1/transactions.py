from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import Caller, get_current_caller
from app.db.session import get_db
from app.decision_engine.model_loader import get_active_model
from app.models.decision import Decision
from app.models.transaction import Transaction
from app.schemas.transaction import (
    ContributingFactorOut, ScoreTransactionRequest, ScoreTransactionResponse, TechnicalDetailResponse,
)
from app.services.scoring_service import _response_from_persisted, score_transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _not_found(transaction_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "not_found", "message": f"No decision found for transaction {transaction_id}"}},
    )


@router.post("/score", response_model=ScoreTransactionResponse)
def score(
    payload: ScoreTransactionRequest,
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_current_caller),
) -> ScoreTransactionResponse:
    return score_transaction(
        db=db,
        req=payload,
        actor_user_id=caller.user.id if caller.user else None,
        actor_type=caller.actor_type,
        bank_code=caller.bank_client.bank_code if caller.bank_client else None,
    )


@router.get("/{transaction_id}", response_model=ScoreTransactionResponse)
def get_decision(
    transaction_id: str,
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_current_caller),
) -> ScoreTransactionResponse:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise _not_found(transaction_id)
    return _response_from_persisted(db, transaction_id)


@router.get("/{transaction_id}/technical-detail", response_model=TechnicalDetailResponse)
def technical_detail(
    transaction_id: str,
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_current_caller),
) -> TechnicalDetailResponse:
    decision = db.query(Decision).filter(Decision.transaction_id == transaction_id).one_or_none()
    if decision is None:
        raise _not_found(transaction_id)

    loaded = get_active_model(db)
    return TechnicalDetailResponse(
        transaction_id=transaction_id,
        model_version=loaded.version_tag,
        policy_version=decision.policy_version or "unversioned",
        risk_score=float(decision.risk_score),
        contributing_factors_detail=[ContributingFactorOut(**f) for f in decision.contributing_factors],
        shap_values=decision.shap_values or {},
    )
