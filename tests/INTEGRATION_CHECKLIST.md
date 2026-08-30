# Nexus — Manual Integration Checklist

`backend/tests/` covers everything that can run without Docker: the
mapping/quality/cleaning engines (pure pandas), upload validation, and
the FastAPI HTTP contract against a SQLite-backed test database. It does
**not** — and cannot, without a real Docker daemon, network access, and
`pyspark`/`fastapi`/`mysql` installed — exercise actual PySpark execution
against a live MySQL instance. This checklist is that missing piece: walk
through it once after `docker compose up --build` on a real machine to
confirm the full stack, end to end.

- [ ] **1. Build & start.** `docker compose up --build` completes with no
      errors. All three containers (`nexus-mysql`, `nexus-backend`,
      `nexus-frontend`) show as healthy: `docker compose ps`.
- [ ] **2. Swagger loads.** http://localhost:8000/docs renders and lists
      all 11 route groups (Upload, Profiling, Column Mapping, Data
      Quality, Processing, Processing Results, Analytics, Insights,
      History, Downloads, Health).
- [ ] **3. Frontend loads.** http://localhost:8080 renders the Overview
      page with the sidebar and no console errors.
- [ ] **4. Upload (TEST 1).** Upload `data/raw/Sample_-_Superstore.csv`.
      Expect: success message, profile shows 9,994 rows / 21 columns,
      encoding shown as `cp1252`.
- [ ] **5. Mapping.** Data Mapping page shows 20 of 21 columns
      auto-mapped (`Row ID` left unmapped). Confirm mapping — expect
      "Mapping confirmed."
- [ ] **6. Quality.** Data Quality page shows a score in the high 90s,
      with a `1 fully duplicate row(s) detected` info/warning issue (a
      real property of the reference dataset once `Row ID` is excluded).
- [ ] **7. Processing (the untested seam).** Click Start Processing.
      Confirm the stage list advances through Cleaning → Transforming →
      Building analytics model → Generating insights → Completed without
      the job status flipping to `failed`. This is the step that
      actually exercises PySpark + the MySQL JDBC write — if anything in
      `app/data_engine/spark/` has an issue, it surfaces here.
- [ ] **8. Verify Gold landed in MySQL.**
      `docker compose exec mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" nexus -e "SELECT COUNT(*) FROM gold_fact_sales;"`
      should return ~9,993 (9,994 minus the one true duplicate).
- [ ] **9. Verify Bronze/Silver/Gold parquet on disk.**
      `ls data/gold/<dataset_id>/` should show `fact_sales/`,
      `dim_date/`, `dim_product/`, `dim_customer/`, `dim_location/` (all
      five, since the reference dataset maps every field that supports
      them).
- [ ] **10. Downloads.** Clean/Rejected CSV, Mapping Report CSV, and
      Quality Report CSV all download successfully and open with
      sensible content.
- [ ] **11. Analytics.** KPIs and every chart render with real numbers
      (no "Unavailable" states, since the reference dataset maps every
      optional field).
- [ ] **12. Insights.** At least a sales-trend and a category-concentration
      insight appear, each with a paired recommendation and the
      standard disclaimer.
- [ ] **13. History.** The processed dataset appears with its quality
      score and `processed` status; clicking "Open" returns to Mapping
      with the same dataset active.
- [ ] **14. Required-field gate (TEST 5).** Upload
      `scripts/test_data/test5_missing_required.csv` (generate it first
      via `python3 scripts/generate_test_variants.py`). Confirm mapping
      with `sales` deliberately left unmapped — expect the confirm
      response to say `sales` could not be identified, and a direct
      `POST /api/process/{id}` call to return **422**, never a hung or
      failed Spark job.
- [ ] **15. Optional-field flexibility (TEST 4).** Upload
      `scripts/test_data/test4_missing_optional.csv`. Confirm mapping
      succeeds, processing completes normally, and Analytics shows
      "Profitability unavailable" / discount and customer analytics
      unavailable — while sales/order/category analytics still work.
- [ ] **16. Oversized file (TEST 6).** Upload
      `scripts/test_data/test6_oversized.csv` — expect an immediate
      "File exceeds the 25 MB upload limit" error, no dataset created.
- [ ] **17. Invalid file (TEST 7).** Upload
      `scripts/test_data/test7_invalid.txt` — expect an immediate
      "Unsupported file type" error.
- [ ] **18. Reprocessing idempotency.** Re-run processing on the same
      dataset a second time. `SELECT COUNT(*) FROM gold_fact_sales WHERE
      _dataset_id = '<id>'` should be unchanged, not doubled — confirming
      `processing_service._clear_prior_gold_rows()` actually works
      against real MySQL.

If every box above checks out, the seam this project's automated test
suite couldn't reach — real PySpark writing real data into real MySQL
through the real Docker network — is confirmed working.
