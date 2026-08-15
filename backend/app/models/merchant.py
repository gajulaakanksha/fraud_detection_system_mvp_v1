from sqlalchemy import CheckConstraint, SmallInteger, String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = (
        CheckConstraint("merchant_risk_score BETWEEN 0 AND 100", name="ck_merchant_risk_score_range"),
    )

    merchant_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    merchant_category: Mapped[str] = mapped_column(String(32), nullable=False)
    home_country: Mapped[str] = mapped_column(String(2), nullable=False)
    merchant_risk_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
