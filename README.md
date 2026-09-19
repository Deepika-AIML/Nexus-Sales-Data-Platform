# Nexus — Sales Data Modernization & Analytics Platform

> An end-to-end data modernization and analytics platform that transforms raw sales data into clean, validated, analytics-ready datasets and presents business insights through an interactive dashboard.

## Overview

**Nexus** addresses the problem of inconsistent and difficult-to-analyze raw sales data by providing a structured workflow:

**Raw Data → Profiling → Column Mapping → Data Quality → Processing → Analytics → Insights**

The platform allows users to upload sales data, understand its structure, map source columns to a canonical schema, validate data quality, process the dataset through layered data processing, store analytics-ready data in MySQL, and explore business KPIs and insights through a web dashboard.

---

## Key Features

* 📂 **Sales Data Upload** — Upload and process raw sales datasets.
* 🔍 **Data Profiling** — Analyze dataset structure, columns, data types, and missing values.
* 🗺️ **Column Mapping** — Map different source column names to a canonical schema.
* ✅ **Data Quality** — Identify duplicates, missing/invalid data, and other quality issues.
* 🏗️ **Bronze → Silver → Gold** — Structured data-processing pipeline.
* 🗄️ **MySQL Storage** — Store processed, analytics-ready data.
* 📊 **Interactive Analytics** — Explore sales trends, categories, regions, segments, products, and customers.
* 💡 **Insights & Recommendations** — Surface important trends and business opportunities.
* 🔌 **REST APIs** — FastAPI endpoints connect the frontend with the processing and analytics layers.
* 🐳 **Dockerized** — Frontend, backend, and database run as containerized services.

---

## Data Flow

```text
Raw Sales Dataset
       ↓
   Profiling
       ↓
 Column Mapping
       ↓
 Data Quality
       ↓
   Processing
       ↓
Bronze → Silver → Gold
       ↓
     MySQL
       ↓
   FastAPI APIs
       ↓
Interactive Dashboard
       ↓
Insights & Recommendations
```

---

## Architecture

```text
┌─────────────────────┐
│      Frontend       │
│ HTML/CSS/JavaScript │
│      Nginx          │
└──────────┬──────────┘
           │ REST API
           ▼
┌─────────────────────┐
│       FastAPI       │
│       Backend       │
└──────┬────────┬─────┘
       │        │
       ▼        ▼
┌──────────┐ ┌──────────┐
│ PySpark  │ │  MySQL   │
│ Pipeline │ │ Database │
└──────────┘ └──────────┘
```

---

## Tech Stack

| Technology             | Purpose                                   |
| ---------------------- | ----------------------------------------- |
| **Python**             | Backend and processing logic              |
| **FastAPI**            | REST API layer                            |
| **PySpark**            | Data processing and transformation        |
| **MySQL**              | Relational data storage and analytics     |
| **HTML/CSS**           | Frontend structure and styling            |
| **Vanilla JavaScript** | Frontend logic and API communication      |
| **Chart.js**           | Interactive data visualization            |
| **Nginx**              | Frontend web server                       |
| **Docker**             | Containerization                          |
| **Docker Compose**     | Multi-service orchestration               |
| **Git/GitHub**         | Version control and repository management |

---

## Project Structure

```text
nexus/
│
├── backend/
│   ├── app/
│   ├── tests/
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   └── requirements.txt
│
├── frontend/
│   ├── assets/
│   ├── css/
│   ├── js/
│   ├── analytics.html
│   ├── insights.html
│   ├── mapping.html
│   ├── processing.html
│   ├── quality.html
│   ├── upload.html
│   ├── Dockerfile
│   └── nginx.conf
│
├── database/
│   └── init.sql
│
├── data/
│   ├── raw/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   ├── rejected/
│   └── outputs/
│
├── docs/
├── scripts/
├── tests/
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## Running Locally

### Prerequisites

* Git
* Docker Desktop

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/nexus-sales-data-platform.git
cd nexus-sales-data-platform
```

### 2. Configure environment variables

Create `.env` from `.env.example`:

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

Update the required values in `.env`.

> Do not commit `.env` or any credentials to GitHub.

### 3. Start the application

```bash
docker compose up --build
```

For background mode:

```bash
docker compose up --build -d
```

### 4. Check services

```bash
docker compose ps
```

### 5. Open the application

**Frontend:**

```text
http://localhost:8080
```

**Backend:**

```text
http://localhost:8000
```

**Health Check:**

```text
http://localhost:8000/api/health
```

---

## Docker Services

Nexus runs as three main services:

```text
Frontend  →  localhost:8080
Backend   →  localhost:8000
MySQL     →  database service
```

The backend communicates with MySQL through the Docker Compose network using the MySQL service name.

---

## API Endpoints

| Endpoint                            | Method | Purpose                      |
| ----------------------------------- | ------ | ---------------------------- |
| `/api/health`                       | GET    | Health check                 |
| `/api/upload`                       | POST   | Upload dataset               |
| `/api/profile/{dataset_id}`         | GET    | Dataset profiling            |
| `/api/mapping/{dataset_id}`         | POST   | Generate mapping suggestions |
| `/api/mapping/{dataset_id}`         | GET    | Retrieve mapping             |
| `/api/mapping/{dataset_id}/confirm` | POST   | Confirm mappings             |
| `/api/quality/{dataset_id}`         | GET    | Data-quality information     |
| `/api/process/{dataset_id}`         | POST   | Process dataset              |
| `/api/results/{dataset_id}`         | GET    | Processing results           |
| `/api/analytics/{dataset_id}`       | GET    | Analytics data               |
| `/api/insights/{dataset_id}`        | GET    | Business insights            |
| `/api/history`                      | GET    | Processing history           |
| `/api/download/{dataset_id}/{kind}` | GET    | Download generated output    |

---

## Analytics

The dashboard provides interactive visualizations for:

* Sales trends
* Category performance
* Regional performance
* Segment performance
* Discount and profit analysis
* Top products
* Top customers

Chart selection is based on the type of analysis:

* **Line charts** → trends over time
* **Bar charts** → category/region/segment comparisons
* **Horizontal bar charts** → ranked products and customers

Currency values are presented in **Indian Rupees (₹)**.

---

## Data Processing Layers

### Bronze

Stores the ingested/raw stage of the dataset.

### Silver

Contains cleaned and validated data.

### Gold

Contains analytics-ready data used by the analytics layer and database.

---

## Why Nexus?

Nexus demonstrates an end-to-end approach to turning raw operational data into usable business analytics.

Instead of manually preparing every dataset, the platform combines:

**Ingestion + Profiling + Mapping + Data Quality + Transformation + Storage + Analytics + Insights**

into one workflow.

---

## Future Enhancements

* Excel and additional data-source support
* Incremental data processing
* Background processing for large datasets
* Advanced analytics and forecasting
* Cloud deployment
* CI/CD automation
* Authentication and role-based access
* Production monitoring and logging

---

## Author

**Deepika Sharma**

B.Tech — Computer Science & Engineering (AI & ML)

**Areas of Interest:** Python • Data Engineering • Backend Development • Data Analytics

---
