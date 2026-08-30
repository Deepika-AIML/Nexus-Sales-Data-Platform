import pandas as pd
from sqlalchemy.orm import Session

from app.data_engine import quality_engine, mapping_engine
from app.models.dataset import DatasetStatus
from app.models.quality import QualityReport, QualityIssue, IssueSeverity
from app.services import dataset_service


def assess_and_persist(db: Session, dataset_id: str, raw_df: pd.DataFrame, confirmed_mapping: dict[str, str]) -> quality_engine.QualityReport:
    canonical_df = mapping_engine.apply_confirmed_mapping(raw_df, confirmed_mapping)
    report = quality_engine.assess_quality(canonical_df, confirmed_mapping)

    # Replace any prior report for this dataset (idempotent re-run).
    db.query(QualityIssue).filter(QualityIssue.dataset_id == dataset_id).delete()
    db.query(QualityReport).filter(QualityReport.dataset_id == dataset_id).delete()

    db.add(QualityReport(
        dataset_id=dataset_id,
        score_overall=report.score_overall,
        completeness=report.completeness,
        uniqueness=report.uniqueness,
        validity=report.validity,
        consistency=report.consistency,
        schema_match=report.schema_match,
    ))
    for issue in report.issues:
        db.add(QualityIssue(
            dataset_id=dataset_id,
            code=issue.code,
            field=issue.field,
            severity=IssueSeverity(issue.severity),
            affected_rows=issue.affected_rows,
            description=issue.description,
        ))
    db.commit()

    dataset_service.update_status(
        db, dataset_id, DatasetStatus.QUALITY_CHECKED, quality_score=report.score_overall
    )
    return report


def get_latest_report_dict(db: Session, dataset_id: str) -> dict | None:
    report = (
        db.query(QualityReport)
        .filter(QualityReport.dataset_id == dataset_id)
        .order_by(QualityReport.generated_at.desc())
        .first()
    )
    if report is None:
        return None
    issues = db.query(QualityIssue).filter(QualityIssue.dataset_id == dataset_id).all()
    return {
        "score_overall": float(report.score_overall),
        "completeness": float(report.completeness),
        "uniqueness": float(report.uniqueness),
        "validity": float(report.validity),
        "consistency": float(report.consistency),
        "schema_match": float(report.schema_match),
        "issues": [
            {
                "code": i.code, "field": i.field, "severity": i.severity.value,
                "affected_rows": i.affected_rows, "description": i.description,
            } for i in issues
        ],
    }
