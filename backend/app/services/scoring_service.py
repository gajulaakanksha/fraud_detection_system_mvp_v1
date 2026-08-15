"""Orchestrates the single-transaction scoring path (blueprint Section 3.3):
feature build -> model score -> SHAP explain -> rules -> band resolve ->
persist decision/rule_hits/audit_log -> update device/customer history.

Idempotency (FR4): resubmitting a transaction_id that's already been scored
returns the original decision unchanged rather than silently re-scoring.
"""
import dataclasses
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.decision_engine import explainability, model_loader
from app.decision_engine.band_resolver import resolve_band
from app.decision_engine.feature_builder import build_feature_row, resolve_history, update_history_after_scoring
from app.decision_engine.risk_level import risk_level_from_score
from app.decision_engine.rules_engine import evaluate_rules
from app.models.audit_log import AuditLog
from app.models.decision import Decision
from app.models.decision_threshold import DecisionThreshold
from app.models.model_version import ModelVersion
from app.models.rule import Rule
from app.models.rule_hit import RuleHit as RuleHitModel
from app.models.transaction import Transaction
from app.schemas.transaction import (
    ContributingFactorOut, RecommendedAction, RuleHitOut, ScoreTransactionRequest, ScoreTransactionResponse,
)

BAND_LABELS = {
    "monitor": "Monitor",
    "step_up_auth": "Step-up authentication",
    "manual_review": "Manual review",
    "decline": "Decline",
}


class DuplicateTransactionError(Exception):
    pass


def _response_from_persisted(db: Session, transaction_id: str) -> ScoreTransactionResponse:
    decision = db.query(Decision).filter(Decision.transaction_id == transaction_id).one()
    rule_hits_out = [
        RuleHitOut(rule_code=code, severity=severity, description=description)
        for (code, severity, description) in (
            db.query(Rule.rule_code, Rule.severity, Rule.description)
            .join(RuleHitModel, RuleHitModel.rule_id == Rule.id)
            .filter(RuleHitModel.decision_id == decision.id)
            .all()
        )
    ]
    mv = db.get(ModelVersion, decision.model_version_id)
    threshold = db.query(DecisionThreshold).filter(DecisionThreshold.band == decision.decision_band).one_or_none()

    factors_detail = [ContributingFactorOut(**f) for f in decision.contributing_factors]

    return ScoreTransactionResponse(
        transaction_id=transaction_id,
        risk_score=float(decision.risk_score),
        decision_band=decision.decision_band,
        risk_level=risk_level_from_score(float(decision.risk_score)),
        band_source=decision.band_source,
        override_rule=decision.override_rule_code,
        policy_version=decision.policy_version or "unversioned",
        recommended_action=RecommendedAction(
            label=BAND_LABELS.get(decision.decision_band, decision.decision_band),
            detail=threshold.recommended_action if threshold else decision.summary_reason,
        ),
        summary_reason=decision.summary_reason,
        contributing_factors=[f.explanation for f in factors_detail],
        contributing_factors_detail=factors_detail,
        rule_hits=rule_hits_out,
        model_version=mv.version_tag if mv else "unknown",
        processing_time_ms=decision.processing_time_ms,
        inference_time_ms=decision.inference_time_ms,
        explainability_time_ms=decision.explainability_time_ms,
        decided_at=decision.decided_at,
    )


