# Nexus — Sales Data Modernization & Analytics Platform

Nexus turns a raw sales CSV into reliable business intelligence. Upload a
file and Nexus profiles it, maps its columns onto a canonical sales
schema, reports data-quality issues, cleans and standardizes the data
through a real **PySpark Bronze → Silver → Gold pipeline**, loads an
analytics-ready star schema into **MySQL**, and generates metrics,
insights, and recommendations — all through a **FastAPI** backend and a
plain **HTML/CSS/vanilla JavaScript** frontend.

---

## 1. What Nexus is

Nexus is a single-instance, local-first data platform for one recurring
job: take a sales CSV that doesn't necessarily match any fixed schema, and
turn it into governed, analytics-ready data plus data-backed insights —
without ever fabricating a value it wasn't given.

## 2. Features

- **Smart column mapping** — multi-signal confidence scoring (synonym
  dictionary, fuzzy name matching, keyword overlap, datatype fit, value
  patterns), not exact string matching.
- **Data profiling & quality scoring** — completeness, uniqueness,
  validity, consistency, and schema-match, each contributing to an overall
  score that is *severity-weighted*, not just a row-fraction average.
- **Real PySpark pipeline** — Bronze (raw ingestion) → Silver (cleaning,
  standardization, validation) → Gold (star-schema analytics model),
  implemented as actual Spark DataFrame transformations, not pandas
  dressed up.
- **MySQL-backed Gold layer** — a `fact_sales` table plus `dim_date`,
  `dim_product`, `dim_customer`, `dim_location` — built only for
  dimensions the dataset actually supports.
- **Dynamic analytics & insights** — every KPI and chart checks whether
  its underlying fields were actually mapped; unavailable metrics say so
  explicitly instead of showing fabricated zeros.
- **Full data lineage** — Raw → Bronze → Silver (clean + rejected, with
  reasons) → Gold, with nothing silently dropped or overwritten.
- **Downloads** — cleaned dataset, rejected records, column-mapping
  report, data-quality report.
- **Processing history** — every upload tracked with its quality score
  and status.

## 3. Architecture

```
                     ┌─────────────────────────┐
   Browser  ───────▶ │  Frontend (nginx, :8080) │  HTML / CSS / vanilla JS
                     └────────────┬─────────────┘
                                  │ fetch() → REST/JSON
                                  ▼
                     ┌─────────────────────────┐
                     │  Backend (FastAPI, :8000)│  API orchestration only
                     └────────────┬─────────────┘
                     services/  →  data_engine/  →  analytics/ · insights/
                                  │
                        ┌─────────┴─────────┐
                        ▼                   ▼
              PySpark pipeline        SQLAlchemy (metadata)
           Bronze → Silver → Gold            │
                        │                    ▼
                        └──────────▶  MySQL (:3306)
                       (JDBC write)   app metadata + gold_* tables
```

See `docs/TECHNICAL_LEARNING_GUIDE.md` for a full component-by-component
walkthrough.

## 4. Tech stack

| Layer            | Technology                                             |
|-------------------|--------------------------------------------------------|
| Frontend           | HTML, CSS, vanilla JavaScript (no framework)            |
| Backend             | FastAPI, Pydantic, SQLAlchemy                             |
| Data engineering     | PySpark, pandas, Python                                     |
| Database              | MySQL 8                                                       |
| Containerization        | Docker, Docker Compose                                          |
| Testing                   | pytest                                                              |

## 5. Folder structure

```
nexus/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app assembly, CORS, error handlers
│   │   ├── api/                # Routers — one file per resource
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── models/                # SQLAlchemy ORM models
│   │   ├── services/               # Orchestration layer (routers call these)
│   │   ├── core/                    # Config, logging, exceptions
│   │   ├── database/                 # SQLAlchemy engine/session
│   │   ├── data_engine/                # Mapping / quality / cleaning engines
│   │   │   └── spark/                    # PySpark Bronze/Silver/Gold pipeline
│   │   ├── analytics/                     # SQL analytics over the Gold layer
│   │   └── insights/                       # Insight + recommendation engines
│   ├── tests/                                # pytest suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                                    # Static HTML/CSS/JS, served by nginx
├── data/                                          # raw / bronze / silver / gold / rejected / outputs
├── database/init.sql                                # MySQL schema (app metadata + Gold tables)
├── docs/                                              # Technical guide + interview prep
├── scripts/                                            # Test-data & performance-data generators
├── docker-compose.yml
└── .env.example
```

## 6. Prerequisites

- Docker and Docker Compose (Docker Desktop, or Docker Engine + Compose
  plugin on Linux)
- ~4 GB of free RAM available to Docker (PySpark's local-mode driver needs
  headroom)
- No local Python, Java, MySQL, or Node install is required — everything
  runs inside containers

## 7. Docker installation

Install Docker Desktop (macOS/Windows) or Docker Engine + the Compose
plugin (Linux), then verify:

```bash
docker --version
docker compose version
```

## 8. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` and set real values for `MYSQL_ROOT_PASSWORD` and
`MYSQL_PASSWORD` — the placeholders (`change_me_...`) are intentionally
not usable as-is. See `.env.example` for what every variable does.

## 9. Where to place the Superstore CSV

