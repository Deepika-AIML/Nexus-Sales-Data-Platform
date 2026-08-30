from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.data_engine import quality_engine
from app.schemas.profile import ProfileResponse
from app.services import storage_service, dataset_service

router = APIRouter(prefix="/api/profile", tags=["Profiling"])


@router.get("/{dataset_id}", response_model=ProfileResponse)
def get_profile(dataset_id: str, db: Session = Depends(get_db)):
    ds = dataset_service.get_dataset_or_404(db, dataset_id)
    df = storage_service.load_raw_dataframe(dataset_id, ds.stored_filename, ds.detected_encoding)

    profile = quality_engine.profile_dataset(
        df, filename=ds.original_filename, file_size_bytes=ds.file_size_bytes,
        detected_encoding=ds.detected_encoding,
    )
    dataset_service.set_profile_stats(db, dataset_id, row_count=profile["row_count"], column_count=profile["column_count"])

    return ProfileResponse(dataset_id=dataset_id, **profile)
