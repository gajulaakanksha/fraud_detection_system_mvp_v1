from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScoreTransactionRequest(BaseModel):
    transaction_id: str = Field(max_length=14)
    customer_id: str = Field(max_length=12)
    merchant_id: str = Field(max_length=12)
    device_id: str = Field(max_length=14)
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    transaction_country: str = Field(min_length=2, max_length=2)
    customer_home_country: str = Field(min_length=2, max_length=2)
    ip_country: str = Field(min_length=2, max_length=2)
    channel: str
    merchant_category: str
    transaction_time: datetime

    session_duration_seconds: int | None = None
    device_age_days: int | None = None
    account_age_days: int | None = None
    average_transaction_amount: float | None = None
    transactions_last_10_minutes: int = 0
    failed_attempts_last_24_hours: int = 0
    days_since_last_transaction: int | None = None
    is_new_beneficiary: bool = False

    # Demo/testing overrides only -- server-computed values win by default.
    is_new_device: bool | None = None
    merchant_risk_score: int | None = None
    customer_risk_score: int | None = None


class RecommendedAction(BaseModel):
    label: str
    detail: str


class RuleHitOut(BaseModel):
    """Rule metadata as of the moment it fired, sourced from the rules
    table -- not duplicated/hardcoded on the frontend, so it can't go stale
    if an admin edits severity/description via PATCH /v1/rules/{code}."""

    rule_code: str
    severity: str
    description: str


class ContributingFactorOut(BaseModel):
    """Structured form of a contributing factor, for a frontend that wants
    to render direction/magnitude (e.g. an arrow + bar) instead of parsing
    the plain-English string in `contributing_factors`."""

    feature: str
    category: Literal["numeric", "binary", "categorical"]
    value: str | None = Field(default=None, description="Matched category value, only set for categorical features.")
    shap_value: float
    direction: Literal["increases_risk", "decreases_risk"]
    explanation: str


class ScoreTransactionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    transaction_id: str
    risk_score: float = Field(
        description=(
            "A 0-100 RISK SCORE, not a calibrated probability. It is monotonic with "
            "actual fraud likelihood (higher score = higher observed fraud rate) and "
            "safe to threshold against, but its numeric value should not be read as "
            "'X% chance of fraud' -- e.g. a score of 85 has historically corresponded "
            "to roughly a 19% observed fraud rate, not 85%, because the underlying "
            "model optimizes ranking, not probability calibration. Decision bands are "
            "tuned against realized outcomes at each cutoff, not the score's face value."
        ),
    )
    decision_band: str
    risk_level: Literal["low", "medium", "high", "critical"] = Field(
        description="Pure score banding (see report_service.RISK_LEVEL_CASE), independent of decision_band -- "
        "not affected by rule overrides.",
    )
    band_source: Literal["model_score", "rule_override"] = Field(
        description="Whether decision_band came straight from the score-vs-threshold lookup, or was forced/bumped by a rule.",
    )
    override_rule: str | None = Field(
        default=None, description="rule_code that forced/bumped the band, only set when band_source is 'rule_override'.",
    )
    policy_version: str = Field(
        description="Which generation of decision_thresholds produced decision_band -- independent of model_version.",
    )
    recommended_action: RecommendedAction
    summary_reason: str
    contributing_factors: list[str]
    contributing_factors_detail: list[ContributingFactorOut]
    rule_hits: list[RuleHitOut]
    model_version: str
    processing_time_ms: int = Field(description="Total end-to-end request time (the number NFR1's P50/P95 budget is measured against).")
    inference_time_ms: int | None = Field(default=None, description="Preprocessing + model.predict_proba only.")
    explainability_time_ms: int | None = Field(default=None, description="SHAP explanation computation only.")
    decided_at: datetime


class TechnicalDetailResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    transaction_id: str
    model_version: str
    policy_version: str
    risk_score: float = Field(description="See ScoreTransactionResponse.risk_score -- a risk score, not a calibrated probability.")
    contributing_factors_detail: list[ContributingFactorOut]
    shap_values: dict
