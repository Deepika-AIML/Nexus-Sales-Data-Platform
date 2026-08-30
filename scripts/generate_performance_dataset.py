#!/usr/bin/env python3
"""
Generates a larger synthetic CSV for performance testing the PySpark
pipeline at a scale beyond the 25 MB single-upload limit (spec section 36).

This is explicitly NOT a substitute for functional/mapping/quality testing
— it is structurally consistent with the canonical schema (same columns,
same realistic value ranges as the Superstore reference data) but the
records themselves are synthetic and carry no real business meaning. Do
not draw business conclusions from Nexus's output on this file — its only
purpose is measuring pipeline throughput.

Since Nexus's upload endpoint enforces a strict 25 MB limit, this file is
meant to be loaded directly into the pipeline for a Spark-level throughput
benchmark (e.g. by pointing scripts/ at it directly in a notebook or a
`spark-submit` job), not through the /api/upload endpoint.

Usage:
    python3 scripts/generate_performance_dataset.py --target-rows 500000
"""
import argparse
import os

import numpy as np
import pandas as pd

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf_data")

CATEGORIES = {
    "Furniture": ["Bookcases", "Chairs", "Tables", "Furnishings"],
    "Office Supplies": ["Labels", "Storage", "Art", "Binders", "Paper"],
    "Technology": ["Phones", "Accessories", "Machines", "Copiers"],
}
REGIONS = ["East", "West", "Central", "South"]
SEGMENTS = ["Consumer", "Corporate", "Home Office"]
SHIP_MODES = ["Standard Class", "Second Class", "First Class", "Same Day"]


def generate(target_rows: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    categories = list(CATEGORIES.keys())
    cat_choices = rng.choice(categories, size=target_rows)
    sub_choices = [rng.choice(CATEGORIES[c]) for c in cat_choices]

    order_dates = pd.to_datetime("2022-01-01") + pd.to_timedelta(
        rng.integers(0, 1000, size=target_rows), unit="D"
    )
    ship_dates = order_dates + pd.to_timedelta(rng.integers(1, 7, size=target_rows), unit="D")

    sales = np.round(rng.gamma(shape=2.0, scale=80.0, size=target_rows), 2)
    quantity = rng.integers(1, 14, size=target_rows)
    discount = np.round(rng.choice([0, 0, 0, 0.1, 0.2, 0.3, 0.4, 0.5], size=target_rows), 2)
    profit = np.round(sales * rng.uniform(-0.2, 0.35, size=target_rows), 2)

    df = pd.DataFrame({
        "Row ID": np.arange(1, target_rows + 1),
        "Order ID": [f"PERF-{2022 + (i % 3)}-{100000 + i}" for i in range(target_rows)],
        "Order Date": order_dates.strftime("%m/%d/%Y"),
        "Ship Date": ship_dates.strftime("%m/%d/%Y"),
        "Ship Mode": rng.choice(SHIP_MODES, size=target_rows),
        "Customer ID": [f"CUST-{i % 5000:05d}" for i in range(target_rows)],
        "Customer Name": [f"Synthetic Customer {i % 5000}" for i in range(target_rows)],
        "Segment": rng.choice(SEGMENTS, size=target_rows),
        "Country": "United States",
        "City": [f"City {i % 200}" for i in range(target_rows)],
        "State": [f"State {i % 50}" for i in range(target_rows)],
        "Postal Code": rng.integers(10000, 99999, size=target_rows),
        "Region": rng.choice(REGIONS, size=target_rows),
        "Product ID": [f"PROD-{i % 3000:05d}" for i in range(target_rows)],
        "Category": cat_choices,
        "Sub-Category": sub_choices,
        "Product Name": [f"Synthetic Product {i % 3000}" for i in range(target_rows)],
        "Sales": sales,
        "Quantity": quantity,
        "Discount": discount,
        "Profit": profit,
    })
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-rows", type=int, default=500_000,
                         help="Number of synthetic rows to generate (default: 500,000)")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    df = generate(args.target_rows)
    out_path = os.path.join(OUT_DIR, f"performance_{args.target_rows}_rows.csv")
    df.to_csv(out_path, index=False)
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"Wrote {args.target_rows:,} synthetic rows to {out_path} ({size_mb:.1f} MB)")
    print("This file is for PySpark throughput benchmarking only — its records are synthetic.")


if __name__ == "__main__":
    main()