def score_transaction(
    db: Session,
    req: ScoreTransactionRequest,
    actor_user_id: uuid.UUID | None,
    actor_type: str,
    bank_code: str | None = None,
) -> ScoreTransactionResponse:
    t0 = time.perf_counter()

    existing = db.get(Transaction, req.transaction_id)
    if existing is not None:
        return _response_from_persisted(db, req.transaction_id)

    loaded = model_loader.get_active_model(db)

    history = resolve_history(db, req)
    feature_row = build_feature_row(req, history)

    t_inference_start = time.perf_counter()
    X = loaded.preprocessor.transform(feature_row)
    proba = float(loaded.model.predict_proba(X)[:, 1][0])
    inference_time_ms = int((time.perf_counter() - t_inference_start) * 1000)

    risk_score_0_100 = round(proba * 100, 2)

    rule_hits = evaluate_rules(db, feature_row)
    band_result = resolve_band(db, risk_score_0_100, rule_hits)

    t_explain_start = time.perf_counter()
    explanation = explainability.explain(
        loaded.shap_explainer, X, loaded.output_feature_names, risk_score_0_100, band_result.band,
    )
    explainability_time_ms = int((time.perf_counter() - t_explain_start) * 1000)

    processing_time_ms = int((time.perf_counter() - t0) * 1000)

    transaction_time = req.transaction_time
    if transaction_time.tzinfo is None:
        transaction_time = transaction_time.replace(tzinfo=timezone.utc)

    transaction = Transaction(
        transaction_id=req.transaction_id,
        customer_id=req.customer_id,
        merchant_id=req.merchant_id,
        device_id=req.device_id,
        amount=req.amount,
        currency=req.currency,
        transaction_country=req.transaction_country,
        ip_country=req.ip_country,
        channel=req.channel,
        is_new_device=history.is_new_device,
        is_new_beneficiary=req.is_new_beneficiary,
        session_duration_seconds=req.session_duration_seconds,
        transactions_last_10_minutes=req.transactions_last_10_minutes,
        failed_attempts_last_24_hours=req.failed_attempts_last_24_hours,
        days_since_last_transaction=req.days_since_last_transaction,
        transaction_time=transaction_time,
        source="bank_api" if actor_type == "bank_client" else "single",
    )
    db.add(transaction)
    db.flush()

    factors_as_dicts = [dataclasses.asdict(f) for f in explanation.contributing_factors_detail]

    decision = Decision(
        transaction_id=req.transaction_id,
        model_version_id=loaded.model_version_id,
        risk_score=risk_score_0_100,
        decision_band=band_result.band,
        band_source=band_result.source,
        override_rule_code=band_result.override_rule_code,
        policy_version=band_result.policy_version,
        summary_reason=explanation.summary_reason,
        contributing_factors=factors_as_dicts,
        shap_values=explanation.shap_values,
        processing_time_ms=processing_time_ms,
        inference_time_ms=inference_time_ms,
        explainability_time_ms=explainability_time_ms,
    )
    db.add(decision)
    db.flush()

    for hit in rule_hits:
        db.add(RuleHitModel(decision_id=decision.id, rule_id=hit.rule.id, detail=hit.detail))

    db.add(AuditLog(
        actor_user_id=actor_user_id,
        action="score_transaction",
        entity_type="transaction",
        entity_id=req.transaction_id,
        metadata_={
            "actor_type": actor_type,
            "bank_code": bank_code,
            "decision_band": band_result.band,
            "risk_score": risk_score_0_100,
        },
    ))

    update_history_after_scoring(db, req, history)

    db.commit()

    return ScoreTransactionResponse(
        transaction_id=req.transaction_id,
        risk_score=risk_score_0_100,
        decision_band=band_result.band,
        risk_level=risk_level_from_score(risk_score_0_100),
        band_source=band_result.source,
        override_rule=band_result.override_rule_code,
        policy_version=band_result.policy_version,
        recommended_action=RecommendedAction(
            label=BAND_LABELS.get(band_result.band, band_result.band),
            detail=band_result.recommended_action,
        ),
        summary_reason=explanation.summary_reason,
        contributing_factors=explanation.contributing_factors,
        contributing_factors_detail=[ContributingFactorOut(**f) for f in factors_as_dicts],
        rule_hits=[
            RuleHitOut(rule_code=hit.rule.rule_code, severity=hit.rule.severity, description=hit.rule.description)
            for hit in rule_hits
        ],
        model_version=loaded.version_tag,
        processing_time_ms=processing_time_ms,
        inference_time_ms=inference_time_ms,
        explainability_time_ms=explainability_time_ms,
        decided_at=decision.decided_at or datetime.now(timezone.utc),
    )
