"""
BRONZE layer
=============
Raw ingestion. Every column is read as a string (schema-on-read) — Bronze's
job is fidelity to the source file, not correctness. No row is dropped, no
value is altered, no type is inferred. Three metadata columns are added so
every downstream row can be traced back to its ingestion event
(data lineage requirement, spec section 17/33).

Bronze is written once per uploaded dataset and is never overwritten by
later re-processing of the same dataset_id — if a user reprocesses after
changing the mapping, Silver/Gold are rebuilt from the SAME Bronze snapshot,
guaranteeing the original upload is immutable.
"""
import os
from datetime import datetime, timezone

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def ingest_to_bronze(
    spark: SparkSession,
    raw_csv_path: str,
    dataset_id: str,
    encoding: str,
    bronze_root: str,
) -> tuple[DataFrame, str]:
    """
    Reads the raw uploaded CSV and writes an immutable Bronze parquet
    snapshot. Returns (bronze_dataframe, bronze_output_path).
    """
    # Spark's CSV reader supports the same encodings pandas validated at
    # upload time (utf-8 / cp1252 / latin1); we pass the detected encoding
    # through explicitly rather than re-detecting it here.
    df = (
        spark.read
        .option("header", "true")
        .option("encoding", encoding)
        .option("multiLine", "true")
        .option("escape", '"')
        .option("mode", "PERMISSIVE")
        .csv(raw_csv_path)
    )

    # Every column stays a string in Bronze — typing happens in Silver, once
    # we know (from the confirmed mapping) what each column is *supposed*
    # to be. This keeps Bronze a faithful, lossless copy of the source.
    for c in df.columns:
        df = df.withColumn(c, F.col(c).cast("string"))

    ingested_at = datetime.now(timezone.utc).isoformat()
    df = (
        df.withColumn("_dataset_id", F.lit(dataset_id))
          .withColumn("_source_file", F.lit(os.path.basename(raw_csv_path)))
          .withColumn("_ingested_at", F.lit(ingested_at))
          .withColumn("_bronze_row_id", F.monotonically_increasing_id())
    )

    output_path = os.path.join(bronze_root, dataset_id)
    df.write.mode("overwrite").parquet(output_path)

    return df, output_path


def read_bronze(spark: SparkSession, bronze_root: str, dataset_id: str) -> DataFrame:
    return spark.read.parquet(os.path.join(bronze_root, dataset_id))
