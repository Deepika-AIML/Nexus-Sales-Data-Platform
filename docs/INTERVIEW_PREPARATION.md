# Nexus — Interview Preparation Guide

Everything below is written to be defensible against a follow-up
question, because it's describing what's actually in the repository, not
what a good version of this project would ideally contain. Where V1
genuinely doesn't do something, that's said plainly — see §"What would
you improve in V2?"

---

## Elevator pitch

Nexus takes an arbitrary sales CSV, figures out which of its columns mean
`sales`, `order_date`, `customer_id`, etc. using a confidence-scored
matching engine (not hardcoded column names), reports exactly what's
wrong with the data without touching it, then runs it through a real
PySpark Bronze → Silver → Gold pipeline into a MySQL star schema, and
generates analytics and recommendations that are only ever computed from
what the dataset actually contains — never fabricated.

## 30-second explanation

"I built a data platform where you upload a sales CSV with whatever
column names it happens to have — 'Revenue' instead of 'Sales', 'Txn
Date' instead of 'Order Date' — and it auto-maps those onto a canonical
schema using a multi-signal confidence scorer, flags data quality issues,
then runs an actual PySpark pipeline that cleans the data and builds a
star schema in MySQL. The frontend is plain HTML/CSS/JS talking to a
FastAPI backend, and the whole thing runs locally with one
`docker compose up`."

## 1-minute explanation

Add to the 30-second version: "The core design principle is that Nexus
never fabricates data. If a dataset doesn't have a profit column, the
analytics page says 'profitability unavailable' instead of showing a
fake number or a zero. If a required field like sales can't be
identified after mapping, processing is blocked with a specific message
— but the upload itself still succeeds, because file validation and
semantic validation are deliberately separate stages. Rejected records
during cleaning aren't dropped, either — they're written out with the
specific reason each one failed. The whole thing is organized as
Bronze/Silver/Gold: Bronze is an immutable raw ingest, Silver is cleaned
and validated with a clean/rejected split, and Gold is a star schema —
`fact_sales` plus dimension tables that only get built for the
attributes the dataset actually has."

## Detailed technical explanation

Frontend (vanilla JS, 9 static pages sharing a common sidebar/API-client
pattern) → FastAPI backend (routers → services → data-engine/analytics/
insights layers, strictly separated) → PySpark for the actual
transformation work → MySQL for both application metadata and the Gold
analytics layer. The mapping engine scores every source column against
every canonical field using five weighted signals and classifies into
auto-mapped/needs-review/unmapped bands. The quality engine computes five
dimensions (completeness, uniqueness, validity, consistency, schema
match) and then applies a severity-weighted penalty on top, specifically
because pure row-fraction averaging let critical issues hide inside a
huge score during testing — that's a real bug that got caught and fixed,
not a hypothetical design choice. The Spark pipeline is genuinely three
distinct stages with distinct responsibilities, not one function called
three names.

## Architecture explanation

See `docs/TECHNICAL_LEARNING_GUIDE.md` §1 and the diagram in the README —
three Docker services (frontend/backend/mysql) on one bridge network, a
bind-mounted `data/` directory for pipeline artifacts, and a MySQL volume
for persistence. Inside the backend, four layers: API (routers) →
services (orchestration) → data_engine (mapping/quality/cleaning/Spark)
→ analytics/insights (read from Gold, generate recommendations).

---

## Likely interviewer questions and answers

**Why FastAPI?**
Pydantic validation catches malformed requests before handler code runs,
async + BackgroundTasks made the "start job, poll for status" pattern
clean to implement, and OpenAPI docs come free from the same type hints.

**Why not Django?**
Django's batteries (ORM, admin, templates) solve problems Nexus doesn't
have — there's no server-rendered HTML and SQLAlchemy was a better fit
for the specific star-schema + raw-SQL-analytics pattern used here.
FastAPI is also just faster to build a pure JSON API in when you don't
need Django's other pieces.

**Why PySpark?**
It's a fixed requirement, but it's also the right tool for the Silver/
Gold workload specifically: window-function-based "most frequent value"
casing normalization, full-dataset deduplication, and building multiple
derived tables from one pass over the clean data are exactly what Spark
DataFrames are for. The interactive profiling/mapping-preview stage
deliberately uses pandas instead, because that stage needs sub-second
response on a ≤25MB file for a live UI — using Spark there would add
JVM startup latency for no benefit.

**Why Docker?**
Reproducible local setup with zero manual installs (no local Python
version conflicts, no local Java, no local MySQL) — `docker compose up
--build` is the entire onboarding story.

**Why Bronze/Silver/Gold?**
Each layer has one job. Bronze is fidelity to the source (nothing typed,
nothing dropped). Silver is where mapping, casting, cleaning, and
validation happen, with a clean/rejected split that's fully explained.
Gold is analytics-ready and dynamically shaped to what the data actually
supports. Separating these means a bug in cleaning logic can't corrupt
the raw record of what was uploaded, and reprocessing after a mapping
change rebuilds Silver/Gold from the same immutable Bronze snapshot.

