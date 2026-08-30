# =============================================================================
# Nexus backend image: FastAPI + PySpark + Python data-engineering stack.
# PySpark needs a JVM, so this image installs a headless JRE alongside the
# Python dependencies.
# =============================================================================

FROM python:3.11-slim-bookworm

# --- System dependencies: JRE for PySpark, curl for JDBC driver download ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        curl \
        procps \
    && rm -rf /var/lib/apt/lists/*

# --- MySQL Connector/J: lets PySpark write Gold tables to MySQL via JDBC ---
RUN mkdir -p /opt/spark-jars && \
    curl -fsSL -o /opt/spark-jars/mysql-connector-j.jar \
        https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/8.4.0/mysql-connector-j-8.4.0.jar

ENV MYSQL_JDBC_JAR=/opt/spark-jars/mysql-connector-j.jar

# --- Python dependencies ---
WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Application code ---
COPY app ./app
COPY tests ./tests
COPY docker-entrypoint.sh .

RUN chmod +x docker-entrypoint.sh

# --- Python/runtime configuration ---
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYSPARK_PYTHON=python3

EXPOSE 8000

# --- Backend health check ---
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

# JAVA_HOME is configured by docker-entrypoint.sh at container startup.
ENTRYPOINT ["./docker-entrypoint.sh"]

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]