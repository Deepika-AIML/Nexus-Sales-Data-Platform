"""
Shared pytest fixtures.

Two kinds of tests live in this suite:
  - Pure data-engine unit tests (test_mapping_engine.py, test_quality_engine.py,
    test_cleaning_engine.py, test_required_optional_fields.py) — these need
    only pandas and run anywhere, including outside Docker.
  - API-level tests (test_api_endpoints.py) — these need a FastAPI TestClient
    and a database. Rather than requiring a live MySQL instance for what
    should be fast unit tests, `db_session`/`client` override the app's
    `get_db` dependency with a SQLite-backed session. This exercises the
    full FastAPI + SQLAlchemy + service-layer contract without needing
    Docker running — genuine MySQL/PySpark/Docker integration is covered
    separately by the manual integration checklist in
    docs/TECHNICAL_LEARNING_GUIDE.md (Testing Strategy section), since that
    requires the full `docker compose up` stack to be meaningful.
"""
import os
import sys

import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SUPERSTORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "raw", "Sample_-_Superstore.csv",
)


@pytest.fixture(scope="session")
def superstore_df() -> pd.DataFrame:
    """The real reference dataset, read with the encoding Nexus actually needs (cp1252)."""
    return pd.read_csv(SUPERSTORE_PATH, encoding="cp1252")


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database.session import Base
    import app.models  # noqa: F401 — registers all models on Base.metadata

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database.session import get_db
    from app.core.config import get_settings

    # Route all filesystem writes (raw uploads, outputs) into a throwaway
    # temp directory instead of the real /data volume during tests.
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
