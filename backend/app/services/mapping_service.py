import pandas as pd
from sqlalchemy.orm import Session

from app.data_engine import mapping_engine
from app.models.dataset import DatasetStatus
from app.models.mapping import ColumnMapping, MappingSuggestedStatus, MappingFinalStatus
from app.schemas.mapping import ConfirmedMappingEntry
from app.services import dataset_service
from app.core.exceptions import MappingNotConfirmedError


def generate_and_persist_suggestions(db: Session, dataset_id: str, df: pd.DataFrame) -> mapping_engine.MappingResult:
    result = mapping_engine.suggest_mapping(df)

    # Replace any prior suggestions for this dataset (idempotent re-profile).
    db.query(ColumnMapping).filter(ColumnMapping.dataset_id == dataset_id).delete()

    for s in result.suggestions:
        db.add(ColumnMapping(
            dataset_id=dataset_id,
            source_column=s.source_column,
            canonical_field=s.best_field,
            confidence=s.confidence,
            suggested_status=MappingSuggestedStatus(s.status),
            final_status=MappingFinalStatus(s.status),  # defaults to the suggestion until user confirms
            is_user_modified=False,
        ))
    db.commit()

    dataset_service.update_status(db, dataset_id, DatasetStatus.MAPPING_REVIEW)
    return result


def confirm_mapping(db: Session, dataset_id: str, entries: list[ConfirmedMappingEntry]) -> dict:
    rows = {r.source_column: r for r in db.query(ColumnMapping).filter(ColumnMapping.dataset_id == dataset_id).all()}
    if not rows:
        raise MappingNotConfirmedError("No mapping suggestions found for this dataset. Run profiling first.")

    chosen_fields: dict[str, str] = {}
    for entry in entries:
        row = rows.get(entry.source_column)
        if row is None:
            continue  # ignore references to columns that don't exist for this dataset
        was_modified = (row.canonical_field or None) != (entry.canonical_field or None)
        row.canonical_field = entry.canonical_field
        row.is_user_modified = row.is_user_modified or was_modified
        row.final_status = (
            MappingFinalStatus.REMOVED if not entry.canonical_field else
            (MappingFinalStatus.MANUAL if was_modified else MappingFinalStatus.CONFIRMED)
        )
        if entry.canonical_field:
            chosen_fields[entry.source_column] = entry.canonical_field

    # Any mapping not referenced in the request keeps its prior (suggested) mapping as-is.
    for source_col, row in rows.items():
        if row.canonical_field and row.final_status not in (MappingFinalStatus.REMOVED,):
            chosen_fields.setdefault(source_col, row.canonical_field)

    db.commit()

    missing_required = mapping_engine.missing_required_fields(chosen_fields)
    missing_optional = mapping_engine.missing_optional_fields(chosen_fields)
    can_proceed = len(missing_required) == 0

    dataset_service.update_status(
        db, dataset_id,
        DatasetStatus.MAPPED if can_proceed else DatasetStatus.MAPPING_REVIEW,
    )

    return {
        "confirmed_mapping": chosen_fields,
        "missing_required_fields": missing_required,
        "missing_optional_fields": missing_optional,
        "can_proceed": can_proceed,
    }


def get_confirmed_mapping(db: Session, dataset_id: str) -> dict[str, str]:
    rows = (
        db.query(ColumnMapping)
        .filter(
            ColumnMapping.dataset_id == dataset_id,
            ColumnMapping.canonical_field.isnot(None),
            ColumnMapping.final_status != MappingFinalStatus.REMOVED,
        )
        .all()
    )
    return {r.source_column: r.canonical_field for r in rows}
