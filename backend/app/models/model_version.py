import uuid

from sqlalchemy import Boolean, Numeric, String, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    version_tag: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    pr_auc: Mapped[float | None] = mapped_column(Numeric(5, 4))
    trained_at = mapped_column(TIMESTAMP(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
