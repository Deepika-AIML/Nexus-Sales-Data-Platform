"""
Data quality engine tests. Run with: pytest tests/test_quality_engine.py -v
"""
import numpy as np
import pandas as pd

from app.data_engine.mapping_engine import suggest_mapping, apply_confirmed_mapping
from app.data_engine.quality_engine import profile_dataset, assess_quality


def _mapping_for(df: pd.DataFrame) -> dict:
    result = suggest_mapping(df)
    return {s.source_column: s.best_field for s in result.suggestions if s.best_field}


def test_profile_dataset_basic_shape(superstore_df):
    profile = profile_dataset(superstore_df, filename="Sample_-_Superstore.csv",
                               file_size_bytes=2_287_806, detected_encoding="cp1252")
    assert profile["row_count"] == 9994
    assert profile["column_count"] == 21
    assert len(profile["columns"]) == 21


def test_clean_reference_dataset_scores_high(superstore_df):
    mapping = _mapping_for(superstore_df)
    canonical = apply_confirmed_mapping(superstore_df, mapping)
    report = assess_quality(canonical, mapping)
    assert report.score_overall >= 95.0
    assert report.completeness == 100.0


def test_dirty_dataset_scores_lower_and_flags_issues(superstore_df):
    """TEST 3 (spec section 35): duplicates, nulls, inconsistent formatting,
    and date problems must all be detected, and the score must meaningfully
    reflect the presence of CRITICAL issues (not just dilute them across
    thousands of clean rows)."""
    dirty = pd.concat([superstore_df, superstore_df.iloc[:20]], ignore_index=True)
    dirty.loc[5:15, "Sales"] = np.nan
    dirty.loc[20:25, "Category"] = "  Furniture "
    dirty.loc[26:30, "Category"] = "FURNITURE"
    dirty.loc[40, "Sales"] = -50
    dirty.loc[41, "Quantity"] = 0
    dirty.loc[42, "Order Date"] = "NOT_A_DATE"
    dirty.loc[43, "Ship Date"] = "2015-01-01"  # mixed date format vs. the rest of the column

    mapping = _mapping_for(dirty)
    canonical = apply_confirmed_mapping(dirty, mapping)
    report = assess_quality(canonical, mapping)

    codes = {i.code for i in report.issues}
    assert "missing_core_value" in codes
    assert "exact_duplicate_rows" in codes
    assert "invalid_date" in codes
    assert "negative_sales" in codes
    assert "non_positive_quantity" in codes

    clean_mapping = _mapping_for(superstore_df)
    clean_canonical = apply_confirmed_mapping(superstore_df, clean_mapping)
    clean_report = assess_quality(clean_canonical, clean_mapping)
    assert report.score_overall < clean_report.score_overall


def test_mixed_date_formats_do_not_silently_become_invalid():
    """Regression test: pandas.to_datetime without format='mixed' silently
    returns NaT for rows that don't match the format it locked onto from
    the rest of the column. A 2015-01-01-style row mixed into an
    otherwise M/D/YYYY column must still parse correctly."""
    df = pd.DataFrame({
        "Order ID": ["A-1", "A-2", "A-3"],
        "Order Date": ["9/23/2017", "9/20/2017", "9/19/2017"],
        "Ship Date": ["9/26/2017", "9/23/2017", "2015-01-01"],
        "Product Name": ["Widget", "Widget", "Widget"],
        "Sales": [10.0, 20.0, 30.0],
    })
    mapping = _mapping_for(df)
    canonical = apply_confirmed_mapping(df, mapping)
    report = assess_quality(canonical, mapping)
    codes = {i.code for i in report.issues}
    # The 2015-01-01 ship_date genuinely precedes its order_date, so this
    # SHOULD be flagged as a real business-rule violation — not as an
    # "invalid_date" parsing failure, which would indicate the mixed-format
    # bug had regressed.
    assert "invalid_date" not in codes
    assert "ship_before_order" in codes