The reference dataset is already included at `data/raw/Sample_-_Superstore.csv`
— you don't need to place anything manually to try Nexus with it. To
process it, upload that exact file through the Upload page once Nexus is
running (the app doesn't auto-ingest files sitting in `data/raw/`; upload
is always an explicit user action, per the product's file-handling design).

To test with a different sales CSV, just upload it — Nexus does not
require any particular filename or location.

## 10. How to start Nexus

```bash
docker compose up --build
```

First build downloads the MySQL JDBC driver and installs PySpark, so the
initial build takes a few minutes. Subsequent runs are fast.

## 11. How to stop Nexus

```bash
docker compose down
```

Add `-v` to also remove the MySQL data volume (full reset):

```bash
docker compose down -v
```

## 12. How to rebuild Nexus

After changing backend or frontend code:

```bash
docker compose up --build
```

To rebuild a single service:

```bash
docker compose build backend
docker compose up -d backend
```

## 13. How to run tests

```bash
docker compose run --rm backend pytest -v
```

(Runs inside the backend container, where `pytest`, `fastapi`, and
`pyspark` are actually installed — see `docs/TECHNICAL_LEARNING_GUIDE.md`
→ "Testing Strategy" for exactly what each test file covers and how it
was validated during development.)

For the parts of the stack that only a live Docker environment can
actually exercise — real PySpark running against real MySQL over
JDBC — walk through `tests/INTEGRATION_CHECKLIST.md` once after your
first `docker compose up --build`.

## 14. How to access the frontend

**http://localhost:8080**

## 15. How to access FastAPI documentation

**http://localhost:8000/docs** (Swagger UI) or **http://localhost:8000/redoc**

## 16. How to initialize MySQL

Nothing manual is required — `database/init.sql` is mounted into the
MySQL container's `/docker-entrypoint-initdb.d/` and runs automatically
the first time the container starts against an empty data volume. If you
ever need to re-run it by hand against a running container:

```bash
docker compose exec -T mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" < database/init.sql
```

## 17. How data flows through Bronze/Silver/Gold

1. **Bronze** — the confirmed-uploaded CSV is read into Spark as-is (every
   column as a string) and written to `data/bronze/<dataset_id>/` as
   parquet. Nothing is dropped, altered, or typed yet.
2. **Silver** — the user-confirmed column mapping is applied (rename +
   select), values are cast to their canonical types, categorical casing
   is normalized, dates are parsed, and business rules split the result
   into `silver/<id>/clean` and `silver/<id>/rejected` (with reasons).
3. **Gold** — `silver/clean` is modeled into a star schema
   (`fact_sales` + whichever dimension tables the mapped fields support)
   and written both to `data/gold/<id>/` (parquet) and to MySQL via JDBC.

## 18. How column mapping works

See `docs/TECHNICAL_LEARNING_GUIDE.md` → "Column Mapping" for the full
algorithm. In short: every source column is scored against every
canonical field using five weighted signals (name equality/synonyms,
fuzzy name similarity, keyword overlap, datatype fit, value-pattern
strength); ≥85 auto-maps, 60–84 is flagged for review, <60 stays
unmapped.

## 19. How cleaning works

Trimming, categorical-casing normalization (to the most frequent form —
never merging genuinely different values), numeric coercion, and
multi-format date parsing happen first; then business rules (missing core
field, negative sales, non-positive quantity, ship-before-order, exact
duplicates) determine CLEAN vs. REJECTED. Optional fields that are simply
absent are never filled in — they stay null, and downstream analytics
report them as unavailable rather than guessing.

## 20. How outputs are generated

`POST /api/process/{dataset_id}` runs the full pipeline and writes:
`data/outputs/<id>__clean.csv`, `data/rejected/<id>__rejected.csv`, plus
on-demand mapping/quality report CSVs — all served through
`/api/download/{dataset_id}/...`.

## 21. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `docker compose up` fails pulling the MySQL JDBC jar | The **build host** needs network access to `repo1.maven.org` (this is unrelated to any environment the project may have been generated in). |
| Backend container keeps restarting | Check `docker compose logs backend` — usually a MySQL not-yet-ready race; the backend's `depends_on: condition: service_healthy` should prevent this, but a very slow first boot can still need a retry. |
| Frontend can't reach the backend (CORS errors) | Confirm you're opening `http://localhost:8080` (not a LAN IP) or add your actual origin to `CORS_ORIGINS` in `.env` and restart the backend. |
| "Required field 'sales' could not be identified" | Expected behavior — map a source column to `sales` manually on the Data Mapping page, or upload a dataset that has a sales/revenue-equivalent column. |
| Processing stuck at "queued" | Check `docker compose logs backend` for a Spark/JDBC error; confirm the `mysql` service is healthy (`docker compose ps`). |

## 22. Git / GitHub instructions

```bash
git init
git add .
git commit -m "Initial commit: Nexus sales data platform"
git branch -M main
git remote add origin https://github.com/<your-username>/nexus-sales-data-platform.git
git push -u origin main
```

Recommended repository name: **nexus-sales-data-platform**. A
`.gitignore` is already included — it excludes `.env`, Python caches,
and regenerated pipeline output directories.

## 23. Future improvements

See `docs/TECHNICAL_LEARNING_GUIDE.md` → "Limitations" and "Future
Improvements" for the full, honest list (authentication/multi-tenancy,
slowly-changing dimensions across re-uploads, async job queue for very
large files, forecasting, XLSX support, and more).

---

**Full technical walkthrough:** `docs/TECHNICAL_LEARNING_GUIDE.md`
**Interview prep:** `docs/INTERVIEW_PREPARATION.md`
