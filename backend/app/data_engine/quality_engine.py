"""
Nexus Data Quality Engine
==========================
Two responsibilities, kept separate on purpose:

1. `profile_dataset(df)` — dataset-level profiling that runs on the RAW
   uploaded file, before any mapping is confirmed. This powers the
   Data Profiling page (row/column counts, per-column null %, inferred
   type, uniqueness, sample values).

2. `assess_quality(canonical_df, mapping)` — runs AFTER column mapping is
   confirmed, against the canonical-shaped view of the data. This is where
   business-rule validity checks live (sales >= 0, quantity > 0, ship_date
   >= order_date, etc.) because those rules are only meaningful once we know
   which column IS `sales`, `quantity`, etc.

Both are pure pandas — no Spark, no FastAPI — so they're fast enough to run
synchronously inside a request/response cycle for interactive review, and
unit-testable in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import warnings

import pandas as pd
import numpy as np

from app.data_engine.canonical_schema import CANONICAL_SCHEMA, FieldType
from app.data_engine.date_utils import parse_dates_robust


# ---------------------------------------------------------------------------
# Stage 1: raw dataset profiling (pre-mapping)
# ---------------------------------------------------------------------------

def _infer_dtype_label(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    sample = non_null.astype(str).str.strip()
    numeric_hits = sample.str.match(r"^-?\$?\d[\d,]*\.?\d*%?$").mean()
    date_hits = 0.0
    try:
        date_hits = parse_dates_robust(sample.head(50)).notna().mean()
    except Exception:
        pass
    if numeric_hits > 0.9:
        return "numeric"
    if date_hits > 0.9:
        return "date"
    if sample.nunique() <= max(20, int(0.05 * len(sample))):
        return "categorical"
    return "text"


def profile_dataset(df: pd.DataFrame, filename: str = "", file_size_bytes: int = 0,
                     detected_encoding: str = "") -> dict:
    n_rows, n_cols = df.shape
    columns_profile = []
    for col in df.columns:
        s = df[col]
        non_null = s.dropna()
        null_count = int(s.isna().sum())
        columns_profile.append({
            "name": col,
            "inferred_type": _infer_dtype_label(s),
            "non_null_count": int(non_null.shape[0]),
            "null_count": null_count,
            "null_pct": round(100 * null_count / n_rows, 2) if n_rows else 0.0,
            "unique_count": int(non_null.nunique()),
            "sample_values": non_null.astype(str).head(5).tolist(),
        })

    duplicate_rows = int(df.duplicated().sum())

    return {
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "detected_encoding": detected_encoding,
        "row_count": n_rows,
        "column_count": n_cols,
        "duplicate_row_count": duplicate_rows,
        "columns": columns_profile,
    }


# ---------------------------------------------------------------------------
# Stage 2: post-mapping quality assessment (business-rule validity)
# ---------------------------------------------------------------------------

@dataclass
class QualityIssue:
    code: str
    field: Optional[str]
    severity: str          # "critical" | "warning" | "info"
    affected_rows: int
    description: str


@dataclass
class QualityReport:
    score_overall: float
    completeness: float
    uniqueness: float
    validity: float
    consistency: float
    schema_match: float
    issues: list  # list[QualityIssue]
    row_count: int


def _numeric_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def assess_quality(canonical_df: pd.DataFrame, mapping: dict[str, str]) -> QualityReport:
    n_rows = len(canonical_df)
    issues: list[QualityIssue] = []
    mapped_fields = [v for v in mapping.values() if v]

    # ---- Completeness: null rate across mapped canonical fields ----------
    if mapped_fields:
        null_rates = []
        for f in mapped_fields:
            if f in canonical_df.columns:
                rate = canonical_df[f].isna().mean()
                null_rates.append(rate)
                if rate > 0 and f in ("order_id", "order_date", "product_name", "sales"):
                    issues.append(QualityIssue(
                        code="missing_core_value", field=f, severity="critical",
                        affected_rows=int(canonical_df[f].isna().sum()),
                        description=f"{int(canonical_df[f].isna().sum())} row(s) are missing a value "
                                    f"for required field '{f}'.",
                    ))
        completeness = round(100 * (1 - (sum(null_rates) / len(null_rates))), 2) if null_rates else 100.0
    else:
        completeness = 0.0

    # ---- Uniqueness: duplicate detection ----------------------------------
    dup_mask = canonical_df.duplicated()
    dup_count = int(dup_mask.sum())
    if "order_id" in canonical_df.columns:
        # A true business duplicate: identical order_id + product line
        subset_cols = [c for c in ("order_id", "product_name") if c in canonical_df.columns]
        biz_dupes = int(canonical_df.duplicated(subset=subset_cols).sum()) if subset_cols else dup_count
    else:
        biz_dupes = dup_count
    if dup_count:
        issues.append(QualityIssue(
            code="exact_duplicate_rows", field=None, severity="warning",
            affected_rows=dup_count,
            description=f"{dup_count} fully duplicate row(s) detected.",
        ))
    uniqueness = round(100 * (1 - (dup_count / n_rows)), 2) if n_rows else 100.0

    # ---- Validity: field-specific business rules ---------------------------
    validity_checks = []

    if "order_date" in canonical_df.columns:
        parsed = parse_dates_robust(canonical_df["order_date"])
        invalid = int(parsed.isna().sum() - canonical_df["order_date"].isna().sum())
        valid_frac = 1 - (invalid / n_rows) if n_rows else 1
        validity_checks.append(valid_frac)
        if invalid:
            issues.append(QualityIssue(
                code="invalid_date", field="order_date", severity="critical",
                affected_rows=invalid,
                description=f"{invalid} row(s) have an order_date that could not be parsed.",
            ))

    if "sales" in canonical_df.columns:
        sales_num = _numeric_series(canonical_df["sales"])
        invalid = int(sales_num.isna().sum() - canonical_df["sales"].isna().sum())
        negative = int((sales_num < 0).sum())
        valid_frac = 1 - ((invalid + negative) / n_rows) if n_rows else 1
        validity_checks.append(max(valid_frac, 0))
        if invalid:
            issues.append(QualityIssue(
                code="invalid_numeric", field="sales", severity="critical",
                affected_rows=invalid,
                description=f"{invalid} row(s) have a non-numeric sales value.",
            ))
        if negative:
            issues.append(QualityIssue(
                code="negative_sales", field="sales", severity="critical",
                affected_rows=negative,
                description=f"{negative} row(s) have a negative sales value.",
            ))

    if "quantity" in canonical_df.columns:
        qty_num = _numeric_series(canonical_df["quantity"])
        non_positive = int((qty_num <= 0).sum())
        valid_frac = 1 - (non_positive / n_rows) if n_rows else 1
        validity_checks.append(max(valid_frac, 0))
        if non_positive:
            issues.append(QualityIssue(
                code="non_positive_quantity", field="quantity", severity="warning",
                affected_rows=non_positive,
                description=f"{non_positive} row(s) have quantity <= 0.",
            ))

    if "discount" in canonical_df.columns:
        disc_num = _numeric_series(canonical_df["discount"])
        out_of_bounds = int(((disc_num < 0) | (disc_num > 1)).sum())
        valid_frac = 1 - (out_of_bounds / n_rows) if n_rows else 1
        validity_checks.append(max(valid_frac, 0))
        if out_of_bounds:
            issues.append(QualityIssue(
                code="discount_out_of_bounds", field="discount", severity="warning",
                affected_rows=out_of_bounds,
                description=f"{out_of_bounds} row(s) have a discount outside the expected 0-1 range.",
            ))

    if "ship_date" in canonical_df.columns and "order_date" in canonical_df.columns:
        ship = parse_dates_robust(canonical_df["ship_date"])
        order = parse_dates_robust(canonical_df["order_date"])
        both_present = ship.notna() & order.notna()
        precedes = int(((ship < order) & both_present).sum())
        valid_frac = 1 - (precedes / n_rows) if n_rows else 1
        validity_checks.append(max(valid_frac, 0))
        if precedes:
            issues.append(QualityIssue(
                code="ship_before_order", field="ship_date", severity="warning",
                affected_rows=precedes,
                description=f"{precedes} row(s) have a ship_date earlier than the order_date.",
            ))

    validity = round(100 * (sum(validity_checks) / len(validity_checks)), 2) if validity_checks else 100.0

    # ---- Consistency: whitespace / casing irregularities in categoricals --
    consistency_checks = []
    for f in ("category", "sub_category", "region", "segment", "ship_mode", "state", "country"):
        if f in canonical_df.columns:
            s = canonical_df[f].dropna().astype(str)
            if s.empty:
                continue
            trimmed = s.str.strip()
            trimmed_diff = int((s != trimmed).sum())
            case_variants = trimmed.str.lower().nunique()
            raw_variants = trimmed.nunique()
            consistency_checks.append(1 - (trimmed_diff / len(s)))
            if trimmed_diff:
                issues.append(QualityIssue(
                    code="whitespace_inconsistency", field=f, severity="info",
                    affected_rows=trimmed_diff,
                    description=f"{trimmed_diff} value(s) in '{f}' have leading/trailing whitespace.",
                ))
            if raw_variants > case_variants:
                # Rows whose (trimmed) value isn't the most common casing for
                # its case-insensitive group are the ones actually affected.
                dominant_form = trimmed.groupby(trimmed.str.lower()).transform(
                    lambda g: g.mode().iloc[0]
                )
                casing_affected = int((trimmed != dominant_form).sum())
                issues.append(QualityIssue(
                    code="casing_inconsistency", field=f, severity="info",
                    affected_rows=casing_affected,
                    description=f"'{f}' has {raw_variants - case_variants} value variant(s) that "
                                f"differ only by casing ({casing_affected} row(s) affected).",
                ))
    consistency = round(100 * (sum(consistency_checks) / len(consistency_checks)), 2) if consistency_checks else 100.0

    # ---- Schema match: how much of the canonical schema got covered -------
    from app.data_engine.canonical_schema import CORE_FIELDS, RECOMMENDED_FIELDS, OPTIONAL_FIELDS
    mapped_set = set(mapped_fields)
    core_hit = sum(1 for f in CORE_FIELDS if f in mapped_set) / max(len(CORE_FIELDS), 1)
    rec_hit = sum(1 for f in RECOMMENDED_FIELDS if f in mapped_set) / max(len(RECOMMENDED_FIELDS), 1)
    opt_hit = sum(1 for f in OPTIONAL_FIELDS if f in mapped_set) / max(len(OPTIONAL_FIELDS), 1)
    schema_match = round(100 * (0.6 * core_hit + 0.2 * rec_hit + 0.2 * opt_hit), 2)

    dimension_score = (
        0.30 * completeness + 0.15 * uniqueness + 0.30 * validity +
        0.15 * consistency + 0.10 * schema_match
    )

    # Severity-weighted penalty layer. Row-fraction averages alone let a
    # handful of critical problems hide inside a huge score (e.g. 3 rows with
    # negative sales out of 10,000 barely move a fractional average). Real
    # data-quality tooling (dbt tests, Great Expectations) treats a failing
    # critical rule as significant regardless of how small its row count is
    # relative to the batch, so each *distinct* issue found also costs a
    # flat penalty based on its severity, on top of the dimension score.
    severity_penalty = sum(
        {"critical": 3.0, "warning": 1.0, "info": 0.25}.get(i.severity, 0.0)
        for i in issues
    )
    severity_penalty = min(severity_penalty, 40.0)  # never let penalties alone zero out a mostly-clean dataset

    overall = round(max(0.0, min(dimension_score, 100.0) - severity_penalty), 1)

    return QualityReport(
        score_overall=overall,
        completeness=completeness,
        uniqueness=uniqueness,
        validity=validity,
        consistency=consistency,
        schema_match=schema_match,
        issues=issues,
        row_count=n_rows,
    )
