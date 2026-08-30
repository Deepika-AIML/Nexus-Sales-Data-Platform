from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.quality import QualityReportSchema, QualityIssueSchema
from app.services import storage_service, dataset_service, mapping_service, quality_service

router = APIRouter(prefix="/api/quality", tags=["Data Quality"])


@router.get("/{dataset_id}", response_model=QualityReportSchema)
def get_quality_report(dataset_id: str, db: Session = Depends(get_db)):
    ds = dataset_service.get_dataset_or_404(db, dataset_id)
    df = storage_service.load_raw_dataframe(dataset_id, ds.stored_filename, ds.detected_encoding)
    confirmed_mapping = mapping_service.get_confirmed_mapping(db, dataset_id)

    report = quality_service.assess_and_persist(db, dataset_id, df, confirmed_mapping)

    return QualityReportSchema(
        dataset_id=dataset_id,
        score_overall=report.score_overall,
        completeness=report.completeness,
        uniqueness=report.uniqueness,
        validity=report.validity,
        consistency=report.consistency,
        schema_match=report.schema_match,
        row_count=report.row_count,
        issues=[QualityIssueSchema(code=i.code, field=i.field, severity=i.severity, affected_rows=i.affected_rows, description=i.description) for i in report.issues],
    )
