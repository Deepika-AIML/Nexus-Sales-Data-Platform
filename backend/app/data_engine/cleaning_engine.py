"""
Nexus Cleaning Engine
======================
Applies *safe* standardization to the canonical-shaped dataset and splits
records into CLEAN vs REJECTED. This module defines the rules; the actual
row-by-row execution at scale happens in PySpark (see
`app/data_engine/spark/silver.py`), which imports the constants and pure
functions defined here so the business rules are defined exactly once and
used by both the pandas-based interactive preview and the Spark batch job.

Rules (per product spec — nothing here fabricates data):
  - Trim whitespace on text/category fields.
  - Normalize obvious casing inconsistencies in categorical fields to the
    most frequent form (does NOT merge semantically-different values).
  - Normalize valid dates to ISO 8601 (YYYY-MM-DD).
  - Coerce numeric-looking strings ("$1,200.50") to floats.
  - Do NOT fill missing profit/discount/customer/etc. with 0 or any
    fabricated value — a missing optional value stays missing.
  - A record is REJECTED (not silently dropped) when:
      * a CORE field is missing or unparseable after cleaning, or
      * sales is negative, or
      * quantity <= 0 (when quantity is mapped), or
      * order_date is unparseable, or
      * ship_date exists and precedes order_date.
  - Exact duplicate rows (post-mapping) are removed from CLEAN and reported
    separately — the first occurrence is kept, the rest are moved to
    REJECTED with a `duplicate_of_row` reason so nothing is silently
    destroyed.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.data_engine.date_utils import parse_dates_robust

CATEGORICAL_FIELDS = ("category", "sub_category", "region", "segment",
                      "ship_mode", "state", "country")


def _clean_numeric(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _clean_date(series: pd.Series) -> pd.Series:
    parsed = parse_dates_robust(series)
    return parsed.dt.strftime("%Y-%m-%d")


def _normalize_categorical(series: pd.Series) -> pd.Series:
    trimmed = series.astype(str).str.strip()
    trimmed = trimmed.where(series.notna(), other=pd.NA)
    non_null = trimmed.dropna()
    if non_null.empty:
        return trimmed
    dominant = non_null.groupby(non_null.str.lower()).transform(lambda g: g.mode().iloc[0])
    trimmed.loc[dominant.index] = dominant
    return trimmed


@dataclass
class CleaningResult:
    clean_df: pd.DataFrame
    rejected_df: pd.DataFrame
    summary: dict


def clean_and_split(canonical_df: pd.DataFrame) -> CleaningResult:
    df = canonical_df.copy()
    reasons = pd.Series([[] for _ in range(len(df))], index=df.index)

    def flag(mask: pd.Series, reason: str):
        for idx in df.index[mask.fillna(False)]:
            reasons.at[idx] = reasons.at[idx] + [reason]

    # ---- standardize text / categorical --------------------------------
    if "product_name" in df.columns:
        df["product_name"] = df["product_name"].astype(str).str.strip()
    if "customer_name" in df.columns:
        df["customer_name"] = df["customer_name"].astype(str).str.strip()
    for f in CATEGORICAL_FIELDS:
        if f in df.columns:
            df[f] = _normalize_categorical(df[f])

    # ---- standardize numerics -------------------------------------------
    for f in ("sales", "quantity", "discount", "profit"):
        if f in df.columns:
            df[f] = _clean_numeric(df[f])

    # ---- standardize dates -------------------------------------------
    for f in ("order_date", "ship_date"):
        if f in df.columns:
            df[f] = _clean_date(df[f])

    # ---- core field presence --------------------------------------------
    for f in ("order_id", "order_date", "product_name", "sales"):
        if f in df.columns:
            flag(df[f].isna() | (df[f].astype(str).str.strip() == ""), f"missing_core_field:{f}")

    # ---- business rule validation ----------------------------------------
    if "sales" in df.columns:
        flag(df["sales"] < 0, "negative_sales")
    if "quantity" in df.columns:
        flag(df["quantity"] <= 0, "non_positive_quantity")
    if "ship_date" in df.columns and "order_date" in df.columns:
        ship = parse_dates_robust(df["ship_date"])
        order = parse_dates_robust(df["order_date"])
        flag((ship < order) & ship.notna() & order.notna(), "ship_before_order")

    # ---- duplicates: keep first occurrence, reject the rest ---------------
    dup_mask = df.duplicated(keep="first")
    flag(dup_mask, "duplicate_row")

    has_reason = reasons.apply(lambda r: len(r) > 0)
    clean_df = df.loc[~has_reason].copy()
    rejected_df = df.loc[has_reason].copy()
    rejected_df["rejection_reasons"] = reasons.loc[has_reason].apply(lambda r: ";".join(r))

    summary = {
        "input_rows": len(df),
        "clean_rows": len(clean_df),
        "rejected_rows": len(rejected_df),
        "rejection_reason_counts": (
            rejected_df["rejection_reasons"].str.split(";").explode().value_counts().to_dict()
            if not rejected_df.empty else {}
        ),
    }
    return CleaningResult(clean_df=clean_df, rejected_df=rejected_df, summary=summary)