**Why MySQL?**
It was a fixed requirement, and it's a genuinely reasonable choice for
this shape of workload — a moderate-sized, mostly-read analytics layer
with a normal star schema, queried with plain SQL (no need for a
document store's flexibility or a data-warehouse-scale columnar engine
at this size).

**How does column mapping work?**
Five weighted signals per source-column/canonical-field pair: synonym/
exact-name match (55 pts), fuzzy name similarity (20 pts), keyword token
overlap (10 pts), datatype fit against sample values (10 pts), and a
stricter value-pattern check (5 pts). ≥85 auto-maps, 60–84 needs review,
<60 stays unmapped. Conflicts (two columns both plausibly meaning the
same canonical field) are flagged, not silently resolved.

**How do you handle missing columns?**
Core fields missing after mapping blocks processing with a specific
message naming the field. Optional fields missing just means the
analytics that depend on them report themselves unavailable — nothing
else changes.

**What happens when profit is absent?**
`ANALYTICS_DEPENDENCIES` in `canonical_schema.py` says `profitability`
needs `profit`; `analytics_service.py` checks that before running any
query and returns `{"available": false, "reason": "..."}` instead of a
zero or null dressed up as data. The frontend renders that as an
explicit "Unavailable" state, not a blank or a misleading `$0`.

**How do you handle duplicates?**
Checked post-mapping (not on raw data, where an incidental unique ID
column would mask real duplicates), first occurrence kept, the rest
rejected with reason `duplicate_row` — visible in the rejected-records
download, never silently dropped.

**How do you maintain data lineage?**
Every Bronze row carries `_dataset_id`/`_source_file`/`_ingested_at`/
`_bronze_row_id`. Every rejected row carries `rejection_reasons`. Every
Gold row carries `_dataset_id`. The raw upload is never overwritten.

**How does the frontend communicate with the backend?**
Plain `fetch()` calls through a small `Api` wrapper (`js/api.js`) that
derives the backend's origin from `window.location.hostname` at
runtime rather than hardcoding it, so the same static build works
whether accessed via `localhost` or a LAN IP.

**What happens during file upload?**
Client-side quick checks for instant feedback → `POST /api/upload` →
server-side extension/size/readability validation only (no semantic
checks yet) → raw bytes saved under a UUID-prefixed filename, never
overwriting → a `datasets` row created in MySQL.

**How does Nexus scale?**
Honestly, V1 doesn't — it's built for a ≤25MB file on `local[*]` Spark.
The scaling path is real but not yet built: point `SPARK_MASTER` at a
cluster (pipeline code is unchanged), replace the coalesce-to-one-file
CSV export with multi-part output, and put a real job queue in front of
the current background-task model for larger files. See
`docs/TECHNICAL_LEARNING_GUIDE.md` §34.

**What happens if the dataset is invalid?**
Depends on what "invalid" means. Non-CSV or >25MB: rejected immediately
at upload with a specific message. Genuinely unreadable/corrupt bytes:
rejected at upload (with a subtlety — see the cp1252-always-decodes bug
below). Dirty-but-readable data (nulls, duplicates, inconsistent
formatting): accepted at upload, fully reported during profiling/
quality, and handled row-by-row during cleaning (reject with reason,
never silently drop).

**What happens if a required field is missing?**
Upload and profiling succeed. Mapping is attempted. If no column maps to
a core field (most commonly `sales`), mapping confirmation reports
`can_proceed: false` with the specific missing field, and
`/api/process` returns a 422 with that same message if called anyway —
it never silently starts a doomed Spark job.

**How do you prevent data loss?**
The raw file is never overwritten (UUID-prefixed filenames, an existence
check before write). Rejected records are written out with reasons, not
deleted. Bronze is immutable and reprocessing always rebuilds from it.

**Why don't you simply reject dirty data?**
Because "dirty" and "unusable" are different things, and the spec is
explicit about this: null values, duplicates, and inconsistent
formatting are normal in real-world exports and are exactly what the
Quality and Cleaning stages exist to surface and handle — rejecting the
whole file for that would defeat the platform's purpose. Only a
file-level problem (wrong type, too large, unreadable, or truly no data
rows) is rejected at upload.

**How would you deploy this to the cloud?**
Same container boundaries, different backing services: RDS/Cloud SQL for
MySQL instead of the `mysql` container, object storage (S3/GCS) instead
of the `data/` bind mount, and either a managed Spark service or the
same `local[*]` approach on a bigger instance, depending on real data
volume. The backend's config is already fully environment-variable-
driven, so none of that requires code changes — just different `.env`
values and swapping the compose file for the target platform's
equivalent.

**What would you improve in V2?**
In order of what would actually matter first: authentication and
per-user dataset isolation (V1 has none, by design, per spec); a real
job queue instead of `BackgroundTasks` for large files; slowly-changing-
dimension handling so re-uploading an updated version of the same
dataset merges into dimension history instead of creating an
independent `_dataset_id` scope; XLSX support; and only after those,
a forecasting module — V1 deliberately has zero predictive modeling
rather than a half-implemented one.
