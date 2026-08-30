-- =============================================================================
-- Nexus MySQL initialization script
-- Mounted into the MySQL container's /docker-entrypoint-initdb.d/ so it runs
-- automatically the first time the `mysql` service starts with an empty
-- data volume. Safe to re-run manually (all statements are idempotent).
-- =============================================================================

CREATE DATABASE IF NOT EXISTS nexus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nexus;

-- -----------------------------------------------------------------------------
-- Application metadata (processing jobs / dataset registry / mappings)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id        VARCHAR(36)  PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename   VARCHAR(255) NOT NULL,
    file_size_bytes   BIGINT       NOT NULL,
    detected_encoding VARCHAR(32),
    row_count         INT,
    column_count      INT,
    status            ENUM('uploaded','profiled','mapping_review','mapped',
                            'quality_checked','processing','processed','failed')
                      NOT NULL DEFAULT 'uploaded',
    quality_score     DECIMAL(5,2),
    uploaded_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    error_message     TEXT NULL,
    INDEX idx_datasets_status (status),
    INDEX idx_datasets_uploaded_at (uploaded_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS column_mappings (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    dataset_id       VARCHAR(36) NOT NULL,
    source_column    VARCHAR(255) NOT NULL,
    canonical_field  VARCHAR(64) NULL,
    confidence       DECIMAL(5,2) NOT NULL DEFAULT 0,
    suggested_status ENUM('auto_mapped','review','unmapped') NOT NULL,
    final_status     ENUM('auto_mapped','review','unmapped','manual','confirmed','removed') NOT NULL,
    is_user_modified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    INDEX idx_mappings_dataset (dataset_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS quality_reports (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    dataset_id    VARCHAR(36) NOT NULL,
    score_overall DECIMAL(5,2) NOT NULL,
    completeness  DECIMAL(5,2) NOT NULL,
    uniqueness    DECIMAL(5,2) NOT NULL,
    validity      DECIMAL(5,2) NOT NULL,
    consistency   DECIMAL(5,2) NOT NULL,
    schema_match  DECIMAL(5,2) NOT NULL,
    generated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    INDEX idx_quality_dataset (dataset_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS quality_issues (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    dataset_id    VARCHAR(36) NOT NULL,
    code          VARCHAR(64) NOT NULL,
    field         VARCHAR(64) NULL,
    severity      ENUM('critical','warning','info') NOT NULL,
    affected_rows INT NOT NULL,
    description   TEXT NOT NULL,
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    INDEX idx_issues_dataset (dataset_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS processing_jobs (
    job_id           VARCHAR(36) PRIMARY KEY,
    dataset_id       VARCHAR(36) NOT NULL,
    status           ENUM('queued','uploading','profiling','mapping','validating',
                           'cleaning','transforming','building_analytics_model',
                           'generating_insights','completed','failed')
                     NOT NULL DEFAULT 'queued',
    started_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at     DATETIME NULL,
    duration_seconds DECIMAL(10,2) NULL,
    input_rows       INT NULL,
    clean_rows       INT NULL,
    rejected_rows    INT NULL,
    error_message    TEXT NULL,
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    INDEX idx_jobs_dataset (dataset_id)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- GOLD layer: star-schema analytics model.
-- Written to by the PySpark pipeline via JDBC (see
-- app/data_engine/spark/gold.py). Every table carries `_dataset_id` so a
-- single physical table can serve analytics for every processed dataset;
-- the FastAPI analytics layer always filters by `_dataset_id`.
-- Spark's JDBC writer can create tables automatically, but they are
-- predefined here with explicit types/indexes for query performance and so
-- the schema is documented in one obvious place.
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gold_dim_date (
    date_key    INT NOT NULL,
    full_date   DATE NOT NULL,
    year        INT,
    quarter     INT,
    month       INT,
    month_name  VARCHAR(16),
    day         INT,
    day_of_week INT,
    day_name    VARCHAR(16),
    is_weekend  BOOLEAN,
    _dataset_id VARCHAR(36) NOT NULL,
    INDEX idx_dim_date_dataset (_dataset_id),
    INDEX idx_dim_date_key (date_key, _dataset_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS gold_dim_product (
    product_key   BIGINT NOT NULL,
    product_id    VARCHAR(64),
    product_name  VARCHAR(500),
    category      VARCHAR(128),
    sub_category  VARCHAR(128),
    _dataset_id   VARCHAR(36) NOT NULL,
    INDEX idx_dim_product_dataset (_dataset_id),
    INDEX idx_dim_product_key (product_key, _dataset_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS gold_dim_customer (
    customer_key  BIGINT NOT NULL,
    customer_id   VARCHAR(64),
    customer_name VARCHAR(255),
    segment       VARCHAR(64),
    _dataset_id   VARCHAR(36) NOT NULL,
    INDEX idx_dim_customer_dataset (_dataset_id),
    INDEX idx_dim_customer_key (customer_key, _dataset_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS gold_dim_location (
    location_key BIGINT NOT NULL,
    country      VARCHAR(128),
    state        VARCHAR(128),
    city         VARCHAR(128),
    region       VARCHAR(64),
    postal_code  VARCHAR(20),
    _dataset_id  VARCHAR(36) NOT NULL,
    INDEX idx_dim_location_dataset (_dataset_id),
    INDEX idx_dim_location_key (location_key, _dataset_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS gold_fact_sales (
    order_id     VARCHAR(64),
    date_key     INT,
    product_key  BIGINT,
    customer_key BIGINT,
    location_key BIGINT,
    ship_mode    VARCHAR(64),
    ship_date    DATE,
    sales        DOUBLE,
    quantity     INT,
    discount     DOUBLE,
    profit       DOUBLE,
    _dataset_id  VARCHAR(36) NOT NULL,
    INDEX idx_fact_dataset (_dataset_id),
    INDEX idx_fact_date (date_key, _dataset_id),
    INDEX idx_fact_product (product_key, _dataset_id),
    INDEX idx_fact_customer (customer_key, _dataset_id),
    INDEX idx_fact_location (location_key, _dataset_id)
) ENGINE=InnoDB;
