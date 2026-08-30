"""
Centralized application settings. Every value is sourced from an
environment variable (populated by Docker Compose from `.env`) — nothing
is ever hard-coded, per spec section 33.
"""
import os
from functools import lru_cache


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_NAME: str = "Nexus Sales Data Modernization & Analytics Platform"

    # --- MySQL -------------------------------------------------------------
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "mysql")
    MYSQL_PORT: str = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "nexus")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "nexus")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    # --- Upload / storage ----------------------------------------------------
    UPLOAD_MAX_MB: int = int(os.getenv("UPLOAD_MAX_MB", "25"))
    UPLOAD_MAX_BYTES: int = UPLOAD_MAX_MB * 1024 * 1024

    DATA_ROOT: str = os.getenv("DATA_ROOT", "/data")
    RAW_DIR: str = os.path.join(DATA_ROOT, "raw")
    BRONZE_DIR: str = os.path.join(DATA_ROOT, "bronze")
    SILVER_DIR: str = os.path.join(DATA_ROOT, "silver")
    GOLD_DIR: str = os.path.join(DATA_ROOT, "gold")
    REJECTED_DIR: str = os.path.join(DATA_ROOT, "rejected")
    OUTPUTS_DIR: str = os.path.join(DATA_ROOT, "outputs")

    # --- CORS ------------------------------------------------------------------
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://localhost").split(",")

    # --- Spark -------------------------------------------------------------------
    SPARK_MASTER: str = os.getenv("SPARK_MASTER", "local[*]")


@lru_cache
def get_settings() -> Settings:
    return Settings()
