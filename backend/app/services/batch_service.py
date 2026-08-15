"""Batch upload handling: schema validation against the template *before*
any row is touched (NFR7), file storage, and batch_jobs bookkeeping. The
actual scoring happens in app/workers/batch_scoring_task.py, off the
request path, via RQ.
"""
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.models.batch_job import BatchJob
from app.models.decision import Decision
from app.models.transaction import Transaction

# Local disk for MVP (blueprint Section 6: "S3-compatible bucket (or local
# disk for MVP demo)"). Swap for an S3 client behind save_upload/result_path
# when needed -- callers only depend on this module's functions, not the
# storage mechanism.
STORAGE_DIR = Path(__file__).resolve().parents[2] / "data" / "batch"
UPLOAD_DIR = STORAGE_DIR / "uploads"
RESULT_DIR = STORAGE_DIR / "results"

REQUIRED_COLUMNS = [
    "transaction_id", "customer_id", "merchant_id", "device_id", "amount", "currency",
    "transaction_country", "customer_home_country", "ip_country", "channel",
    "merchant_category", "transaction_time",
]
OPTIONAL_COLUMNS = [
    "session_duration_seconds", "device_age_days", "account_age_days",
    "average_transaction_amount", "transactions_last_10_minutes",
    "failed_attempts_last_24_hours", "days_since_last_transaction", "is_new_beneficiary",
]
TEMPLATE_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class CsvSchemaError(Exception):
    """Raised when the uploaded CSV is missing required columns -- rejected
    before any row is scored, per NFR7."""


# A header-only template leaves the exact expected format (especially
# transaction_time -- ISO-8601 UTC, e.g. trailing "Z") to guesswork. This
# example row uses a real seeded customer/merchant pair so it also
# demonstrates the "resolves from real history" path if uploaded as-is.
EXAMPLE_ROW = {
    "transaction_id": "TXN-EXAMPLE01", "customer_id": "CUS-000000", "merchant_id": "MER-000000",
    "device_id": "DEV-EXAMPLE01", "amount": "150.00", "currency": "SGD",
    "transaction_country": "SG", "customer_home_country": "SG", "ip_country": "SG",
    "channel": "mobile_app", "merchant_category": "grocery", "transaction_time": "2026-08-15T09:00:00Z",
    "session_duration_seconds": "60", "device_age_days": "", "account_age_days": "",
    "average_transaction_amount": "", "transactions_last_10_minutes": "0",
    "failed_attempts_last_24_hours": "0", "days_since_last_transaction": "1", "is_new_beneficiary": "false",
}


def csv_template_bytes() -> bytes:
    header = ",".join(TEMPLATE_COLUMNS)
    example = ",".join(EXAMPLE_ROW[c] for c in TEMPLATE_COLUMNS)
    return f"{header}\n{example}\n".encode("utf-8")


def validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise CsvSchemaError(f"Missing required columns: {', '.join(missing)}")


def create_batch_job(db: Session, submitted_by: uuid.UUID, filename: str, file_bytes: bytes) -> tuple[BatchJob, int]:
    import io
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except pd.errors.EmptyDataError:
        raise CsvSchemaError("The uploaded file is empty.")
    except pd.errors.ParserError as exc:
        raise CsvSchemaError(f"Could not parse file as CSV: {exc}")
    validate_columns(df)
    row_count = len(df)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    job = BatchJob(
        submitted_by=submitted_by,
        original_filename=filename,
        input_uri="",  # filled in after we have the job id, below
        row_count=row_count,
        status="queued",
    )
    db.add(job)
    db.flush()

    input_path = UPLOAD_DIR / f"{job.id}.csv"
    input_path.write_bytes(file_bytes)
    job.input_uri = str(input_path)
    db.commit()

    return job, row_count


def result_path(job: BatchJob) -> Path:
    return RESULT_DIR / f"{job.id}_scored.csv"


def rows_processed_count(db: Session, job_id: uuid.UUID) -> int:
    return db.query(Transaction).filter(Transaction.batch_job_id == job_id).count()


def decision_distribution(db: Session, job_id: uuid.UUID) -> dict[str, int]:
    rows = (
        db.query(Decision.decision_band, Transaction.transaction_id)
        .join(Transaction, Transaction.transaction_id == Decision.transaction_id)
        .filter(Transaction.batch_job_id == job_id)
        .all()
    )
    dist: dict[str, int] = {}
    for band, _ in rows:
        dist[band] = dist.get(band, 0) + 1
    return dist
