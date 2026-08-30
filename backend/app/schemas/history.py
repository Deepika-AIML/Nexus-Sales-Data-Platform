from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class HistoryItem(BaseModel):
    dataset_id: str
    original_filename: str
    uploaded_at: datetime
    row_count: Optional[int]
    column_count: Optional[int]
    quality_score: Optional[float]
    status: str


class HistoryResponse(BaseModel):
    items: List[HistoryItem]
    total: int
