# Nexus — Technical Learning Guide

This document explains Nexus the way you'd explain it to yourself six
months from now, or to an interviewer who wants to know you actually built
it rather than copy-pasted it. Every section maps to a real file in the
repository — nothing here describes a feature that doesn't exist in code.

---

## 1. Overall architecture

Nexus is three containers: a static **frontend** (nginx serving vanilla
HTML/CSS/JS), a **backend** (FastAPI, orchestrating everything, running
PySpark in-process for the data pipeline), and **MySQL** (application
metadata + the Gold analytics layer). The frontend never touches MySQL or
Spark directly — it only ever calls the backend's REST API. The backend
never renders HTML — it's a pure JSON API. This strict separation is what
makes "vanilla JS frontend, FastAPI backend" an honest description rather
than a loose one.

Inside the backend, there's a second separation that matters just as
much: **routers** (`app/api/`) only parse requests and call **services**
(`app/services/`); services orchestrate but contain no data-transformation
logic themselves; the actual mapping/quality/cleaning/Spark logic lives in
**`app/data_engine/`**, and analytics/insight logic lives in
**`app/analytics/`** and **`app/insights/`**. You could delete every
router and still unit-test the entire data-engineering logic — that's the
point of the split (and exactly what `tests/test_mapping_engine.py`,
`test_quality_engine.py`, and `test_cleaning_engine.py` do).

## 2. Why FastAPI was chosen

