import uuid

from sqlalchemy import ForeignKey, Integer, String, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    input_uri: Mapped[str] = mapped_column(Text, nullable=False)
    output_uri: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at = mapped_column(TIMESTAMP(timezone=True))
    completed_at = mapped_column(TIMESTAMP(timezone=True))
    created_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
