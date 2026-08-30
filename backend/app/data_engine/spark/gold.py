"""
GOLD layer
===========
Builds an analytics-ready, star-schema-inspired model from Silver's clean
data: one `fact_sales` table plus dimension tables that are ONLY created
when the source fields that support them were actually mapped (spec
section 20 — "Do not create fake dimension data").

Surrogate keys are deterministic hashes of each dimension's natural key
(via `xxhash64`), not row-order-dependent — reprocessing the same dataset
produces the same keys, which matters once Gold is loaded into MySQL.

Every Gold table carries a `dataset_id` column. Gold tables in MySQL are
shared across all processed datasets (so History/Analytics can query any
past run); `dataset_id` is how a single dataset's analytics are isolated.
Slowly-changing-dimension handling across re-uploads of the "same" business
entity is intentionally out of scope for V1 (see docs "Limitations").
"""
import os

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from app.data_engine.spark.spark_session import mysql_jdbc_options


def _surrogate_key(*cols):
    return F.abs(F.xxhash64(*[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in cols]))


def build_dim_date(clean_df: DataFrame) -> DataFrame | None:
    if "order_date" not in clean_df.columns:
        return None
    dates = clean_df.select(F.col("order_date").alias("full_date")).where(F.col("full_date").isNotNull()).distinct()
    return (
        dates
        .withColumn("date_key", F.date_format("full_date", "yyyyMMdd").cast("int"))
        .withColumn("year", F.year("full_date"))
        .withColumn("quarter", F.quarter("full_date"))
        .withColumn("month", F.month("full_date"))
        .withColumn("month_name", F.date_format("full_date", "MMMM"))
        .withColumn("day", F.dayofmonth("full_date"))
        .withColumn("day_of_week", F.dayofweek("full_date"))
        .withColumn("day_name", F.date_format("full_date", "EEEE"))
        .withColumn("is_weekend", F.dayofweek("full_date").isin(1, 7))
    )


def build_dim_product(clean_df: DataFrame) -> DataFrame | None:
    if "product_name" not in clean_df.columns:
        return None
    cols = [c for c in ("product_id", "product_name", "category", "sub_category") if c in clean_df.columns]
    dim = clean_df.select(*cols).distinct()
    key_cols = cols
    return dim.withColumn("product_key", _surrogate_key(*key_cols))


def build_dim_customer(clean_df: DataFrame) -> DataFrame | None:
    if "customer_id" not in clean_df.columns and "customer_name" not in clean_df.columns:
        return None
    cols = [c for c in ("customer_id", "customer_name", "segment") if c in clean_df.columns]
    dim = clean_df.select(*cols).distinct()
    return dim.withColumn("customer_key", _surrogate_key(*cols))


def build_dim_location(clean_df: DataFrame) -> DataFrame | None:
    cols = [c for c in ("country", "state", "city", "region", "postal_code") if c in clean_df.columns]
    if not cols:
        return None
    dim = clean_df.select(*cols).distinct()
    return dim.withColumn("location_key", _surrogate_key(*cols))


def build_fact_sales(
    clean_df: DataFrame,
    dim_product: DataFrame | None,
    dim_customer: DataFrame | None,
    dim_location: DataFrame | None,
) -> DataFrame:
    fact = clean_df

    if "order_date" in fact.columns:
        fact = fact.withColumn("date_key", F.date_format("order_date", "yyyyMMdd").cast("int"))

    if dim_product is not None:
        product_cols = [c for c in ("product_id", "product_name", "category", "sub_category") if c in fact.columns]
        fact = fact.withColumn("product_key", _surrogate_key(*product_cols))

    if dim_customer is not None:
        customer_cols = [c for c in ("customer_id", "customer_name", "segment") if c in fact.columns]
        fact = fact.withColumn("customer_key", _surrogate_key(*customer_cols))

    if dim_location is not None:
        location_cols = [c for c in ("country", "state", "city", "region", "postal_code") if c in fact.columns]
        fact = fact.withColumn("location_key", _surrogate_key(*location_cols))

    measure_and_key_cols = [c for c in [
        "order_id", "date_key", "product_key", "customer_key", "location_key",
        "ship_mode", "ship_date", "sales", "quantity", "discount", "profit",
        "_dataset_id",
    ] if c in fact.columns]
    return fact.select(*measure_and_key_cols)


def build_gold_layer(spark: SparkSession, silver_clean_df: DataFrame, dataset_id: str, gold_root: str) -> dict:
    dim_date = build_dim_date(silver_clean_df)
    dim_product = build_dim_product(silver_clean_df)
    dim_customer = build_dim_customer(silver_clean_df)
    dim_location = build_dim_location(silver_clean_df)
    fact_sales = build_fact_sales(silver_clean_df, dim_product, dim_customer, dim_location)

    tables = {"fact_sales": fact_sales}
    if dim_date is not None:
        tables["dim_date"] = dim_date
    if dim_product is not None:
        tables["dim_product"] = dim_product
    if dim_customer is not None:
        tables["dim_customer"] = dim_customer
    if dim_location is not None:
        tables["dim_location"] = dim_location

    # dataset_id is added to every dimension too, so Gold in MySQL can be
    # filtered per-dataset without a fragile global surrogate-key space.
    for name, df in tables.items():
        if "_dataset_id" not in df.columns:
            df = df.withColumn("_dataset_id", F.lit(dataset_id))
            tables[name] = df

    row_counts = {}
    for name, df in tables.items():
        out_path = os.path.join(gold_root, dataset_id, name)
        df.write.mode("overwrite").parquet(out_path)
        row_counts[name] = df.count()

    return {"tables_built": list(tables.keys()), "row_counts": row_counts, "dataframes": tables}


def write_gold_to_mysql(tables: dict[str, DataFrame], dataset_id: str) -> None:
    """
    Writes each Gold table to a shared MySQL table (prefixed `gold_`), first
    deleting any prior rows for this dataset_id so re-processing the same
    dataset is idempotent, then appending the fresh rows.
    """
    opts = mysql_jdbc_options()
    for name, df in tables.items():
        table_name = f"gold_{name}"
        # Spark's JDBC writer has no native "delete-then-insert" — we rely on
        # the FastAPI orchestration layer (see services/processing_service.py)
        # to issue a DELETE FROM ... WHERE _dataset_id = ? via SQLAlchemy
        # immediately before this append, keeping re-processing idempotent
        # without needing Spark to manage transactional upserts itself.
        (
            df.write
            .format("jdbc")
            .option("url", opts["url"])
            .option("dbtable", table_name)
            .option("user", opts["user"])
            .option("password", opts["password"])
            .option("driver", opts["driver"])
            .mode("append")
            .save()
        )