Three concrete reasons, not a popularity contest: (1) Pydantic-based
request/response validation means a malformed request is rejected with a
structured 422 before any handler code runs — no hand-written validation
scattered across routes; (2) automatic OpenAPI/Swagger docs (`/docs`)
come for free from the same type hints that give you validation, so the
API is self-documenting; (3) native `async def` support and
`BackgroundTasks` made the "start processing, poll for status" pattern
(spec's requirement that the UI never freeze) straightforward to
implement correctly — see `app/api/process.py`.

## 3. Why vanilla HTML/CSS/JS was chosen

This was a fixed technology constraint, not a preference — the product
brief explicitly forbids React/Vue/Angular/Bootstrap. Working within that
constraint shaped real decisions: `frontend/js/common.js` implements a
tiny shared-sidebar "component" pattern (`renderSidebar()` injects markup
into a mount point) so nine static HTML pages don't duplicate navigation
markup, and `frontend/js/api.js` centralizes every `fetch()` call so no
page hand-rolls its own request/error handling. It's proof that
"framework-free" doesn't have to mean "unstructured."

## 4. How frontend communicates with FastAPI

Every page loads `js/api.js`, which exposes an `Api` object
(`Api.upload(file)`, `Api.getProfile(id)`, etc.) — a thin wrapper around
`fetch()` that adds JSON headers, parses `{detail: "..."}` error bodies
into JS `Error` objects, and derives the backend's base URL from
`window.location.hostname` (never hardcoded `localhost`, so the same
build works whether you access Nexus via `localhost` or a LAN IP). CORS
is configured on the backend (`app/core/config.py` → `CORS_ORIGINS`,
`app/main.py` → `CORSMiddleware`) to allow exactly the frontend's origin.

## 5. How file upload works

`frontend/js/upload.js` handles drag-and-drop and click-to-browse, does
client-side extension/size checks for instant feedback, then calls
`Api.upload(file)`, which POSTs a `FormData` to `/api/upload`. The
backend route (`app/api/upload.py`) reads the bytes, calls
`storage_service.validate_upload()` and `detect_encoding_and_read()`,
generates a UUID `dataset_id`, saves the raw bytes under
`data/raw/<dataset_id>__<sanitized_filename>` (never overwriting an
existing file), and creates a `datasets` row in MySQL.

## 6. How CSV validation works

Deliberately two-tier. **File-level** validation (`storage_service.py`,
spec section 3) happens at upload time and checks only: is it a `.csv`,
is it ≤25 MB, and can it actually be parsed as a CSV in one of
`utf-8 / utf-8-sig / cp1252 / latin1`? A subtlety worth knowing: cp1252
and latin1 can decode *any* byte sequence, so pure binary garbage will
often "successfully" parse into a nonsense single-column, zero-row
result — `detect_encoding_and_read()` explicitly rejects a zero-data-row
result too, or that garbage would sail through as a "valid" upload (this
was caught by `tests/test_upload_validation.py` during development — see
"Testing Strategy" below). **Semantic** validation — nulls, duplicates,
"does this look like sales data" — never happens at this stage; it's the
Data Profiling/Quality stages' job entirely.

## 7. How profiling works

`GET /api/profile/{dataset_id}` re-reads the raw CSV with pandas (fast
enough at the 25 MB ceiling) and calls `quality_engine.profile_dataset()`,
which computes row/column counts, per-column inferred type
(numeric/date/categorical/text, via lightweight regex + `pd.to_datetime`
sampling), null percentage, unique-value count, and five sample values —
all shown on the Upload page immediately after a successful upload.

## 8. How column mapping works

`app/data_engine/mapping_engine.py` is the heart of Nexus's
differentiation from a hardcoded importer. For every source column it
computes a normalized name (`Sub-Category` → `sub_category`) and scores it
against **every** canonical field using five independent signals (see
next section), keeping the best match. `mapping_engine.suggest_mapping()`
returns a ranked suggestion per column plus a **conflict list** — if two
source columns both plausibly mean `sales`, that's flagged for the user
to resolve rather than silently picking one (`_detect_conflicts()`).

**Example:** given a column named `Revenue` with values like `$1,204.50`,
the engine finds `revenue` in the `sales` synonym list (55 pts), adds a
small fuzzy-match bonus, checks the values parse as currency (10 pts) and
contain decimals (a `.` pattern bonus), landing well above the 85%
auto-map threshold.

## 9. How confidence scores work

Confidence is a 0–100 sum of five weighted signals
(`score_column_against_field()`):

| Signal | Max pts | What it checks |
|---|---|---|
| Name exact/synonym match | 55 | normalized name is in the field's synonym list |
| Fuzzy name similarity | 20 | `difflib.SequenceMatcher` ratio against synonyms (only if no exact match) |
| Keyword token overlap | 10 | shared tokens between the column name and a per-field keyword set |
| Datatype fit | 10 | fraction of sample values consistent with the field's expected type |
| Pattern strength | 5 | a stricter secondary check (e.g. ID length consistency, currency decimals) |

`≥85` → auto-mapped, `60–84` → suggested/needs review, `<60` → unmapped
— these thresholds are constants (`AUTO_MAP_THRESHOLD`,
`REVIEW_THRESHOLD`) at the top of the file, not scattered magic numbers.

## 10. Required vs. optional schema

`app/data_engine/canonical_schema.py` defines three tiers: **core**
(`order_id`, `order_date`, `product_name`, `sales` — processing is
blocked without these), **recommended** (`quantity` — processing
proceeds, but it's flagged), and **optional** (everything else). This
tiering is a plain Python dict, not hardcoded logic — adding a new field
means editing one data structure, not touching the
mapping/quality/pipeline code.

## 11. Data-quality concepts

`quality_engine.assess_quality()` computes five dimensions after mapping
is confirmed: **completeness** (null rate on mapped fields),
**uniqueness** (duplicate row rate), **validity** (business-rule pass
rate: valid dates, non-negative sales, etc.), **consistency**
(whitespace/casing irregularities in categorical fields), and **schema
match** (how much of the canonical schema got covered). These combine
into a weighted dimension score, **then** a severity-weighted penalty is
subtracted per distinct issue found (critical −3, warning −1, info
−0.25, capped at −40) — see the next paragraph for why that second step
exists.

**A real bug this caught:** the first version of the scoring only
averaged row-fractions. A dataset with 3 rows of negative sales out of
10,000 barely moved a fractional average, so a dataset with genuinely
critical problems still scored ~100/100. The severity-weighted penalty
was added specifically so a handful of critical issues can never hide
inside a huge score — this mirrors how real tools like dbt tests or Great
Expectations treat a failing critical rule as significant regardless of
row count. `tests/test_quality_engine.py::test_dirty_dataset_scores_lower_and_flags_issues`
locks this behavior in.

## 12. Duplicate handling

Detected **after** mapping is applied, not on the raw file — the raw
Superstore CSV has a unique `Row ID` on every row, which would mask real
duplicates if checked pre-mapping. `cleaning_engine.clean_and_split()`
(pandas, for interactive preview) and `silver.py`'s `validate_and_split()`
(PySpark, for the real pipeline run) both use the same rule: keep the
first occurrence, reject the rest with reason `duplicate_row` — never
silently drop them.

## 13. Missing-value handling

The single rule that shows up in more places than any other in this
codebase: **a missing optional value stays missing.** No `fillna(0)`, no
guessed customer name, no assumed zero profit. `cleaning_engine.py`'s
module docstring states this explicitly, and
`tests/test_cleaning_engine.py::test_never_fabricates_missing_optional_values`
enforces it. Missing **core** fields, by contrast, cause the row to be
rejected (not fabricated, not silently kept).

## 14. Date normalization

A genuinely subtle bug lives here: `pandas.to_datetime()` without
`format="mixed"` infers ONE format from the column and silently returns
`NaT` for any row that doesn't match it — so a column that's mostly
`M/D/YYYY` with one `YYYY-MM-DD` row mixed in loses that row entirely,
with no error raised. `app/data_engine/date_utils.py` centralizes the
fix (`parse_dates_robust()`, using `format="mixed"`) and every date-
parsing call site in the pandas engines uses it.
`tests/test_quality_engine.py::test_mixed_date_formats_do_not_silently_become_invalid`
is a regression test for exactly this. The PySpark Silver stage
(`silver.py`) uses a different, Spark-appropriate technique: an explicit,
ordered list of `to_date(col, fmt)` attempts coalesced together — Spark
has no equivalent of pandas' `format="mixed"`, so the list is deliberately
explicit and documented rather than a black box.

## 15. Data validation

Business-rule validation (as opposed to type/format validation) runs
identically in both engines: `sales >= 0`, `quantity > 0` (when mapped),
`order_date` must parse, and `ship_date` must not precede `order_date`
(when both are mapped). A row failing any rule is rejected with a
specific reason string (`negative_sales`, `non_positive_quantity`,
`ship_before_order`, `missing_core_field:<field>`) — never just dropped
silently.

## 16. Raw vs. clean vs. rejected data

**Raw** = the exact uploaded bytes, at `data/raw/<id>__<filename>`, never
overwritten. **Clean** = Silver-stage rows that passed every rule,
downloadable as CSV. **Rejected** = Silver-stage rows that failed at
least one rule, downloadable as CSV **with a `rejection_reasons` column**
so nothing is a mystery. All three coexist — Nexus never deletes the raw
file, and rejected records are a first-class, inspectable output, not a
silent discard pile.

## 17. Bronze / Silver / Gold architecture

`app/data_engine/spark/bronze.py`, `silver.py`, `gold.py`. **Bronze**:
schema-on-read, every column as a string, plus lineage columns
(`_dataset_id`, `_source_file`, `_ingested_at`, `_bronze_row_id`) — a
faithful, lossless copy. **Silver**: the confirmed mapping is applied,
values are cast and cleaned, business rules split clean vs. rejected.
**Gold**: Silver's clean data is modeled into a star schema and written
to both parquet and MySQL. Reprocessing a dataset always rebuilds
Silver/Gold from the SAME Bronze snapshot — Bronze is written once and
treated as immutable.

## 18. Why PySpark is used

Two honest reasons, not one aspirational one. First, it's a fixed
technology requirement of the product brief. Second — and this is the
real engineering argument — Silver/Gold is exactly the kind of workload
Spark is built for: wide transformations (casing normalization via
`Window` + `row_number()` to find the most frequent value per group),
deduplication across the full row set, and building multiple derived
tables from one pass over the clean data. pandas is used deliberately for
the earlier, small, *interactive* stages (profiling and mapping-suggestion
preview on a ≤25 MB file, where sub-second response matters for a live
UI); PySpark is used for the *authoritative* clean/transform/model stage
that actually determines what ends up in Gold and MySQL. This is a
genuine architectural choice, and it's one of the more interesting things
to be able to explain and defend (see `docs/INTERVIEW_PREPARATION.md`).

## 19. What transformations PySpark performs

Reading the raw CSV (`bronze.py`); renaming/selecting per the confirmed
mapping (`silver.apply_mapping()`); trimming and casing-normalizing
categorical fields via a `Window`-based "most frequent form" pattern
(`_normalize_categorical_casing()`); coercing currency-like strings to
`double` (`_clean_numeric()`); multi-format date parsing
(`_parse_date_multi_format()`); business-rule validation and the
clean/rejected split, including duplicate detection via
`Window.partitionBy(*business_cols)` (`validate_and_split()`); building
`dim_date`/`dim_product`/`dim_customer`/`dim_location` and `fact_sales`
with deterministic surrogate keys via `xxhash64` (`gold.py`); and writing
Gold to MySQL over JDBC (`write_gold_to_mysql()`).

## 20. Data modeling

Nexus models Gold as a star schema, but a **dynamic** one: dimensions are
only built when the fields that support them were actually mapped
(`gold.build_dim_product()` etc. each return `None` if their required
source fields are absent). `build_gold_layer()` only includes the
dimensions that came back non-`None`. This directly implements the spec's
"do not create fake dimension data" requirement in code, not just as a
policy.

## 21. Star schema concepts

`fact_sales` holds one row per (clean) order line: measures (`sales`,
`quantity`, `discount`, `profit`) plus foreign keys (`date_key`,
`product_key`, `customer_key`, `location_key`) into the dimension tables.
Surrogate keys are deterministic hashes (`xxhash64`) of each dimension's
natural key columns — not row-order-dependent auto-increment IDs — so
reprocessing the same dataset produces the same keys every time, which
matters because Gold tables in MySQL are **shared across every processed
dataset** (see next section) and reprocessing must be idempotent.

## 22. MySQL's role

Two distinct jobs in one database (`database/init.sql`). **Application
metadata**: `datasets`, `column_mappings`, `quality_reports`,
`quality_issues`, `processing_jobs` — written via SQLAlchemy ORM from the
FastAPI service layer. **Gold analytics data**: `gold_fact_sales` +
`gold_dim_*` — written via PySpark's JDBC writer, never through the ORM.
Every Gold table carries a `_dataset_id` column so one physical table
serves analytics for every dataset ever processed; `analytics_service.py`
always filters by it. Reprocessing a dataset issues a `DELETE FROM
gold_* WHERE _dataset_id = ?` (via SQLAlchemy) immediately before Spark's
JDBC append, because Spark's JDBC writer has no native "upsert" — see
`processing_service._clear_prior_gold_rows()`.

## 23. API architecture

One router file per resource under `app/api/` (`upload.py, profile.py,
mapping.py, quality.py, process.py, results.py, analytics.py,
insights.py, history.py, download.py`), each declaring a `prefix` and
delegating everything beyond request parsing to a service. `app/main.py`
assembles them, configures CORS, and registers two exception handlers:
`NexusError` subclasses map to clean `{"detail": "..."}` JSON with the
right status code (see "Error Handling" below), and a catch-all handler
ensures an unhandled exception never leaks a traceback to the client.

## 24. Analytics generation

`app/analytics/analytics_service.py` never computes a metric from raw or
Silver data — everything queries `gold_*` tables in MySQL via SQLAlchemy
Core (`text(...)` SQL), because that's the layer that's actually been
validated and modeled. Before running any query, `_available()` checks
`ANALYTICS_DEPENDENCIES` (in `canonical_schema.py`) against the dataset's
confirmed mapping; if a dependency is missing, the endpoint returns
`{"available": false, "reason": "..."}` instead of running a query that
would return zeros or nulls dressed up as real numbers.

## 25. Insight generation

`app/insights/insights_engine.py` takes the **exact** dict
`analytics_service.get_analytics()` returned in the same request and
derives `Insight` objects (a raw `metric` string plus what it means) —
period-over-period trend change, category/region concentration, margin
health, negative-margin categories, discount-vs-profit correlation,
segment leadership. Nothing is computed that wasn't already in the
analytics payload; there is no forecasting model, because none is
implemented, and the spec is explicit that Nexus shouldn't pretend
otherwise.

## 26. Recommendation generation

`app/insights/recommendation_engine.py` takes the **same** `Insight`
objects (never recomputes anything) and maps each insight ID to a
concrete suggested action via a lookup table (`_ACTION_BY_INSIGHT_ID`),
always appended with the same disclaimer: *"based on the available
dataset and should be validated using business context."* Metric →
Insight → Recommendation stay three visibly separate fields all the way
to the UI (`frontend/js/insights.js`), matching the spec's explicit
distinction.

## 27. Docker architecture

Three services, three concerns. `frontend/Dockerfile`: `nginx:alpine`
serving static files — no build step, because there's nothing to compile.
`backend/Dockerfile`: `python:3.11-slim` + a headless JRE (PySpark needs
a JVM) + the MySQL JDBC driver downloaded at build time + the Python
dependencies. `mysql` uses the stock `mysql:8.0` image with
`database/init.sql` mounted into `/docker-entrypoint-initdb.d/`.

**A real portability bug fixed during development:** the backend
Dockerfile originally hardcoded
`JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64` — which silently breaks
on arm64 hosts (e.g. Apple Silicon Macs), where apt installs the JRE
under a `-arm64` path instead. The fix (`backend/docker-entrypoint.sh`)
resolves `JAVA_HOME` at **container start** via `readlink -f
"$(command -v java)"`, which works identically regardless of CPU
architecture, rather than baking an architecture-specific guess in at
build time. This was verified by actually running the entrypoint's
resolution logic in the development environment against a real Java
installation and confirming it correctly derives the JVM root
directory — see "Testing Strategy" for what "verified" means here.

## 28. Docker Compose networking

All three services share one bridge network (`nexus-network`), so they
resolve each other by service name (the backend connects to MySQL at
host `mysql`, port `3306` — see `MYSQL_HOST` in `.env.example`). Only the
backend (`8000`) and frontend (`8080`, mapped to nginx's `80`) — and, for
local debugging convenience, MySQL's `3306` — are published to the host;
nothing else needs to be reachable from outside Docker's network. The
backend's `depends_on: mysql: condition: service_healthy` (using MySQL's
`mysqladmin ping` healthcheck) ensures the backend doesn't start racing
an unready database.

## 29. Volumes

One named volume, `mysql_data`, persists MySQL's data directory across
container restarts. One bind mount, `./data:/data`, gives the backend
container access to `raw/ bronze/ silver/ gold/ rejected/ outputs/` on
the host filesystem — which means pipeline outputs are inspectable
directly from the host (e.g. `data/gold/<dataset_id>/fact_sales/*.parquet`)
without needing to shell into the container.

## 30. Environment variables

Every configurable value is read from the environment in
`app/core/config.py` — nothing is hardcoded, including database
credentials. `.env.example` documents `MYSQL_HOST`, `MYSQL_PORT`,
`MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`,
`APP_ENV`, `UPLOAD_MAX_MB`, `CORS_ORIGINS`, and `SPARK_MASTER`. A static
audit performed during development (parsing both `docker-compose.yml`
and `.env.example`) confirmed every variable `docker-compose.yml`
references is defined in `.env.example` and vice versa — see "Testing
Strategy."

## 31. Testing strategy

Three tiers, and it matters which is which:

1. **Pure data-engine unit tests** (`test_mapping_engine.py`,
   `test_quality_engine.py`, `test_cleaning_engine.py`,
   `test_required_optional_fields.py`) — pandas only, no DB, no Docker.
   These were actually executed during development against the real
   `Sample_-_Superstore.csv` (not synthetic fixtures) and directly caught
   two real bugs: the mixed-date-format silent-failure bug (§14) and the
   severity-dilution scoring bug (§11).
2. **Upload validation tests** (`test_upload_validation.py`) — also pure
   Python; caught a third real bug (§6): binary garbage decoding
   "successfully" under cp1252 into a zero-row result.
3. **API-level tests** (`test_api_endpoints.py`) — FastAPI `TestClient`
   against a SQLite-backed session (overriding the `get_db` dependency),
   covering the full upload → profile → mapping → confirm → quality →
   history HTTP flow, plus the `/api/process` validation/scheduling
   contract with the actual Spark execution function monkeypatched out
   (that endpoint's real Bronze/Silver/Gold run needs the full Docker
   stack to test meaningfully — see the honesty note below).

**Run them:** `docker compose run --rm backend pytest -v` (needs Docker,
since `pytest`/`fastapi`/`pyspark` are only installed inside the backend
image). `scripts/generate_test_variants.py` and
`generate_performance_dataset.py` produce the TEST 1–7 CSV scenarios from
spec section 35 for manual click-through testing of the running UI —
both scripts were actually run during development and their output
spot-checked (correct row counts, correct columns removed/renamed, a
genuinely oversized file, a genuine encoding/structure mismatch).

**Honesty note on what was and wasn't executed during development:** the
pandas-based unit tests above genuinely ran and genuinely caught bugs
(18 of 18 mapping/quality/cleaning/required-field tests passed; 7 of 7
upload-validation tests passed, after the cp1252 fix). A live end-to-end
run through Docker Compose — actual `pyspark` executing against a real
MySQL via JDBC — was **not** performed in the environment that generated
this project, because that environment had no Docker daemon, no network
access, and no `pyspark`/`fastapi`/`httpx` installed. Every file in
`app/data_engine/spark/` was written to the real PySpark 3.5 API and
syntax-verified (`python3 -m py_compile`), and every cross-file import
and every frontend↔backend API contract (all 12 endpoints, all HTTP
methods and path parameters) was statically audited via an AST-based
import checker and a route cross-checker — but "the Spark job runs and
MySQL accepts the JDBC write" can only be confirmed by actually running
`docker compose up --build` on a machine with Docker and network access.
If you hit an issue there, it's most likely to be in that untested
seam — start with `docker compose logs backend`.

## 32. Error handling

`app/core/exceptions.py` defines a small hierarchy
(`FileValidationError`, `DatasetNotFoundError`, `MappingNotConfirmedError`,
`RequiredFieldMissingError`, `ProcessingError`), each with a
`status_code` and a clean `user_message`. `app/main.py` registers a
handler for the base `NexusError` that returns exactly
`{"detail": "<user_message>"}` — never a traceback — and a catch-all
handler for anything unexpected, which logs the full exception
server-side (`core/logging_config.py`) and returns a generic 500 to the
client. `processing_service.execute_processing_job()` (the Spark
background job) wraps its entire body in try/except specifically because
a background task that raises is silently swallowed by FastAPI otherwise
— it must record failure into the `processing_jobs` row itself.

## 33. Data lineage

Every Bronze row carries `_dataset_id`, `_source_file`, `_ingested_at`,
and `_bronze_row_id`. Every rejected Silver row carries
`rejection_reasons`. Every Gold row carries `_dataset_id`. Combined with
the raw file never being overwritten, you can always answer "where did
this Gold row come from, and if it's missing, why" — which is the whole
point of a Bronze/Silver/Gold architecture as opposed to just cleaning a
CSV in place.

## 34. Scalability considerations

Nexus V1 targets a single 25 MB file processed by a single-machine
`local[*]` Spark session — appropriate for the stated use case, not for
big data. The honest scaling path: (1) point `SPARK_MASTER` at a real
cluster instead of `local[*]` — the pipeline code doesn't change, only
the session config in `spark_session.py`; (2) the CSV-export helper
(`csv_export.py`) coalesces to one partition before writing, which is
fine at 25 MB and wrong at scale — it would need to write multi-part
output instead; (3) the synchronous-request "queue and background-task"
processing model would need a real message queue (Celery/RabbitMQ or
similar) once processing time exceeds what a single background thread
per request comfortably handles.

## 35. Limitations

No authentication or multi-tenant user isolation (explicitly out of
scope per spec section 29 — anyone with network access to the backend
can see every dataset). No slowly-changing-dimension handling —
re-uploading a "new version" of the same business entity creates
independent surrogate keys scoped to that dataset's `_dataset_id`, not a
merged dimension history. No forecasting or ML-based insights — only
descriptive, already-computed metrics. XLSX is explicitly not supported
in V1 (spec section 3). Large files beyond 25 MB are rejected outright
rather than chunked. The frontend's SVG charts are hand-rolled (no
charting library) and cover the metrics spec section 25 lists, not every
metric Nexus computes.

## 36. Future improvements

Authentication + per-user dataset isolation; XLSX support; a real
message queue for large-file processing; slowly-changing dimensions for
re-uploaded datasets; a forecasting module (explicitly absent today, not
half-implemented); richer chart types (stacked/segmented) once a
charting approach beyond hand-rolled SVG is justified; configurable
business-rule thresholds (currently `quantity > 0`, discount `0–1`, etc.
are constants, not per-tenant settings).
