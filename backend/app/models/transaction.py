from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, SmallInteger, String, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),)

    transaction_id: Mapped[str] = mapped_column(String(14), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(12), ForeignKey("customers.customer_id"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(12), ForeignKey("merchants.merchant_id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(14), ForeignKey("devices.device_id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    transaction_country: Mapped[str] = mapped_column(String(2), nullable=False)
    ip_country: Mapped[str] = mapped_column(String(2), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    is_new_device: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_new_beneficiary: Mapped[bool] = mapped_column(Boolean, nullable=False)
    session_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    transactions_last_10_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_attempts_last_24_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_since_last_transaction: Mapped[int | None] = mapped_column(Integer)
    transaction_time = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ingested_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="single")
    batch_job_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("batch_jobs.id"))
    submitted_by_bank_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_clients.id"))

    # Labeling lineage for training/eval datasets only -- never populated by live scoring.
    fraud_label: Mapped[int | None] = mapped_column(SmallInteger)
    fraud_type: Mapped[str | None] = mapped_column(String(32))
