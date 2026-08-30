from typing import List, Optional

from pydantic import BaseModel


class QualityIssueSchema(BaseModel):
    code: str
    field: Optional[str]
    severity: str
    affected_rows: int
    description: str


class QualityReportSchema(BaseModel):
    dataset_id: str
    score_overall: float
    completeness: float
    uniqueness: float
    validity: float
    consistency: float
    schema_match: float
    row_count: int
    issues: List[QualityIssueSchema]
