#!/usr/bin/env python3
"""
Generates the test-variant CSVs described in spec section 35 (TEST 1-7)
from the reference Superstore dataset, so every scenario in the Testing
Strategy section of docs/TECHNICAL_LEARNING_GUIDE.md can be exercised by
hand through the running UI/API, not just by the automated pytest suite.

Usage (from the project root, with pandas available):
    python3 scripts/generate_test_variants.py

Writes into scripts/test_data/:
    test1_original.csv           - unmodified reference dataset
    test2_renamed_columns.csv    - Order ID/Order Date/Sales/Quantity renamed
    test3_dirty.csv              - duplicates, nulls, bad formatting, bad dates
    test4_missing_optional.csv   - Profit/Discount/Customer ID removed
    test5_missing_required.csv   - Sales removed entirely
    test6_oversized.csv          - a >25MB CSV for the upload-limit check
    test7_invalid.txt            - a non-CSV file for the file-type check
"""
import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_CSV = os.path.join(REPO_ROOT, "data", "raw", "Sample_-_Superstore.csv")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")


def load_source() -> pd.DataFrame:
    for enc in ("utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(SOURCE_CSV, encoding=enc)
        except Exception:
            continue
    raise SystemExit(f"Could not read source dataset at {SOURCE_CSV}")


def make_test1(df: pd.DataFrame):
    df.to_csv(os.path.join(OUT_DIR, "test1_original.csv"), index=False)


def make_test2(df: pd.DataFrame):
    renamed = df.rename(columns={
        "Order ID": "Transaction ID",
        "Order Date": "Purchase Date",
        "Sales": "Revenue",
        "Quantity": "Units Sold",
    })
    renamed.to_csv(os.path.join(OUT_DIR, "test2_renamed_columns.csv"), index=False)


def make_test3(df: pd.DataFrame):
    dirty = pd.concat([df, df.iloc[:20]], ignore_index=True)  # exact duplicates
    dirty.loc[5:15, "Sales"] = np.nan                          # missing core value
    dirty.loc[20:25, "Category"] = "  Furniture "               # whitespace
    dirty.loc[26:30, "Category"] = "FURNITURE"                   # casing inconsistency
    dirty.loc[40, "Sales"] = -50                                  # negative sales
    dirty.loc[41, "Quantity"] = 0                                  # non-positive quantity
    dirty.loc[42, "Order Date"] = "NOT_A_DATE"                      # invalid date
    dirty.loc[43, "Ship Date"] = "2015-01-01"                        # ship before order
    dirty.to_csv(os.path.join(OUT_DIR, "test3_dirty.csv"), index=False)


def make_test4(df: pd.DataFrame):
    df.drop(columns=["Profit", "Discount", "Customer ID"]).to_csv(
        os.path.join(OUT_DIR, "test4_missing_optional.csv"), index=False
    )


def make_test5(df: pd.DataFrame):
    df.drop(columns=["Sales"]).to_csv(
        os.path.join(OUT_DIR, "test5_missing_required.csv"), index=False
    )


def make_test6(df: pd.DataFrame):
    """Repeats the reference dataset until the file exceeds 25 MB, to
    exercise the upload-size rejection path. Deliberately NOT the default
    dataset Nexus ships with — the 25 MB limit is an application
    constraint, not a property of the reference dataset itself (spec
    section 36)."""
    path = os.path.join(OUT_DIR, "test6_oversized.csv")
    target_bytes = 26 * 1024 * 1024
    chunk = df.to_csv(index=False)
    header, _, body = chunk.partition("\n")
    with open(path, "w") as f:
        f.write(header + "\n")
        written = len(header) + 1
        while written < target_bytes:
            f.write(body)
            if not body.endswith("\n"):
                f.write("\n")
            written += len(body) + 1
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"  test6_oversized.csv: {size_mb:.1f} MB")


def make_test7():
    path = os.path.join(OUT_DIR, "test7_invalid.txt")
    with open(path, "w") as f:
        f.write("This is a plain text file, not a CSV — Nexus should reject it at upload time.\n")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_source()
    print(f"Loaded reference dataset: {df.shape[0]} rows, {df.shape[1]} columns")

    make_test1(df); print("  wrote test1_original.csv")
    make_test2(df); print("  wrote test2_renamed_columns.csv")
    make_test3(df); print("  wrote test3_dirty.csv")
    make_test4(df); print("  wrote test4_missing_optional.csv")
    make_test5(df); print("  wrote test5_missing_required.csv")
    make_test6(df)
    make_test7(); print("  wrote test7_invalid.txt")

    print(f"\nAll test variants written to {OUT_DIR}")


if __name__ == "__main__":
    main()
