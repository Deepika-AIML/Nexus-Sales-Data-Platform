"""
Canonical Nexus Sales Schema
=============================
This is the single source of truth for what a "sales dataset" means to Nexus.
Every uploaded dataset — regardless of its original column names — is mapped
onto this schema before any cleaning, transformation, or analytics happens.

The schema is intentionally data-driven (plain Python structures) so that
extending it later (e.g. adding a `channel` field) does not require touching
the mapping engine, quality engine, or pipeline logic.
"""
from enum import Enum


class FieldTier(str, Enum):
    CORE = "core"                # Cannot proceed to full analytics without these
    RECOMMENDED = "recommended"  # Strongly desired, processing still works without it
    OPTIONAL = "optional"        # Enriches analytics when present


class FieldType(str, Enum):
    IDENTIFIER = "identifier"    # opaque id / code, treated as string
    TEXT = "text"                # free text
    CATEGORY = "category"        # low-cardinality label
    DATE = "date"
    CURRENCY = "currency"        # non-negative-ish monetary float
    SIGNED_CURRENCY = "signed_currency"  # monetary float that CAN be negative (profit)
    QUANTITY = "quantity"        # non-negative integer-like
    RATE = "rate"                # 0..1 (or 0..100) percentage-like float
    POSTAL = "postal"


# canonical_field -> metadata
CANONICAL_SCHEMA = {
    "order_id":       {"tier": FieldTier.CORE,        "type": FieldType.IDENTIFIER, "label": "Order ID"},
    "order_date":     {"tier": FieldTier.CORE,        "type": FieldType.DATE,       "label": "Order Date"},
    "product_name":   {"tier": FieldTier.CORE,        "type": FieldType.TEXT,       "label": "Product Name"},
    "sales":          {"tier": FieldTier.CORE,        "type": FieldType.CURRENCY,   "label": "Sales"},

    "quantity":       {"tier": FieldTier.RECOMMENDED, "type": FieldType.QUANTITY,   "label": "Quantity"},

    "ship_date":      {"tier": FieldTier.OPTIONAL, "type": FieldType.DATE,       "label": "Ship Date"},
    "ship_mode":      {"tier": FieldTier.OPTIONAL, "type": FieldType.CATEGORY,   "label": "Ship Mode"},
    "customer_id":    {"tier": FieldTier.OPTIONAL, "type": FieldType.IDENTIFIER, "label": "Customer ID"},
    "customer_name":  {"tier": FieldTier.OPTIONAL, "type": FieldType.TEXT,       "label": "Customer Name"},
    "segment":        {"tier": FieldTier.OPTIONAL, "type": FieldType.CATEGORY,   "label": "Segment"},
    "country":        {"tier": FieldTier.OPTIONAL, "type": FieldType.CATEGORY,   "label": "Country"},
    "city":           {"tier": FieldTier.OPTIONAL, "type": FieldType.CATEGORY,   "label": "City"},
    "state":          {"tier": FieldTier.OPTIONAL, "type": FieldType.CATEGORY,   "label": "State"},
    "postal_code":    {"tier": FieldTier.OPTIONAL, "type": FieldType.POSTAL,     "label": "Postal Code"},
    "region":         {"tier": FieldTier.OPTIONAL, "type": FieldType.CATEGORY,   "label": "Region"},
    "product_id":     {"tier": FieldTier.OPTIONAL, "type": FieldType.IDENTIFIER, "label": "Product ID"},
    "category":       {"tier": FieldTier.OPTIONAL, "type": FieldType.CATEGORY,   "label": "Category"},
    "sub_category":   {"tier": FieldTier.OPTIONAL, "type": FieldType.CATEGORY,   "label": "Sub-Category"},
    "discount":       {"tier": FieldTier.OPTIONAL, "type": FieldType.RATE,       "label": "Discount"},
    "profit":         {"tier": FieldTier.OPTIONAL, "type": FieldType.SIGNED_CURRENCY, "label": "Profit"},
}

CORE_FIELDS = [f for f, m in CANONICAL_SCHEMA.items() if m["tier"] == FieldTier.CORE]
RECOMMENDED_FIELDS = [f for f, m in CANONICAL_SCHEMA.items() if m["tier"] == FieldTier.RECOMMENDED]
OPTIONAL_FIELDS = [f for f, m in CANONICAL_SCHEMA.items() if m["tier"] == FieldTier.OPTIONAL]
ALL_FIELDS = list(CANONICAL_SCHEMA.keys())

# Analytics capabilities and the canonical fields each one depends on.
# The analytics engine checks this map at runtime against whatever fields
# actually got mapped for a given dataset — this is how "profit unavailable"
# style messages are produced without hard-coding logic per dataset.
ANALYTICS_DEPENDENCIES = {
    "revenue_kpis":        ["sales"],
    "order_kpis":          ["order_id"],
    "quantity_kpis":       ["quantity"],
    "profitability":       ["profit"],
    "category_profitability": ["category", "profit", "sales"],
    "sales_trend":         ["order_date", "sales"],
    "sales_by_category":   ["category", "sales"],
    "sales_by_subcategory": ["sub_category", "sales"],
    "sales_by_region":     ["region", "sales"],
    "top_products":        ["product_name", "sales"],
    "segment_analysis":    ["segment", "sales"],
    "customer_analysis":   ["customer_id", "sales"],
    "discount_analysis":   ["discount", "sales"],
    "shipping_analysis":   ["ship_date", "order_date"],
    "geo_analysis":        ["state", "sales"],
}
