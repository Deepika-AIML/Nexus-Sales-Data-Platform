"""
Required vs. optional field behavior tests (spec section 6/7, TEST 4 & TEST 5
from spec section 35). Run with: pytest tests/test_required_optional_fields.py -v
"""
from app.data_engine.mapping_engine import suggest_mapping, missing_required_fields, missing_optional_fields


def _mapping_for(df):
    result = suggest_mapping(df)
    return {s.source_column: s.best_field for s in result.suggestions if s.best_field}


def test_optional_fields_missing_does_not_block_processing(superstore_df):
    """TEST 4: removing Profit, Discount, and Customer ID must NOT prevent
    the dataset from being considered processable — only the missing
    optional fields should be reported."""
    reduced = superstore_df.drop(columns=["Profit", "Discount", "Customer ID"])
    mapping = _mapping_for(reduced)

    required_missing = missing_required_fields(mapping)
    optional_missing = missing_optional_fields(mapping)

    assert required_missing == [], "Removing only optional fields must not create a required-field gap"
    assert "profit" in optional_missing
    assert "discount" in optional_missing
    assert "customer_id" in optional_missing


def test_required_sales_field_missing_blocks_processing(superstore_df):
    """TEST 5: removing Sales (a CORE field with no synonym elsewhere in
    the dataset) must be detected as a required-field gap. Upload and
    profiling still succeed — only the processing gate should trip."""
    no_sales = superstore_df.drop(columns=["Sales"])
    mapping = _mapping_for(no_sales)

    required_missing = missing_required_fields(mapping)
    assert required_missing == ["sales"]


def test_all_core_fields_present_in_reference_dataset(superstore_df):
    mapping = _mapping_for(superstore_df)
    assert missing_required_fields(mapping) == []
