"""
SILVER layer
=============
Takes the immutable Bronze snapshot plus the user-CONFIRMED column mapping
and produces a standardized, validated, canonically-shaped dataset — split
into `silver_clean` and `silver_rejected`.

This is the layer where the "no fabrication" rule lives: missing optional
values are left null, never filled with 0 or a guessed value. Only rows
that violate a defined rule move to `silver_rejected`, and every rejected
row keeps a `rejection_reasons` column explaining why — nothing is
silently dropped (data lineage requirement, spec sections 16/17).

Common date formats are tried explicitly and coalesced, because Spark (unlike
pandas' `format="mixed"`) does not auto-detect per-row date formats — this is
a deliberate, explainable list rather than a black box.
"""
import os

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from app.data_engine.canonical_schema import CANONICAL_SCHEMA, FieldType

CATEGORICAL_FIELDS = ("category", "sub_category", "region", "segment",
                      "ship_mode", "state", "country")

# Tried in order; first one that parses a given value wins.
DATE_FORMATS = [
    "M/d/yyyy", "MM/dd/yyyy", "yyyy-MM-dd", "d/M/yyyy",
    "yyyy/MM/dd", "MM-dd-yyyy", "dd-MM-yyyy", "M/d/yy",
]


def _parse_date_multi_format(colname: str):
    attempts = [F.to_date(F.trim(F.col(colname)), fmt) for fmt in DATE_FORMATS]
    return F.coalesce(*attempts)


def _clean_numeric(colname: str):
    stripped = F.regexp_replace(F.col(colname), r"[\$,%]", "")
    return F.trim(stripped).cast("double")


def apply_mapping(bronze_df: DataFrame, confirmed_mapping: dict[str, str]) -> DataFrame:
    """confirmed_mapping: {source_column: canonical_field}. Renames + selects
    only mapped columns (plus lineage columns), leaving Bronze untouched."""
    select_exprs = []
    for source_col, canonical_field in confirmed_mapping.items():
        if canonical_field and source_col in bronze_df.columns:
            select_exprs.append(F.col(f"`{source_col}`").alias(canonical_field))
    lineage_cols = ["_dataset_id", "_source_file", "_ingested_at", "_bronze_row_id"]
    select_exprs += [F.col(c) for c in lineage_cols if c in bronze_df.columns]
    return bronze_df.select(*select_exprs)


def _normalize_categorical_casing(df: DataFrame, field: str) -> DataFrame:
    """
    Finds the most frequent original casing for each case-insensitive group
    and rewrites every row to that dominant form. Does NOT merge values that
    differ by more than casing/whitespace (e.g. 'Furniture' vs 'Furnishings'
    stay distinct) — only exact case-insensitive matches are consolidated.
    """
    trimmed_col = f"__{field}_trimmed"
    key_col = f"__{field}_key"
    df = df.withColumn(trimmed_col, F.trim(F.col(field)))
    df = df.withColumn(key_col, F.lower(F.col(trimmed_col)))

    freq = (
        df.filter(F.col(trimmed_col).isNotNull())
        .groupBy(key_col, trimmed_col)
        .count()
    )
    w = Window.partitionBy(key_col).orderBy(F.col("count").desc(), F.col(trimmed_col))
    dominant = (
        freq.withColumn("rn", F.row_number().over(w))
        .filter(F.col("rn") == 1)
        .select(F.col(key_col), F.col(trimmed_col).alias(f"__{field}_dominant"))
    )

    df = df.join(dominant, on=key_col, how="left")
    df = df.withColumn(field, F.coalesce(F.col(f"__{field}_dominant"), F.col(trimmed_col)))
    df = df.drop(trimmed_col, key_col, f"__{field}_dominant")
    return df


def clean_and_standardize(mapped_df: DataFrame) -> DataFrame:
    df = mapped_df
    fields = set(df.columns)

    if "product_name" in fields:
        df = df.withColumn("product_name", F.trim(F.col("product_name")))
    if "customer_name" in fields:
        df = df.withColumn("customer_name", F.trim(F.col("customer_name")))

    for f in CATEGORICAL_FIELDS:
        if f in fields:
            df = _normalize_categorical_casing(df, f)

    for f in ("sales", "quantity", "discount", "profit"):
        if f in fields:
            df = df.withColumn(f, _clean_numeric(f))

    for f in ("order_date", "ship_date"):
        if f in fields:
            df = df.withColumn(f, _parse_date_multi_format(f))

    if "order_id" in fields:
        df = df.withColumn("order_id", F.trim(F.col("order_id")))

    return df


def validate_and_split(clean_std_df: DataFrame) -> tuple[DataFrame, DataFrame, dict]:
    """Returns (silver_clean, silver_rejected, summary_dict)."""
    df = clean_std_df
    fields = set(df.columns)
    reasons = []

    def add_reason(condition, code):
        reasons.append(F.when(condition, F.lit(code)))

    for f in ("order_id", "order_date", "product_name", "sales"):
        if f in fields:
            add_reason(F.col(f).isNull(), f"missing_core_field:{f}")

    if "sales" in fields:
        add_reason(F.col("sales") < 0, "negative_sales")
    if "quantity" in fields:
        add_reason(F.col("quantity") <= 0, "non_positive_quantity")
    if "ship_date" in fields and "order_date" in fields:
        add_reason(
            (F.col("ship_date").isNotNull()) & (F.col("order_date").isNotNull()) &
            (F.col("ship_date") < F.col("order_date")),
            "ship_before_order",
        )

    reason_array = F.array_compact(F.array(*reasons)) if reasons else F.array()
    df = df.withColumn("_reasons", reason_array)

    # Exact-duplicate detection across canonical business columns (excludes
    # lineage columns so two truly identical business rows are still caught).
    business_cols = [c for c in df.columns if not c.startswith("_")]
    dup_window = Window.partitionBy(*[F.col(c) for c in business_cols]).orderBy(F.col("_bronze_row_id"))
    df = df.withColumn("_dup_rank", F.row_number().over(dup_window))
    df = df.withColumn(
        "_reasons",
        F.when(F.col("_dup_rank") > 1, F.array_union(F.col("_reasons"), F.array(F.lit("duplicate_row"))))
         .otherwise(F.col("_reasons")),
    )

    df = df.withColumn("rejection_reasons", F.array_join(F.col("_reasons"), ";"))
    df = df.withColumn("_is_rejected", F.size(F.col("_reasons")) > 0)

    silver_clean = df.filter(~F.col("_is_rejected")).drop("_reasons", "_is_rejected", "_dup_rank", "rejection_reasons")
    silver_rejected = df.filter(F.col("_is_rejected")).drop("_reasons", "_is_rejected", "_dup_rank")

    summary = {
        "input_rows": df.count(),
        "clean_rows": silver_clean.count(),
        "rejected_rows": silver_rejected.count(),
    }
    return silver_clean, silver_rejected, summary


def run_silver_stage(
    spark: SparkSession,
    bronze_df: DataFrame,
    confirmed_mapping: dict[str, str],
    dataset_id: str,
    silver_root: str,
) -> dict:
    mapped = apply_mapping(bronze_df, confirmed_mapping)
    standardized = clean_and_standardize(mapped)
    clean_df, rejected_df, summary = validate_and_split(standardized)

    clean_path = os.path.join(silver_root, dataset_id, "clean")
    rejected_path = os.path.join(silver_root, dataset_id, "rejected")
    clean_df.write.mode("overwrite").parquet(clean_path)
    rejected_df.write.mode("overwrite").parquet(rejected_path)

    summary["clean_path"] = clean_path
    summary["rejected_path"] = rejected_path
    return summary
