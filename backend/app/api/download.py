import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.services import dataset_service, report_service

router = APIRouter(prefix="/api/download", tags=["Downloads"])
settings = get_settings()


@router.get("/{dataset_id}/clean")
def download_clean(dataset_id: str, db: Session = Depends(get_db)):
    ds = dataset_service.get_dataset_or_404(db, dataset_id)
    path = os.path.join(settings.OUTPUTS_DIR, f"{dataset_id}__clean.csv")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Clean dataset is not available yet. Run processing first.")
    filename = f"{os.path.splitext(ds.original_filename)[0]}_clean.csv"
    return FileResponse(path, media_type="text/csv", filename=filename)


@router.get("/{dataset_id}/rejected")
def download_rejected(dataset_id: str, db: Session = Depends(get_db)):
    ds = dataset_service.get_dataset_or_404(db, dataset_id)
    path = os.path.join(settings.REJECTED_DIR, f"{dataset_id}__rejected.csv")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Rejected records file is not available yet. Run processing first.")
    filename = f"{os.path.splitext(ds.original_filename)[0]}_rejected.csv"
    return FileResponse(path, media_type="text/csv", filename=filename)


@router.get("/{dataset_id}/quality-report")
def download_quality_report(dataset_id: str, db: Session = Depends(get_db)):
    dataset_service.get_dataset_or_404(db, dataset_id)
    path = report_service.build_quality_report_csv(db, dataset_id)
    return FileResponse(path, media_type="text/csv", filename="data_quality_report.csv")


@router.get("/{dataset_id}/mapping-report")
def download_mapping_report(dataset_id: str, db: Session = Depends(get_db)):
    dataset_service.get_dataset_or_404(db, dataset_id)
    path = report_service.build_mapping_report_csv(db, dataset_id)
    return FileResponse(path, media_type="text/csv", filename="column_mapping_report.csv")
