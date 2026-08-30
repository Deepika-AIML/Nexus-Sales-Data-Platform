"""
SQLAlchemy engine + session factory.

`get_db()` is a FastAPI dependency — routers declare `db: Session =
Depends(get_db)` and never construct sessions themselves, keeping
connection lifecycle management in exactly one place.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,   # survives MySQL closing idle connections
    pool_recycle=280,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
