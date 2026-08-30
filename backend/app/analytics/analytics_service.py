"""
Analytics service — SQL-based analytics over the Gold star schema (spec
section 24). Every metric/chart checks `ANALYTICS_DEPENDENCIES` (see
`app/data_engine/canonical_schema.py`) against the dataset's ACTUAL
confirmed mapping before running its query. If a dependency isn't met
(e.g. no `profit` field was mapped), the metric is returned with
`"available": false` and a clear reason — it is never silently
fabricated or defaulted to zero (spec sections 6 and 24).

All queries run directly against MySQL via SQLAlchemy Core (`text(...)`)
— this is the "processed data, not raw unvalidated data" analytics layer;
it only ever reads from `gold_*` tables, which are only populated once a
dataset has been through the Silver/Gold Spark pipeline.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_engine.canonical_schema import ANALYTICS_DEPENDENCIES


def _mapped_fields(db: Session, dataset_id: str) -> set[str]:
    from app.services.mapping_service import get_confirmed_mapping
    return set(get_confirmed_mapping(db, dataset_id).values())


def _available(capability: str, mapped: set[str]) -> tuple[bool, list[str]]:
    required = ANALYTICS_DEPENDENCIES.get(capability, [])
    missing = [f for f in required if f not in mapped]
    return (len(missing) == 0, missing)


def _unavailable_block(capability: str, missing: list[str]) -> dict:
    field = missing[0] if missing else "required data"
    return {
        "available": False,
        "reason": f"{capability.replace('_', ' ').title()} unavailable because {field} data was not provided.",
    }


def get_analytics(db: Session, dataset_id: str) -> dict:
    mapped = _mapped_fields(db, dataset_id)
    result: dict = {"dataset_id": dataset_id}

    result["revenue_kpis"] = _revenue_kpis(db, dataset_id, mapped)
    result["order_kpis"] = _order_kpis(db, dataset_id, mapped)
    result["quantity_kpis"] = _quantity_kpis(db, dataset_id, mapped)
    result["profitability"] = _profitability(db, dataset_id, mapped)
    result["category_profitability"] = _category_profitability(db, dataset_id, mapped)
    result["sales_trend"] = _sales_trend(db, dataset_id, mapped)
    result["sales_by_category"] = _sales_by_category(db, dataset_id, mapped)
    result["sales_by_subcategory"] = _sales_by_subcategory(db, dataset_id, mapped)
    result["sales_by_region"] = _sales_by_region(db, dataset_id, mapped)
    result["top_products"] = _top_products(db, dataset_id, mapped)
    result["segment_analysis"] = _segment_analysis(db, dataset_id, mapped)
    result["customer_analysis"] = _customer_analysis(db, dataset_id, mapped)
    result["discount_analysis"] = _discount_analysis(db, dataset_id, mapped)
    return result


def _revenue_kpis(db, dataset_id, mapped):
    ok, missing = _available("revenue_kpis", mapped)
    if not ok:
        return _unavailable_block("revenue_kpis", missing)
    row = db.execute(text(
        "SELECT SUM(sales) AS total_sales, AVG(sales) AS avg_line_sales, COUNT(*) AS line_count "
        "FROM gold_fact_sales WHERE _dataset_id = :did"
    ), {"did": dataset_id}).mappings().first()
    return {"available": True, "total_sales": float(row["total_sales"] or 0), "avg_line_sales": float(row["avg_line_sales"] or 0)}


def _order_kpis(db, dataset_id, mapped):
    ok, missing = _available("order_kpis", mapped)
    if not ok:
        return _unavailable_block("order_kpis", missing)
    row = db.execute(text(
        "SELECT COUNT(DISTINCT order_id) AS total_orders, SUM(sales) AS total_sales "
        "FROM gold_fact_sales WHERE _dataset_id = :did"
    ), {"did": dataset_id}).mappings().first()
    total_orders = int(row["total_orders"] or 0)
    total_sales = float(row["total_sales"] or 0)
    avg_order_value = round(total_sales / total_orders, 2) if total_orders else 0.0
    return {"available": True, "total_orders": total_orders, "average_order_value": avg_order_value}


def _quantity_kpis(db, dataset_id, mapped):
    ok, missing = _available("quantity_kpis", mapped)
    if not ok:
        return _unavailable_block("quantity_kpis", missing)
    row = db.execute(text(
        "SELECT SUM(quantity) AS total_quantity FROM gold_fact_sales WHERE _dataset_id = :did"
    ), {"did": dataset_id}).mappings().first()
    return {"available": True, "total_quantity": int(row["total_quantity"] or 0)}


def _profitability(db, dataset_id, mapped):
    ok, missing = _available("profitability", mapped)
    if not ok:
        return _unavailable_block("profitability", missing)
    row = db.execute(text(
        "SELECT SUM(profit) AS total_profit, SUM(sales) AS total_sales "
        "FROM gold_fact_sales WHERE _dataset_id = :did"
    ), {"did": dataset_id}).mappings().first()
    total_profit = float(row["total_profit"] or 0)
    total_sales = float(row["total_sales"] or 0)
    margin = round(100 * total_profit / total_sales, 2) if total_sales else None
    return {"available": True, "total_profit": total_profit, "profit_margin_pct": margin}


def _category_profitability(db, dataset_id, mapped):
    ok, missing = _available("category_profitability", mapped)
    if not ok:
        return _unavailable_block("category_profitability", missing)
    rows = db.execute(text(
        "SELECT p.category AS category, SUM(f.sales) AS sales, SUM(f.profit) AS profit "
        "FROM gold_fact_sales f JOIN gold_dim_product p "
        "  ON f.product_key = p.product_key AND f._dataset_id = p._dataset_id "
        "WHERE f._dataset_id = :did AND p.category IS NOT NULL "
        "GROUP BY p.category ORDER BY profit ASC"
    ), {"did": dataset_id}).mappings().all()
    categories = []
    for r in rows:
        sales = float(r["sales"] or 0)
        profit = float(r["profit"] or 0)
        margin = round(100 * profit / sales, 2) if sales else None
        categories.append({"category": r["category"], "sales": sales, "profit": profit, "margin_pct": margin})
    return {"available": True, "categories": categories}


def _sales_trend(db, dataset_id, mapped):
    ok, missing = _available("sales_trend", mapped)
    if not ok:
        return _unavailable_block("sales_trend", missing)
    rows = db.execute(text(
        "SELECT d.year AS year, d.month AS month, SUM(f.sales) AS sales "
        "FROM gold_fact_sales f JOIN gold_dim_date d "
        "  ON f.date_key = d.date_key AND f._dataset_id = d._dataset_id "
        "WHERE f._dataset_id = :did "
        "GROUP BY d.year, d.month ORDER BY d.year, d.month"
    ), {"did": dataset_id}).mappings().all()
    return {"available": True, "points": [{"year": r["year"], "month": r["month"], "sales": float(r["sales"] or 0)} for r in rows]}


def _sales_by_category(db, dataset_id, mapped):
    ok, missing = _available("sales_by_category", mapped)
    if not ok:
        return _unavailable_block("sales_by_category", missing)
    rows = db.execute(text(
        "SELECT p.category AS category, SUM(f.sales) AS sales "
        "FROM gold_fact_sales f JOIN gold_dim_product p "
        "  ON f.product_key = p.product_key AND f._dataset_id = p._dataset_id "
        "WHERE f._dataset_id = :did AND p.category IS NOT NULL "
        "GROUP BY p.category ORDER BY sales DESC"
    ), {"did": dataset_id}).mappings().all()
    return {"available": True, "categories": [{"category": r["category"], "sales": float(r["sales"] or 0)} for r in rows]}


def _sales_by_subcategory(db, dataset_id, mapped):
    ok, missing = _available("sales_by_subcategory", mapped)
    if not ok:
        return _unavailable_block("sales_by_subcategory", missing)
    rows = db.execute(text(
        "SELECT p.sub_category AS sub_category, SUM(f.sales) AS sales "
        "FROM gold_fact_sales f JOIN gold_dim_product p "
        "  ON f.product_key = p.product_key AND f._dataset_id = p._dataset_id "
        "WHERE f._dataset_id = :did AND p.sub_category IS NOT NULL "
        "GROUP BY p.sub_category ORDER BY sales DESC"
    ), {"did": dataset_id}).mappings().all()
    return {"available": True, "sub_categories": [{"sub_category": r["sub_category"], "sales": float(r["sales"] or 0)} for r in rows]}


def _sales_by_region(db, dataset_id, mapped):
    ok, missing = _available("sales_by_region", mapped)
    if not ok:
        return _unavailable_block("sales_by_region", missing)
    rows = db.execute(text(
        "SELECT l.region AS region, SUM(f.sales) AS sales "
        "FROM gold_fact_sales f JOIN gold_dim_location l "
        "  ON f.location_key = l.location_key AND f._dataset_id = l._dataset_id "
        "WHERE f._dataset_id = :did AND l.region IS NOT NULL "
        "GROUP BY l.region ORDER BY sales DESC"
    ), {"did": dataset_id}).mappings().all()
    return {"available": True, "regions": [{"region": r["region"], "sales": float(r["sales"] or 0)} for r in rows]}


def _top_products(db, dataset_id, mapped, limit: int = 10):
    ok, missing = _available("top_products", mapped)
    if not ok:
        return _unavailable_block("top_products", missing)
    rows = db.execute(text(
        "SELECT p.product_name AS product_name, SUM(f.sales) AS sales, SUM(f.quantity) AS quantity "
        "FROM gold_fact_sales f JOIN gold_dim_product p "
        "  ON f.product_key = p.product_key AND f._dataset_id = p._dataset_id "
        "WHERE f._dataset_id = :did "
        "GROUP BY p.product_name ORDER BY sales DESC LIMIT :lim"
    ), {"did": dataset_id, "lim": limit}).mappings().all()
    return {"available": True, "products": [{"product_name": r["product_name"], "sales": float(r["sales"] or 0), "quantity": int(r["quantity"] or 0)} for r in rows]}


def _segment_analysis(db, dataset_id, mapped):
    ok, missing = _available("segment_analysis", mapped)
    if not ok:
        return _unavailable_block("segment_analysis", missing)
    rows = db.execute(text(
        "SELECT c.segment AS segment, SUM(f.sales) AS sales, COUNT(DISTINCT f.order_id) AS orders "
        "FROM gold_fact_sales f JOIN gold_dim_customer c "
        "  ON f.customer_key = c.customer_key AND f._dataset_id = c._dataset_id "
        "WHERE f._dataset_id = :did AND c.segment IS NOT NULL "
        "GROUP BY c.segment ORDER BY sales DESC"
    ), {"did": dataset_id}).mappings().all()
    return {"available": True, "segments": [{"segment": r["segment"], "sales": float(r["sales"] or 0), "orders": int(r["orders"] or 0)} for r in rows]}


def _customer_analysis(db, dataset_id, mapped):
    ok, missing = _available("customer_analysis", mapped)
    if not ok:
        return _unavailable_block("customer_analysis", missing)
    row = db.execute(text(
        "SELECT COUNT(DISTINCT c.customer_key) AS unique_customers "
        "FROM gold_fact_sales f JOIN gold_dim_customer c "
        "  ON f.customer_key = c.customer_key AND f._dataset_id = c._dataset_id "
        "WHERE f._dataset_id = :did"
    ), {"did": dataset_id}).mappings().first()
    top_rows = db.execute(text(
        "SELECT c.customer_name AS customer_name, SUM(f.sales) AS sales "
        "FROM gold_fact_sales f JOIN gold_dim_customer c "
        "  ON f.customer_key = c.customer_key AND f._dataset_id = c._dataset_id "
        "WHERE f._dataset_id = :did AND c.customer_name IS NOT NULL "
        "GROUP BY c.customer_name ORDER BY sales DESC LIMIT 10"
    ), {"did": dataset_id}).mappings().all()
    return {
        "available": True,
        "unique_customers": int(row["unique_customers"] or 0),
        "top_customers": [{"customer_name": r["customer_name"], "sales": float(r["sales"] or 0)} for r in top_rows],
    }


def _discount_analysis(db, dataset_id, mapped):
    ok, missing = _available("discount_analysis", mapped)
    if not ok:
        return _unavailable_block("discount_analysis", missing)
    rows = db.execute(text(
        "SELECT "
        "  CASE WHEN discount = 0 THEN 'No discount' "
        "       WHEN discount <= 0.2 THEN '0-20%' "
        "       WHEN discount <= 0.4 THEN '20-40%' "
        "       ELSE '40%+' END AS discount_band, "
        "  SUM(sales) AS sales, AVG(profit) AS avg_profit "
        "FROM gold_fact_sales WHERE _dataset_id = :did "
        "GROUP BY discount_band"
    ), {"did": dataset_id}).mappings().all()
    return {"available": True, "bands": [{"discount_band": r["discount_band"], "sales": float(r["sales"] or 0), "avg_profit": (float(r["avg_profit"]) if r["avg_profit"] is not None else None)} for r in rows]}
