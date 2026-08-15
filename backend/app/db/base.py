from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import every model module here so Alembic's autogenerate (and Base.metadata)
# sees the full schema. Individual modules are otherwise never imported directly.
from app.models import (  # noqa: E402,F401
    audit_log,
    bank_client,
    batch_job,
    customer,
    customer_device,
    decision,
    decision_threshold,
    device,
    merchant,
    model_version,
    rule,
    rule_hit,
    transaction,
    user,
)
