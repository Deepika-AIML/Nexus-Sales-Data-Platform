import enum

from sqlalchemy import Column, String, BigInteger, Integer, DECIMAL, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func

from app.database.session import Base


class IssueSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class QualityReport(Base):
    __tablename__ = "quality_reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id = Column(String(36), ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    score_overall = Column(DECIMAL(5, 2), nullable=False)
    completeness = Column(DECIMAL(5, 2), nullable=False)
    uniqueness = Column(DECIMAL(5, 2), nullable=False)
    validity = Column(DECIMAL(5, 2), nullable=False)
    consistency = Column(DECIMAL(5, 2), nullable=False)
    schema_match = Column(DECIMAL(5, 2), nullable=False)
    generated_at = Column(DateTime, server_default=func.now())


class QualityIssue(Base):
    __tablename__ = "quality_issues"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id = Column(String(36), ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    code = Column(String(64), nullable=False)
    field = Column(String(64), nullable=True)
    severity = Column(Enum(IssueSeverity), nullable=False)
    affected_rows = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
