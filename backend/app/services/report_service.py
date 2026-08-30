import os

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.mapping import ColumnMapping
from app.models.quality import QualityReport, QualityIssue

settings = get_settings()


def build_mapping_report_csv(db: Session, dataset_id: str) -> str:
    rows = db.query(ColumnMapping).filter(ColumnMapping.dataset_id == dataset_id).all()
    df = pd.DataFrame([{
        "source_column": r.source_column,
        "nexus_field": r.canonical_field or "",
        "confidence": float(r.confidence),
        "suggested_status": r.suggested_status.value,
        "final_status": r.final_status.value,
        "user_modified": r.is_user_modified,
    } for r in rows])

    os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUTS_DIR, f"{dataset_id}__mapping_report.csv")
    df.to_csv(path, index=False)
    return path


def build_quality_report_csv(db: Session, dataset_id: str) -> str:
    report = (
        db.query(QualityReport)
        .filter(QualityReport.dataset_id == dataset_id)
        .order_by(QualityReport.generated_at.desc())
        .first()
    )
    issues = db.query(QualityIssue).filter(QualityIssue.dataset_id == dataset_id).all()

    summary_rows = []
    if report:
        summary_rows = [{
            "metric": m, "value": float(getattr(report, m))
        } for m in ("score_overall", "completeness", "uniqueness", "validity", "consistency", "schema_match")]

    issue_rows = [{
        "code": i.code, "field": i.field or "", "severity": i.severity.value,
        "affected_rows": i.affected_rows, "description": i.description,
    } for i in issues]

    os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUTS_DIR, f"{dataset_id}__quality_report.csv")
    with open(path, "w") as f:
        f.write("# Data Quality Summary\n")
        pd.DataFrame(summary_rows).to_csv(f, index=False)
        f.write("\n# Data Quality Issues\n")
        pd.DataFrame(issue_rows).to_csv(f, index=False)
    return path
