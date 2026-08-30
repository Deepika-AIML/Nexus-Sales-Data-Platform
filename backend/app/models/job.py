import enum

from sqlalchemy import Column, String, Integer, DECIMAL, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func

from app.database.session import Base


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    PROFILING = "profiling"
    MAPPING = "mapping"
    VALIDATING = "validating"
    CLEANING = "cleaning"
    TRANSFORMING = "transforming"
    BUILDING_ANALYTICS_MODEL = "building_analytics_model"
    GENERATING_INSIGHTS = "generating_insights"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    job_id = Column(String(36), primary_key=True)
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.dataset_id", ondelete="CASCADE"),
        nullable=False
    )

    status = Column(
        Enum(
            JobStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=JobStatus.QUEUED,
    )

    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(DECIMAL(10, 2), nullable=True)
    input_rows = Column(Integer, nullable=True)
    clean_rows = Column(Integer, nullable=True)
    rejected_rows = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)