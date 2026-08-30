import enum

from sqlalchemy import Column, String, BigInteger, Integer, DECIMAL, DateTime, Text, Enum
from sqlalchemy.sql import func

from app.database.session import Base


class DatasetStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROFILED = "profiled"
    MAPPING_REVIEW = "mapping_review"
    MAPPED = "mapped"
    QUALITY_CHECKED = "quality_checked"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Dataset(Base):
    __tablename__ = "datasets"

    dataset_id = Column(String(36), primary_key=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    detected_encoding = Column(String(32))
    row_count = Column(Integer)
    column_count = Column(Integer)

    status = Column(
        Enum(
            DatasetStatus,
            values_callable=lambda enum_class: [member.value for member in enum_class]
        ),
        nullable=False,
        default=DatasetStatus.UPLOADED,
    )

    quality_score = Column(DECIMAL(5, 2))
    uploaded_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    error_message = Column(Text, nullable=True)