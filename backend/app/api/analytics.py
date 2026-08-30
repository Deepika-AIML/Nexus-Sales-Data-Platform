from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.analytics import AnalyticsResponse
from app.services import dataset_service
from app.analytics import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/{dataset_id}", response_model=AnalyticsResponse)
def get_analytics(dataset_id: str, db: Session = Depends(get_db)):
    dataset_service.get_dataset_or_404(db, dataset_id)
    metrics = analytics_service.get_analytics(db, dataset_id)
    return AnalyticsResponse(dataset_id=dataset_id, metrics=metrics)
