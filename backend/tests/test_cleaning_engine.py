"""
Cleaning engine tests. Run with: pytest tests/test_cleaning_engine.py -v
"""
import numpy as np
import pandas as pd

from app.data_engine.mapping_engine import suggest_mapping, apply_confirmed_mapping
from app.data_engine.cleaning_engine import clean_and_split


def _mapping_for(df: pd.DataFrame) -> dict:
    result = suggest_mapping(df)
    return {s.source_column: s.best_field for s in result.suggestions if s.best_field}


def test_clean_split_preserves_row_count(superstore_df):
    mapping = _mapping_for(superstore_df)
    canonical = apply_confirmed_mapping(superstore_df, mapping)
    result = clean_and_split(canonical)
    assert result.summary["clean_rows"] + result.summary["rejected_rows"] == result.summary["input_rows"]


def test_never_fabricates_missing_optional_values(superstore_df):
    """A missing profit/discount/customer value must stay missing after
    cleaning — never filled with 0 or any other guessed value."""
    df = superstore_df.copy()
    df.loc[0, "Profit"] = np.nan
    mapping = _mapping_for(df)
    canonical = apply_confirmed_mapping(df, mapping)
    result = clean_and_split(canonical)
    combined = pd.concat([result.clean_df, result.rejected_df.drop(columns=["rejection_reasons"])])
    assert combined.loc[0, "profit"] is None or pd.isna(combined.loc[0, "profit"])


def test_negative_sales_and_bad_quantity_are_rejected_not_dropped():
    df = pd.DataFrame({
        "Order ID": ["A-1", "A-2", "A-3"],
        "Order Date": ["1/1/2024", "1/2/2024", "1/3/2024"],
        "Product Name": ["Widget", "Widget", "Widget"],
        "Sales": [10.0, -5.0, 20.0],
        "Quantity": [2, 3, 0],
    })
    mapping = _mapping_for(df)
    canonical = apply_confirmed_mapping(df, mapping)
    result = clean_and_split(canonical)

    # Row A-2 (negative sales) and A-3 (zero quantity) are rejected, not lost.
    assert result.summary["clean_rows"] == 1
    assert result.summary["rejected_rows"] == 2
    reasons = set(result.rejected_df["rejection_reasons"])
    assert any("negative_sales" in r for r in reasons)
    assert any("non_positive_quantity" in r for r in reasons)


def test_categorical_casing_normalized_without_merging_distinct_values():
    df = pd.DataFrame({
        "Order ID": [f"A-{i}" for i in range(6)],
        "Order Date": ["1/1/2024"] * 6,
        "Product Name": ["Widget"] * 6,
        "Sales": [10.0] * 6,
        "Category": ["Furniture", "furniture", "FURNITURE", "Furniture", "Technology", "technology"],
    })
    mapping = _mapping_for(df)
    canonical = apply_confirmed_mapping(df, mapping)
    result = clean_and_split(canonical)
    combined = pd.concat([result.clean_df, result.rejected_df.drop(columns=["rejection_reasons"], errors="ignore")])
    categories = set(combined["category"].dropna().unique())
    # Casing variants collapse to one dominant spelling per group...
    assert "Furniture" in categories or "furniture" in categories
    # ...but Furniture and Technology remain genuinely distinct categories.
    assert len(categories) == 2
