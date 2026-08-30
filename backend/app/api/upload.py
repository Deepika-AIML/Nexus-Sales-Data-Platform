from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.dataset import UploadResponse
from app.services import storage_service, dataset_service
from app.core.logging_config import get_logger

router = APIRouter(prefix="/api/upload", tags=["Upload"])
logger = get_logger(__name__)


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()

    # Basic file-level validation ONLY (extension, size, readability) —
    # dirty/duplicate/messy data is never a reason to reject at this stage.
    storage_service.validate_upload(file.filename, content)
    df, encoding = storage_service.detect_encoding_and_read(content)

    dataset_id = storage_service.new_dataset_id()
    stored_filename = storage_service.save_raw_file(dataset_id, file.filename, content)

    ds = dataset_service.create_dataset(
        db,
        dataset_id=dataset_id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_size_bytes=len(content),
        detected_encoding=encoding,
        row_count=df.shape[0],
        column_count=df.shape[1],
    )
    logger.info("Uploaded dataset %s (%s rows, %s cols, encoding=%s)", ds.dataset_id, ds.row_count, ds.column_count, encoding)

    return UploadResponse(
        dataset_id=ds.dataset_id,
        original_filename=ds.original_filename,
        file_size_bytes=ds.file_size_bytes,
        detected_encoding=encoding,
        row_count=ds.row_count,
        column_count=ds.column_count,
    )
