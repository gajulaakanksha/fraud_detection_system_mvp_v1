import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    transaction_id: Mapped[str] = mapped_column(String(14), ForeignKey("transactions.transaction_id"), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id"), nullable=False
    )
    # 0-100 RISK SCORE, not a calibrated probability -- see
    # decision_engine/explainability.py module docstring and
    # IMPLEMENTATION_NOTES.md for why (reliability curve is monotonic/
    # rank-ordered but overconfident vs. observed fraud rate at every
    # bin except the very top). Safe to threshold against; not safe to
    # present as "X% chance of fraud" without a calibration layer.
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    decision_band: Mapped[str] = mapped_column(String(16), nullable=False)
    # Whether decision_band came straight from the score-vs-threshold lookup,
    # or was forced/bumped by a rule (band_resolver.py: critical->decline,
    # high->step_up_auth). Persisted at scoring time rather than recomputed
    # later, since decision_thresholds can be retuned after the fact.
    band_source: Mapped[str] = mapped_column(String(16), nullable=False, default="model_score")
    override_rule_code: Mapped[str | None] = mapped_column(String(64))
    # Which generation of decision_thresholds produced decision_band --
    # independent of model_version_id, since thresholds can be retuned
    # without retraining (FR5).
    policy_version: Mapped[str | None] = mapped_column(String(64))
    summary_reason: Mapped[str] = mapped_column(Text, nullable=False)
    contributing_factors: Mapped[list] = mapped_column(JSONB, nullable=False)
    shap_values: Mapped[dict | None] = mapped_column(JSONB)
    # Total end-to-end request time (what NFR1's P50<100ms/P95<300ms budgets
    # against) vs. the two dominant components broken out separately --
    # a 3.3s regression traced to an uncached SHAP explainer would have been
    # invisible in processing_time_ms alone without this split.
    processing_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    inference_time_ms: Mapped[int | None] = mapped_column(Integer)
    explainability_time_ms: Mapped[int | None] = mapped_column(Integer)
    decided_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
