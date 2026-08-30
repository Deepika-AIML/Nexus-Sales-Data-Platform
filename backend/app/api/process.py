from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.process import ProcessRequest
from app.services import processing_service

router = APIRouter(prefix="/api/process", tags=["Processing"])


@router.post("/{dataset_id}", status_code=202)
def start_processing(dataset_id: str, request: ProcessRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Validates synchronously (fails fast on a missing required field), then
    schedules the actual Bronze->Silver->Gold Spark run as a background
    task and returns immediately with a job_id to poll via
    GET /api/results/{dataset_id} (spec section 23: processing must not
    appear to freeze the UI; polling-based status is acceptable for V1).
    """
    job = processing_service.validate_and_queue(db, dataset_id)
    background_tasks.add_task(
        processing_service.execute_processing_job, dataset_id, job.job_id, request.write_to_mysql,
    )
    return {
        "dataset_id": dataset_id,
        "job_id": job.job_id,
        "status": job.status.value,
        "message": "Processing started. Poll GET /api/results/{dataset_id} for status.",
    }
