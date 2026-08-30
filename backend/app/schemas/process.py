from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel


class ProcessRequest(BaseModel):
    write_to_mysql: bool = True


class JobStatusResponse(BaseModel):
    job_id: str
    dataset_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    input_rows: Optional[int] = None
    clean_rows: Optional[int] = None
    rejected_rows: Optional[int] = None
    error_message: Optional[str] = None


class ProcessResultResponse(BaseModel):
    dataset_id: str
    job_id: str
    status: str
    stages_completed: List[str]
    clean_rows: int
    rejected_rows: int
    gold_tables_built: List[str]
    message: str
