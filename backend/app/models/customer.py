from sqlalchemy import CheckConstraint, Numeric, SmallInteger, String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("customer_risk_score BETWEEN 0 AND 100", name="ck_customer_risk_score_range"),
    )

    customer_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    home_country: Mapped[str] = mapped_column(String(2), nullable=False)
    account_created_at: Mapped["TIMESTAMP"] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    average_transaction_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    customer_risk_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
