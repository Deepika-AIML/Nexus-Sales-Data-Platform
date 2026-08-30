from typing import List

from pydantic import BaseModel


class ColumnProfileSchema(BaseModel):
    name: str
    inferred_type: str
    non_null_count: int
    null_count: int
    null_pct: float
    unique_count: int
    sample_values: List[str]


class ProfileResponse(BaseModel):
    dataset_id: str
    filename: str
    file_size_bytes: int
    detected_encoding: str
    row_count: int
    column_count: int
    duplicate_row_count: int
    columns: List[ColumnProfileSchema]
