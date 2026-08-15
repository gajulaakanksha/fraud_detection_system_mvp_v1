from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.batch_job import BatchJob
from app.models.user import User
from app.schemas.batch import BatchJobCreateResponse, BatchJobStatusResponse
from app.services import batch_service
from app.workers.batch_scoring_task import run_batch_scoring
from app.workers.queue import batch_queue

router = APIRouter(prefix="/transactions/batch", tags=["batch"])


def _not_found(job_id) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "not_found", "message": f"No batch job {job_id}"}},
    )


@router.get("/template")
def download_template() -> Response:
    return Response(
        content=batch_service.csv_template_bytes(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=valli_batch_template.csv"},
    )


@router.post("", response_model=BatchJobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchJobCreateResponse:
    file_bytes = await file.read()
    try:
        job, row_count = batch_service.create_batch_job(db, user.id, file.filename, file_bytes)
    except batch_service.CsvSchemaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "invalid_csv_schema", "message": str(exc)}},
        )

    db.add(AuditLog(
        actor_user_id=user.id, action="batch_score_submitted", entity_type="batch_job", entity_id=str(job.id),
        metadata_={"filename": file.filename, "row_count": row_count},
    ))
    db.commit()

    batch_queue.enqueue(run_batch_scoring, str(job.id), job_timeout="1h")

    return BatchJobCreateResponse(job_id=job.id, status=job.status, row_count_detected=row_count)


@router.get("/{job_id}", response_model=BatchJobStatusResponse)
def batch_status(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchJobStatusResponse:
    job = db.get(BatchJob, job_id)
    if job is None:
        raise _not_found(job_id)

    return BatchJobStatusResponse(
        job_id=job.id,
        status=job.status,
        original_filename=job.original_filename,
        row_count=job.row_count,
        rows_processed=batch_service.rows_processed_count(db, job.id) if job.status in ("running", "done") else None,
        decision_distribution=batch_service.decision_distribution(db, job.id) if job.status == "done" else None,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get("/{job_id}/download")
def download_result(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    job = db.get(BatchJob, job_id)
    if job is None:
        raise _not_found(job_id)
    if job.status != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "not_ready", "message": f"Job status is '{job.status}', not 'done' yet."}},
        )
    path = Path(job.output_uri)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "result_missing", "message": "Job marked done but result file is missing."}},
        )
    return FileResponse(path, media_type="text/csv", filename=f"{job_id}_scored.csv")
