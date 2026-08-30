from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetStatus
from app.core.exceptions import DatasetNotFoundError


def create_dataset(
    db: Session,
    dataset_id: str,
    original_filename: str,
    stored_filename: str,
    file_size_bytes: int,
    detected_encoding: str,
    row_count: int,
    column_count: int,
) -> Dataset:
    ds = Dataset(
        dataset_id=dataset_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_size_bytes=file_size_bytes,
        detected_encoding=detected_encoding,
        row_count=row_count,
        column_count=column_count,
        status=DatasetStatus.UPLOADED,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def get_dataset_or_404(db: Session, dataset_id: str) -> Dataset:
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise DatasetNotFoundError(dataset_id)
    return ds


def update_status(db: Session, dataset_id: str, status: DatasetStatus, **fields) -> Dataset:
    ds = get_dataset_or_404(db, dataset_id)
    ds.status = status
    for k, v in fields.items():
        setattr(ds, k, v)
    db.commit()
    db.refresh(ds)
    return ds


def set_profile_stats(db: Session, dataset_id: str, row_count: int, column_count: int) -> Dataset:
    return update_status(db, dataset_id, DatasetStatus.PROFILED, row_count=row_count, column_count=column_count)


def list_history(db: Session, limit: int = 100) -> list[Dataset]:
    return (
        db.query(Dataset)
        .order_by(Dataset.uploaded_at.desc())
        .limit(limit)
        .all()
    )
