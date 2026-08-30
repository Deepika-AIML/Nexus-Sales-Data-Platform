"""
Bronze -> Silver -> Gold pipeline orchestrator.

This is the ONE function FastAPI's `/api/process/{dataset_id}` endpoint
calls (via `app/services/processing_service.py`) to run the actual data
engineering work. It intentionally does not touch MySQL directly for the
delete-before-append step — see `write_gold_to_mysql`'s docstring — that
idempotency guard is issued by the calling service via SQLAlchemy just
before `write_gold_to_mysql` runs, so this module stays focused purely on
Spark transformation logic and stays independently testable.
"""
from dataclasses import dataclass, field

from app.data_engine.spark.spark_session import get_spark_session
from app.data_engine.spark.bronze import ingest_to_bronze
from app.data_engine.spark.silver import run_silver_stage
from app.data_engine.spark.gold import build_gold_layer, write_gold_to_mysql


@dataclass
class PipelineResult:
    dataset_id: str
    bronze_path: str
    silver_summary: dict
    gold_summary: dict
    stages_completed: list = field(default_factory=list)


def run_pipeline(
    dataset_id: str,
    raw_csv_path: str,
    encoding: str,
    confirmed_mapping: dict[str, str],
    bronze_root: str,
    silver_root: str,
    gold_root: str,
    write_to_mysql: bool = True,
) -> PipelineResult:
    spark = get_spark_session(app_name=f"nexus-pipeline-{dataset_id}")
    stages_completed = []
    try:
        bronze_df, bronze_path = ingest_to_bronze(spark, raw_csv_path, dataset_id, encoding, bronze_root)
        stages_completed.append("bronze")

        silver_summary = run_silver_stage(spark, bronze_df, confirmed_mapping, dataset_id, silver_root)
        stages_completed.append("silver")

        silver_clean_df = spark.read.parquet(silver_summary["clean_path"])
        gold_summary = build_gold_layer(spark, silver_clean_df, dataset_id, gold_root)
        stages_completed.append("gold")

        if write_to_mysql:
            write_gold_to_mysql(gold_summary["dataframes"], dataset_id)
            stages_completed.append("mysql_load")

        gold_summary_out = {k: v for k, v in gold_summary.items() if k != "dataframes"}
        return PipelineResult(
            dataset_id=dataset_id,
            bronze_path=bronze_path,
            silver_summary=silver_summary,
            gold_summary=gold_summary_out,
            stages_completed=stages_completed,
        )
    finally:
        spark.stop()
