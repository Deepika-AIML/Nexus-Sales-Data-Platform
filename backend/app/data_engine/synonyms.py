"""
Synonym & keyword dictionary for the Nexus column mapping engine.

Every list is expressed in *normalized* form already (lowercase, single
underscores) so the mapping engine can do direct comparisons without
re-normalizing at lookup time. Keep this file as the single place to extend
recognized naming conventions — no other module should hard-code column
name strings.
"""

# canonical_field -> list of normalized synonym phrases that should be
# treated as (near) exact equivalents of the field name itself.
SYNONYMS = {
    "order_id": [
        "order_id", "orderid", "order_number", "ordernumber", "order_no",
        "order_num", "transaction_id", "transactionid", "transaction_number",
        "transactionnumber", "txn_id", "txn_number", "invoice_id",
        "invoice_number", "invoice_no", "sale_id", "sales_id", "ref_id",
        "reference_number", "id",
    ],
    "order_date": [
        "order_date", "orderdate", "purchase_date", "purchasedate",
        "transaction_date", "transactiondate", "sale_date", "saledate",
        "date_of_order", "order_dt", "date", "invoice_date", "created_date",
        "created_at",
    ],
    "product_name": [
        "product_name", "productname", "product", "item", "item_name",
        "itemname", "product_title", "product_desc", "product_description",
        "sku_name", "item_description", "description",
    ],
    "sales": [
        "sales", "sale", "revenue", "sales_amount", "salesamount",
        "net_revenue", "netrevenue", "total_sales", "totalsales",
        "total_revenue", "totalrevenue", "amount", "gross_sales",
        "order_amount", "order_value", "net_sales", "sale_amount",
        "line_total", "total_amount", "total",
    ],
    "quantity": [
        "quantity", "qty", "units", "units_sold", "unitssold",
        "order_quantity", "item_quantity", "num_units", "unit_count",
        "quantity_sold", "count",
    ],
    "ship_date": [
        "ship_date", "shipdate", "delivery_date", "deliverydate",
        "shipped_date", "dispatch_date", "shipping_date",
    ],
    "ship_mode": [
        "ship_mode", "shipmode", "shipping_mode", "shipping_method",
        "delivery_mode", "delivery_method", "carrier",
    ],
    "customer_id": [
        "customer_id", "customerid", "cust_id", "custid", "client_id",
        "buyer_id", "customer_number", "customernumber", "client_number",
        "clientnumber", "account_id", "account_number",
    ],
    "customer_name": [
        "customer_name", "customername", "client_name", "buyer_name",
        "cust_name", "account_name", "customer",
    ],
    "segment": [
        "segment", "customer_segment", "market_segment", "segment_name",
        "customer_type",
    ],
    "country": ["country", "nation", "country_name", "country_code"],
    "city": ["city", "town", "city_name"],
    "state": ["state", "province", "state_name", "state_province"],
    "postal_code": [
        "postal_code", "postalcode", "zip", "zip_code", "zipcode",
        "postcode", "post_code",
    ],
    "region": ["region", "sales_region", "area", "territory", "zone"],
    "product_id": [
        "product_id", "productid", "sku", "item_id", "item_code",
        "product_code", "sku_id",
    ],
    "category": [
        "category", "product_category", "category_name", "dept",
        "department", "product_type",
    ],
    "sub_category": [
        "sub_category", "subcategory", "sub_cat", "product_subcategory",
        "sub_department", "subcat",
    ],
    "discount": [
        "discount", "discount_rate", "discount_pct", "discount_percentage",
        "disc", "discount_amount",
    ],
    "profit": [
        "profit", "net_profit", "margin", "profit_amount", "earnings",
        "gross_profit",
    ],
}

# Loosely related keywords used for partial / semantic scoring when no
# strong synonym match is found. These are single tokens that, if present
# in a normalized column name, weakly suggest the given canonical field.
KEYWORDS = {
    "order_id": {"order", "transaction", "invoice", "txn", "id", "number", "no"},
    "order_date": {"order", "purchase", "sale", "transaction", "date"},
    "product_name": {"product", "item", "sku", "name", "description"},
    "sales": {"sales", "revenue", "amount", "value", "total", "gross", "net"},
    "quantity": {"quantity", "qty", "units", "count"},
    "ship_date": {"ship", "shipped", "delivery", "dispatch", "date"},
    "ship_mode": {"ship", "shipping", "mode", "method", "delivery", "carrier"},
    "customer_id": {"customer", "cust", "client", "buyer", "id", "number"},
    "customer_name": {"customer", "cust", "client", "buyer", "name"},
    "segment": {"segment", "market", "type"},
    "country": {"country", "nation"},
    "city": {"city", "town"},
    "state": {"state", "province"},
    "postal_code": {"postal", "zip", "post", "code"},
    "region": {"region", "area", "territory", "zone"},
    "product_id": {"product", "sku", "item", "code", "id"},
    "category": {"category", "dept", "department", "type"},
    "sub_category": {"sub", "category", "subcat"},
    "discount": {"discount", "disc", "rate", "pct", "percentage"},
    "profit": {"profit", "margin", "earnings"},
}
