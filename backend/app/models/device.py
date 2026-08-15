from sqlalchemy import String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(14), primary_key=True)
    first_seen_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
