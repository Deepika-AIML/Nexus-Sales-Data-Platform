"""
Processing service — the orchestration layer FastAPI's `/api/process`
route calls into. This is deliberately thin: every real transformation
happens in `app.data_engine.spark.*` (PySpark) or `app.data_engine.*`
(pandas engines for the interactive review stages). This module's jobs are:
(1) validate synchronously so a doomed request (e.g. missing required
field) fails fast instead of silently failing in the background, (2) drive
the stage-by-stage `processing_jobs` status the UI polls, (3) guarantee
re-processing a dataset is idempotent in MySQL, and (4) produce the
downloadable CSV artifacts.

FastAPI should orchestrate the workflow; the data-engineering layer should
perform the processing (spec section 19) — this file is that boundary.

Two entry points, split deliberately:
  - `validate_and_queue(db, dataset_id)` runs on the request thread inside
    the FastAPI route, using the request's own DB session. It does the fast
    required-field check and creates the `queued` job row.
  - `execute_processing_job(dataset_id, job_id)` is handed to
    `BackgroundTasks.add_task(...)` by the route. FastAPI runs sync
    background tasks in a worker thread, so this function opens its OWN
    SQLAlchemy session (`SessionLocal()`) rather than reusing the request's
    session, which is not safe to share across threads/requests.
"""
import os
import time
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import RequiredFieldMissingError
from app.core.logging_config import get_logger
from app.data_engine import mapping_engine
from app.database.session import SessionLocal
from app.models.job import ProcessingJob, JobStatus
from app.models.dataset import DatasetStatus
from app.services import dataset_service, mapping_service

logger = get_logger(__name__)
settings = get_settings()

GOLD_TABLES = ("gold_fact_sales", "gold_dim_date", "gold_dim_product", "gold_dim_customer", "gold_dim_location")


def validate_and_queue(db: Session, dataset_id: str) -> ProcessingJob:
    """Runs on the request thread. Raises RequiredFieldMissingError (422)
    immediately if the confirmed mapping can't support processing — the
    client should never have to poll to discover that."""
    dataset_service.get_dataset_or_404(db, dataset_id)
    confirmed_mapping = mapping_service.get_confirmed_mapping(db, dataset_id)

    missing_required = mapping_engine.missing_required_fields(confirmed_mapping)
    if missing_required:
        raise RequiredFieldMissingError(
            f"Required field '{missing_required[0]}' could not be identified from this dataset."
        )

    job = ProcessingJob(job_id=str(uuid.uuid4()), dataset_id=dataset_id, status=JobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)

    dataset_service.update_status(db, dataset_id, DatasetStatus.PROCESSING)
    return job


def _update_job(db: Session, job: ProcessingJob, status: JobStatus, **fields) -> None:
    job.status = status
    for k, v in fields.items():
        setattr(job, k, v)
    db.commit()


def _clear_prior_gold_rows(db: Session, dataset_id: str) -> None:
    """
    Spark's JDBC writer only knows how to append or overwrite an entire
    table — it has no concept of 'replace rows matching this dataset_id'.
    Reprocessing the same dataset must still be idempotent (no duplicate
    Gold rows), so we delete this dataset's previous Gold rows via a plain
    SQL statement immediately before Spark appends the fresh ones.
    """
    for table in GOLD_TABLES:
        try:
            db.execute(text(f"DELETE FROM {table} WHERE _dataset_id = :did"), {"did": dataset_id})
        except Exception as e:  # table may not exist yet on a fresh DB before first run
            logger.info("Skipping cleanup for %s (%s)", table, e)
    db.commit()


def execute_processing_job(dataset_id: str, job_id: str, write_to_mysql: bool = True) -> None:
    """The actual Bronze -> Silver -> Gold run. Runs in a background
    thread — owns its own DB session and its own SparkSession end to end."""
    from app.data_engine.spark.spark_session import get_spark_session
    from app.data_engine.spark.bronze import ingest_to_bronze
    from app.data_engine.spark.silver import run_silver_stage
    from app.data_engine.spark.gold import build_gold_layer, write_gold_to_mysql
    from app.data_engine.spark.csv_export import write_single_csv

    db = SessionLocal()
    spark = None
    start = time.monotonic()
    try:
        job = db.get(ProcessingJob, job_id)
        ds = dataset_service.get_dataset_or_404(db, dataset_id)
        confirmed_mapping = mapping_service.get_confirmed_mapping(db, dataset_id)
        raw_csv_path = os.path.join(settings.RAW_DIR, ds.stored_filename)

        spark = get_spark_session(app_name=f"nexus-{dataset_id}")

        _update_job(db, job, JobStatus.CLEANING)
        bronze_df, _bronze_path = ingest_to_bronze(
            spark, raw_csv_path, dataset_id, ds.detected_encoding or "utf-8", settings.BRONZE_DIR,
        )
        silver_summary = run_silver_stage(spark, bronze_df, confirmed_mapping, dataset_id, settings.SILVER_DIR)

        _update_job(db, job, JobStatus.TRANSFORMING)
        silver_clean_df = spark.read.parquet(silver_summary["clean_path"])
        silver_rejected_df = spark.read.parquet(silver_summary["rejected_path"])
        gold_summary = build_gold_layer(spark, silver_clean_df, dataset_id, settings.GOLD_DIR)

        _update_job(db, job, JobStatus.BUILDING_ANALYTICS_MODEL)
        if write_to_mysql:
            _clear_prior_gold_rows(db, dataset_id)
            write_gold_to_mysql(gold_summary["dataframes"], dataset_id)

        # Downloadable artifacts (spec section 28).
        os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
        os.makedirs(settings.REJECTED_DIR, exist_ok=True)
        clean_csv_path = os.path.join(settings.OUTPUTS_DIR, f"{dataset_id}__clean.csv")
        rejected_csv_path = os.path.join(settings.REJECTED_DIR, f"{dataset_id}__rejected.csv")
        write_single_csv(silver_clean_df, clean_csv_path)
        write_single_csv(silver_rejected_df, rejected_csv_path)

        _update_job(db, job, JobStatus.GENERATING_INSIGHTS)
        # Insights/recommendations are computed on demand from Gold data by
        # /api/insights rather than persisted here — the underlying Gold
        # rows they read are now in place, so this stage is a checkpoint
        # rather than additional heavy computation.

        duration = round(time.monotonic() - start, 2)
        _update_job(
            db, job, JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=duration,
            input_rows=silver_summary["input_rows"],
            clean_rows=silver_summary["clean_rows"],
            rejected_rows=silver_summary["rejected_rows"],
        )
        dataset_service.update_status(db, dataset_id, DatasetStatus.PROCESSED)

    except Exception as e:  # noqa: BLE001 — background task: must never raise, only record failure
        logger.error("Processing failed for dataset %s: %s\n%s", dataset_id, e, traceback.format_exc())
        try:
            job = db.get(ProcessingJob, job_id)
            if job is not None:
                _update_job(
                    db, job, JobStatus.FAILED,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=round(time.monotonic() - start, 2),
                    error_message="Processing could not be completed. Your original dataset remains unchanged.",
                )
            dataset_service.update_status(db, dataset_id, DatasetStatus.FAILED, error_message="Processing failed.")
        except Exception:  # noqa: BLE001
            logger.error("Failed to record processing failure for dataset %s", dataset_id)
    finally:
        if spark is not None:
            spark.stop()
        db.close()


def get_job_status(db: Session, dataset_id: str) -> ProcessingJob | None:
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.dataset_id == dataset_id)
        .order_by(ProcessingJob.started_at.desc())
        .first()
    )
