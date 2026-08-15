"""Turns a scoring request + persisted history into the exact feature row
the model expects.

Per the blueprint's Section 5.2 API contract, only three fields are ever
server-resolved and override whatever the client sent: is_new_device,
merchant_risk_score, customer_risk_score. Everything else (amount, device
age, velocity counters, etc.) is accepted from the request -- this is what
fixes the is_new_device calibration bug specifically, without requiring a
full server-side velocity/session-history subsystem to ship in this pass.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.customer_device import CustomerDevice
from app.models.device import Device
from app.models.merchant import Merchant
from app.schemas.transaction import ScoreTransactionRequest

FEATURE_COLUMNS = [
    # numeric
    "amount", "amount_to_avg_ratio", "device_age_days", "account_age_days",
    "transactions_last_10_minutes", "failed_attempts_last_24_hours",
    "days_since_last_transaction", "session_duration_seconds",
    "merchant_risk_score", "customer_risk_score",
    # binary
    "is_new_device", "is_new_beneficiary", "is_cross_border", "is_ip_merchant_country_mismatch",
    # categorical
    "channel", "merchant_category", "customer_home_country", "transaction_country", "ip_country",
]

DEFAULT_RISK_SCORE = 20  # neutral-low prior for a brand-new customer/merchant with no history yet


@dataclass
class ResolvedHistory:
    customer: Customer
    merchant: Merchant
    device: Device | None
    is_new_device: bool
    is_new_customer: bool
    is_new_merchant: bool


def _resolve_customer(db: Session, req: ScoreTransactionRequest) -> tuple[Customer, bool]:
    customer = db.get(Customer, req.customer_id)
    if customer is not None:
        return customer, False
    customer = Customer(
        customer_id=req.customer_id,
        home_country=req.customer_home_country,
        account_created_at=req.transaction_time,
        average_transaction_amount=req.average_transaction_amount or req.amount,
        customer_risk_score=req.customer_risk_score or DEFAULT_RISK_SCORE,
    )
    db.add(customer)
    db.flush()
    return customer, True


def _resolve_merchant(db: Session, req: ScoreTransactionRequest) -> tuple[Merchant, bool]:
    merchant = db.get(Merchant, req.merchant_id)
    if merchant is not None:
        return merchant, False
    merchant = Merchant(
        merchant_id=req.merchant_id,
        merchant_category=req.merchant_category,
        home_country=req.transaction_country,
        merchant_risk_score=req.merchant_risk_score or DEFAULT_RISK_SCORE,
    )
    db.add(merchant)
    db.flush()
    return merchant, True


def _resolve_device(db: Session, req: ScoreTransactionRequest) -> tuple[Device | None, bool]:
    device = db.get(Device, req.device_id)
    is_new = device is None
    if device is None:
        device = Device(device_id=req.device_id, first_seen_at=req.transaction_time, last_seen_at=req.transaction_time)
        db.add(device)
        db.flush()
    return device, is_new


def resolve_history(db: Session, req: ScoreTransactionRequest) -> ResolvedHistory:
    customer, is_new_customer = _resolve_customer(db, req)
    merchant, is_new_merchant = _resolve_merchant(db, req)
    device, is_new_device_globally = _resolve_device(db, req)

    known_pair = (
        db.query(CustomerDevice)
        .filter(CustomerDevice.customer_id == req.customer_id, CustomerDevice.device_id == req.device_id)
        .one_or_none()
    )
    is_new_device = known_pair is None

    return ResolvedHistory(
        customer=customer, merchant=merchant, device=device,
        is_new_device=is_new_device, is_new_customer=is_new_customer, is_new_merchant=is_new_merchant,
    )


def build_feature_row(req: ScoreTransactionRequest, history: ResolvedHistory) -> pd.DataFrame:
    device_age_days = req.device_age_days
    if device_age_days is None:
        device_age_days = 0 if history.is_new_device else max(
            (req.transaction_time - history.device.first_seen_at.replace(tzinfo=timezone.utc)).days, 0
        )

    account_age_days = req.account_age_days
    if account_age_days is None:
        account_created_at = history.customer.account_created_at
        if account_created_at.tzinfo is None:
            account_created_at = account_created_at.replace(tzinfo=timezone.utc)
        account_age_days = max((req.transaction_time - account_created_at).days, 0)

    average_transaction_amount = req.average_transaction_amount
    if average_transaction_amount is None:
        average_transaction_amount = float(history.customer.average_transaction_amount)

    # Server-resolved, always override client input for these three (the
    # calibration fix): is_new_device, customer_risk_score, merchant_risk_score.
    is_new_device = history.is_new_device
    customer_risk_score = history.customer.customer_risk_score
    merchant_risk_score = history.merchant.merchant_risk_score

    row = {
        "amount": req.amount,
        "amount_to_avg_ratio": req.amount / max(average_transaction_amount, 1.0),
        "device_age_days": device_age_days,
        "account_age_days": account_age_days,
        "transactions_last_10_minutes": req.transactions_last_10_minutes,
        "failed_attempts_last_24_hours": req.failed_attempts_last_24_hours,
        "days_since_last_transaction": req.days_since_last_transaction if req.days_since_last_transaction is not None else 0,
        "session_duration_seconds": req.session_duration_seconds if req.session_duration_seconds is not None else 0,
        "merchant_risk_score": merchant_risk_score,
        "customer_risk_score": customer_risk_score,
        "is_new_device": int(is_new_device),
        "is_new_beneficiary": int(req.is_new_beneficiary),
        "is_cross_border": int(req.ip_country != req.customer_home_country),
        "is_ip_merchant_country_mismatch": int(req.ip_country != req.transaction_country),
        "channel": req.channel,
        "merchant_category": req.merchant_category,
        "customer_home_country": req.customer_home_country,
        "transaction_country": req.transaction_country,
        "ip_country": req.ip_country,
    }
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def update_history_after_scoring(db: Session, req: ScoreTransactionRequest, history: ResolvedHistory) -> None:
    """Fire-and-forget-equivalent: upserts device/customer_device last-seen
    so the *next* transaction benefits from this one (blueprint step 3.3.7)."""
    if history.device is not None:
        history.device.last_seen_at = req.transaction_time

    pair = (
        db.query(CustomerDevice)
        .filter(CustomerDevice.customer_id == req.customer_id, CustomerDevice.device_id == req.device_id)
        .one_or_none()
    )
    if pair is None:
        db.add(CustomerDevice(
            customer_id=req.customer_id, device_id=req.device_id,
            first_seen_at=req.transaction_time, last_seen_at=req.transaction_time,
        ))
    else:
        pair.last_seen_at = req.transaction_time
