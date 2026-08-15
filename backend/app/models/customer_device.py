from sqlalchemy import ForeignKey, String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CustomerDevice(Base):
    """The persisted customer<->device history that fixes the is_new_device
    calibration bug: it lets the feature builder answer "has this device been
    used by this customer before?" from real history instead of guessing.
    """

    __tablename__ = "customer_devices"

    customer_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("customers.customer_id"), primary_key=True
    )
    device_id: Mapped[str] = mapped_column(
        String(14), ForeignKey("devices.device_id"), primary_key=True
    )
    first_seen_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
