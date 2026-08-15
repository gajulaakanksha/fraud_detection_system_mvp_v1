import uuid
from datetime import datetime

from pydantic import BaseModel


class BatchJobCreateResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    row_count_detected: int


class BatchJobStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    original_filename: str
    row_count: int | None = None
    rows_processed: int | None = None
    decision_distribution: dict[str, int] | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
