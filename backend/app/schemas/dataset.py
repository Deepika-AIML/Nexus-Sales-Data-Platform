from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    dataset_id: str
    original_filename: str
    file_size_bytes: int
    detected_encoding: str
    row_count: int
    column_count: int
    message: str = "Dataset uploaded successfully."


class DatasetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_id: str
    original_filename: str
    file_size_bytes: int
    detected_encoding: Optional[str] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    status: str
    quality_score: Optional[float] = None
    uploaded_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
