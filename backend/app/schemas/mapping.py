from typing import List, Optional, Dict

from pydantic import BaseModel


class FieldCandidateSchema(BaseModel):
    canonical_field: str
    confidence: float
    signals: Dict[str, float]


class ColumnMappingSuggestionSchema(BaseModel):
    source_column: str
    normalized: str
    best_field: Optional[str]
    confidence: float
    status: str
    candidates: List[FieldCandidateSchema]
    sample_values: List[str]


class MappingConflictSchema(BaseModel):
    canonical_field: str
    competing_source_columns: List[str]
    message: str


class MappingSuggestResponse(BaseModel):
    dataset_id: str
    suggestions: List[ColumnMappingSuggestionSchema]
    conflicts: List[MappingConflictSchema]
    core_fields: List[str]
    recommended_fields: List[str]
    optional_fields: List[str]


class ConfirmedMappingEntry(BaseModel):
    source_column: str
    canonical_field: Optional[str] = None  # null/omitted = leave unmapped


class ConfirmMappingRequest(BaseModel):
    mappings: List[ConfirmedMappingEntry]


class ConfirmMappingResponse(BaseModel):
    dataset_id: str
    confirmed_mapping: Dict[str, str]
    missing_required_fields: List[str]
    missing_optional_fields: List[str]
    can_proceed: bool
    message: str
