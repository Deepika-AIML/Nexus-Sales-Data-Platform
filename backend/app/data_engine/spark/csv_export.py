"""
Spark's `DataFrame.write.csv(...)` always writes a directory of part-files
(one per partition) plus a `_SUCCESS` marker — never a single named CSV.
For Nexus's download endpoints we want one clean file the user can open
directly, so this coalesces to a single partition, writes to a temp
directory, then moves/renames the resulting `part-*.csv` to the requested
final path and removes the temp directory.

Coalescing to 1 partition before writing is fine at the row counts Nexus
targets (a 25 MB upload); it would need reconsideration for true
big-data-scale exports (see docs "Scalability considerations").
"""
import glob
import os
import shutil
import uuid

from pyspark.sql import DataFrame


def write_single_csv(df: DataFrame, final_csv_path: str) -> str:
    tmp_dir = f"{final_csv_path}.tmp-{uuid.uuid4().hex[:8]}"
    (
        df.coalesce(1)
        .write
        .mode("overwrite")
        .option("header", "true")
        .csv(tmp_dir)
    )

    part_files = glob.glob(os.path.join(tmp_dir, "part-*.csv"))
    os.makedirs(os.path.dirname(final_csv_path), exist_ok=True)
    if part_files:
        shutil.move(part_files[0], final_csv_path)
    else:
        # Empty DataFrame (e.g. zero rejected rows) — Spark writes only
        # _SUCCESS with no part file. Write a header-only CSV so the
        # download link is still valid.
        header = ",".join(df.columns)
        with open(final_csv_path, "w") as f:
            f.write(header + "\n")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    return final_csv_path
