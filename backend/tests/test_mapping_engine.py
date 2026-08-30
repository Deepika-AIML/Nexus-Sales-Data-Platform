"""
Column mapping engine tests. Pure pandas — no DB, no FastAPI, no Docker
required. Run with: pytest tests/test_mapping_engine.py -v
"""
import pandas as pd

from app.data_engine.mapping_engine import (
    normalize_column_name, suggest_mapping, apply_confirmed_mapping,
    missing_required_fields, AUTO_MAP_THRESHOLD, REVIEW_THRESHOLD,
)


def test_normalize_column_name():
    assert normalize_column_name("Order ID") == "order_id"
    assert normalize_column_name("  Sub-Category ") == "sub_category"
    assert normalize_column_name("Postal Code") == "postal_code"
    assert normalize_column_name("Sales__Amount") == "sales_amount"


def test_original_superstore_columns_map_correctly(superstore_df):
    """TEST 1 (spec section 35): the unmodified reference dataset should
    auto-map every meaningful column and leave the meaningless Row ID
    column unmapped."""
    result = suggest_mapping(superstore_df)
    by_source = {s.source_column: s for s in result.suggestions}

    expected = {
        "Order ID": "order_id", "Order Date": "order_date", "Ship Date": "ship_date",
        "Ship Mode": "ship_mode", "Customer ID": "customer_id", "Customer Name": "customer_name",
        "Segment": "segment", "Country": "country", "City": "city", "State": "state",
        "Postal Code": "postal_code", "Region": "region", "Product ID": "product_id",
        "Category": "category", "Sub-Category": "sub_category", "Product Name": "product_name",
        "Sales": "sales", "Quantity": "quantity", "Discount": "discount", "Profit": "profit",
    }
    for source_col, expected_field in expected.items():
        assert by_source[source_col].best_field == expected_field, (
            f"{source_col} mapped to {by_source[source_col].best_field}, expected {expected_field}"
        )
        assert by_source[source_col].status == "auto_mapped"

    # Row ID is a meaningless surrogate index — it should NOT confidently map anywhere.
    assert by_source["Row ID"].status != "auto_mapped"


def test_renamed_columns_still_map_correctly(superstore_df):
    """TEST 2 (spec section 35): renamed columns should still be identified
    via synonym/fuzzy/keyword matching."""
    renamed = superstore_df.rename(columns={
        "Order ID": "Transaction ID",
        "Order Date": "Purchase Date",
        "Sales": "Revenue",
        "Quantity": "Units Sold",
    })
    result = suggest_mapping(renamed)
    by_source = {s.source_column: s for s in result.suggestions}

    assert by_source["Transaction ID"].best_field == "order_id"
    assert by_source["Purchase Date"].best_field == "order_date"
    assert by_source["Revenue"].best_field == "sales"
    assert by_source["Units Sold"].best_field == "quantity"
    for col in ("Transaction ID", "Purchase Date", "Revenue", "Units Sold"):
        assert by_source[col].confidence >= REVIEW_THRESHOLD


def test_confidence_band_classification():
    """A column with no name/keyword/type resemblance to anything should
    land below the review threshold and be left unmapped."""
    df = pd.DataFrame({
        "Order ID": ["A-1", "A-2", "A-3"],
        "xyzzy_plugh_qux": ["z", "y", "x"],
    })
    result = suggest_mapping(df)
    by_source = {s.source_column: s for s in result.suggestions}
    assert by_source["xyzzy_plugh_qux"].confidence < REVIEW_THRESHOLD
    assert by_source["xyzzy_plugh_qux"].status == "unmapped"


def test_conflict_detection():
    """Two columns that both plausibly mean 'sales' should raise a conflict,
    not silently pick one."""
    df = pd.DataFrame({
        "Sales": [100.0, 200.0, 300.0],
        "Revenue": [100.0, 200.0, 300.0],
        "Order ID": ["A-1", "A-2", "A-3"],
    })
    result = suggest_mapping(df)
    conflict_fields = {c["canonical_field"] for c in result.conflicts}
    assert "sales" in conflict_fields


def test_apply_confirmed_mapping_renames_and_drops_unmapped():
    df = pd.DataFrame({"Order ID": ["A-1"], "Sales": [10.0], "Junk": ["x"]})
    mapping = {"Order ID": "order_id", "Sales": "sales", "Junk": None}
    canonical = apply_confirmed_mapping(df, mapping)
    assert list(canonical.columns) == ["order_id", "sales"]


def test_missing_required_fields_detects_gap():
    mapping = {"Order ID": "order_id", "Order Date": "order_date", "Product Name": "product_name"}
    missing = missing_required_fields(mapping)
    assert missing == ["sales"]
