from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.history import HistoryResponse, HistoryItem
from app.services import dataset_service

router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("", response_model=HistoryResponse)
def get_history(db: Session = Depends(get_db)):
    datasets = dataset_service.list_history(db)
    items = [
        HistoryItem(
            dataset_id=d.dataset_id, original_filename=d.original_filename, uploaded_at=d.uploaded_at,
            row_count=d.row_count, column_count=d.column_count,
            quality_score=float(d.quality_score) if d.quality_score is not None else None,
            status=d.status.value,
        ) for d in datasets
    ]
    return HistoryResponse(items=items, total=len(items))
