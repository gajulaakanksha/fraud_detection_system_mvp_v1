import uuid

from sqlalchemy import Numeric, String, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DecisionThreshold(Base):
    __tablename__ = "decision_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    band: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    min_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    # Shared across all 4 band rows whenever they're (re)seeded together as a
    # matched set -- lets a Decision record exactly which generation of
    # thresholds was in effect, independent of the model_version that scored it.
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="unversioned")
    updated_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
