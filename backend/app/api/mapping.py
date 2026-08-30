from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.data_engine.canonical_schema import CORE_FIELDS, RECOMMENDED_FIELDS, OPTIONAL_FIELDS
from app.models.mapping import ColumnMapping
from app.schemas.mapping import (
    MappingSuggestResponse, ColumnMappingSuggestionSchema, FieldCandidateSchema,
    MappingConflictSchema, ConfirmMappingRequest, ConfirmMappingResponse,
)
from app.services import storage_service, dataset_service, mapping_service

router = APIRouter(prefix="/api/mapping", tags=["Column Mapping"])


@router.post("/{dataset_id}", response_model=MappingSuggestResponse)
def generate_mapping_suggestions(dataset_id: str, db: Session = Depends(get_db)):
    ds = dataset_service.get_dataset_or_404(db, dataset_id)
    df = storage_service.load_raw_dataframe(dataset_id, ds.stored_filename, ds.detected_encoding)
    result = mapping_service.generate_and_persist_suggestions(db, dataset_id, df)

    return MappingSuggestResponse(
        dataset_id=dataset_id,
        suggestions=[
            ColumnMappingSuggestionSchema(
                source_column=s.source_column, normalized=s.normalized, best_field=s.best_field,
                confidence=s.confidence, status=s.status, sample_values=s.sample_values,
                candidates=[FieldCandidateSchema(canonical_field=c.canonical_field, confidence=c.confidence, signals=c.signals) for c in s.candidates],
            ) for s in result.suggestions
        ],
        conflicts=[MappingConflictSchema(**c) for c in result.conflicts],
        core_fields=CORE_FIELDS, recommended_fields=RECOMMENDED_FIELDS, optional_fields=OPTIONAL_FIELDS,
    )


@router.get("/{dataset_id}", response_model=MappingSuggestResponse)
def get_current_mapping(dataset_id: str, db: Session = Depends(get_db)):
    dataset_service.get_dataset_or_404(db, dataset_id)
    rows = db.query(ColumnMapping).filter(ColumnMapping.dataset_id == dataset_id).all()

    return MappingSuggestResponse(
        dataset_id=dataset_id,
        suggestions=[
            ColumnMappingSuggestionSchema(
                source_column=r.source_column, normalized=r.source_column.lower(),
                best_field=r.canonical_field, confidence=float(r.confidence),
                status=r.final_status.value, sample_values=[], candidates=[],
            ) for r in rows
        ],
        conflicts=[],
        core_fields=CORE_FIELDS, recommended_fields=RECOMMENDED_FIELDS, optional_fields=OPTIONAL_FIELDS,
    )


@router.post("/{dataset_id}/confirm", response_model=ConfirmMappingResponse)
def confirm_mapping(dataset_id: str, request: ConfirmMappingRequest, db: Session = Depends(get_db)):
    dataset_service.get_dataset_or_404(db, dataset_id)
    result = mapping_service.confirm_mapping(db, dataset_id, request.mappings)

    if result["can_proceed"]:
        message = "Mapping confirmed. All required fields were identified."
    else:
        field = result["missing_required_fields"][0]
        message = f"Required field '{field}' could not be identified from this dataset."

    return ConfirmMappingResponse(dataset_id=dataset_id, message=message, **result)
