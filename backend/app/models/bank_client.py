import uuid

from sqlalchemy import Boolean, String, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BankClient(Base):
    """One row per API credential issued to an integrating bank's backend.

    Distinct from `users`: users are humans logging into the analyst console
    (email/password -> JWT session); bank_clients are machine callers hitting
    the scoring/batch API directly (X-API-Key -> no session, long-lived key).
    """

    __tablename__ = "bank_clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    bank_name: Mapped[str] = mapped_column(String(128), nullable=False)
    bank_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    api_key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    revoked_at = mapped_column(TIMESTAMP(timezone=True))
