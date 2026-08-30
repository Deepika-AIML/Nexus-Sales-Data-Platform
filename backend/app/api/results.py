from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.process import JobStatusResponse
from app.services import processing_service, dataset_service

router = APIRouter(prefix="/api/results", tags=["Processing Results"])


@router.get("/{dataset_id}", response_model=JobStatusResponse)
def get_results(dataset_id: str, db: Session = Depends(get_db)):
    dataset_service.get_dataset_or_404(db, dataset_id)
    job = processing_service.get_job_status(db, dataset_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No processing job has been started for this dataset yet.")

    return JobStatusResponse(
        job_id=job.job_id, dataset_id=job.dataset_id, status=job.status.value,
        started_at=job.started_at, completed_at=job.completed_at,
        duration_seconds=float(job.duration_seconds) if job.duration_seconds is not None else None,
        input_rows=job.input_rows, clean_rows=job.clean_rows, rejected_rows=job.rejected_rows,
        error_message=job.error_message,
    )
