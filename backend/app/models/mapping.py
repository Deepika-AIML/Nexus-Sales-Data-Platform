import enum

from sqlalchemy import (
    Column,
    String,
    BigInteger,
    DECIMAL,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.database.session import Base


class MappingSuggestedStatus(str, enum.Enum):
    AUTO_MAPPED = "auto_mapped"
    REVIEW = "review"
    UNMAPPED = "unmapped"


class MappingFinalStatus(str, enum.Enum):
    AUTO_MAPPED = "auto_mapped"
    REVIEW = "review"
    UNMAPPED = "unmapped"
    MANUAL = "manual"
    CONFIRMED = "confirmed"
    REMOVED = "removed"


class ColumnMapping(Base):
    __tablename__ = "column_mappings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    dataset_id = Column(
        String(36),
        ForeignKey("datasets.dataset_id", ondelete="CASCADE"),
        nullable=False,
    )

    source_column = Column(String(255), nullable=False)

    canonical_field = Column(String(64), nullable=True)

    confidence = Column(
        DECIMAL(5, 2),
        nullable=False,
        default=0,
    )

    suggested_status = Column(
        Enum(
            MappingSuggestedStatus,
            values_callable=lambda enum_class: [e.value for e in enum_class],
            name="mappingsuggestedstatus",
        ),
        nullable=False,
    )

    final_status = Column(
        Enum(
            MappingFinalStatus,
            values_callable=lambda enum_class: [e.value for e in enum_class],
            name="mappingfinalstatus",
        ),
        nullable=False,
    )

    is_user_modified = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )