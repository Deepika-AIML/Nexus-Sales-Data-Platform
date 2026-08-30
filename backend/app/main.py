"""
Nexus FastAPI application entrypoint.

Responsibilities kept deliberately narrow: assemble routers, configure
CORS, translate internal exceptions into clean user-facing JSON (never a
raw traceback — spec section 30), and ensure the local data directories +
DB schema exist on startup. All actual logic lives in `app/services`,
`app/data_engine`, `app/analytics`, and `app/insights`.
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import NexusError
from app.core.logging_config import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.APP_ENV)
logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="Upload a sales CSV and Nexus will profile, map, clean, transform, and analyze it "
                "through a Bronze/Silver/Gold PySpark pipeline before generating data-backed insights.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NexusError)
async def nexus_error_handler(request: Request, exc: NexusError):
    logger.warning("NexusError on %s %s: %s", request.method, request.url.path, exc.user_message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.user_message})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again or contact support."},
    )


@app.on_event("startup")
def on_startup():
    for d in (settings.RAW_DIR, settings.BRONZE_DIR, settings.SILVER_DIR,
              settings.GOLD_DIR, settings.REJECTED_DIR, settings.OUTPUTS_DIR):
        os.makedirs(d, exist_ok=True)

    # Defensive fallback: database/init.sql is the source of truth and runs
    # automatically on a fresh MySQL volume. create_all() additionally
    # ensures the app-metadata tables exist even if someone points Nexus at
    # a MySQL instance that skipped the init script — it is a no-op against
    # tables that already exist.
    try:
        from app.database.session import Base, engine
        import app.models  # noqa: F401 — registers all models on Base.metadata
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema verified.")
    except Exception as e:  # noqa: BLE001
        logger.error("Could not verify database schema at startup: %s", e)


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "nexus-backend"}


from app.api import (  # noqa: E402 — imported after `app` exists, per FastAPI convention
    upload, profile, mapping, quality, process, results, analytics, insights, history, download,
)

app.include_router(upload.router)
app.include_router(profile.router)
app.include_router(mapping.router)
app.include_router(quality.router)
app.include_router(process.router)
app.include_router(results.router)
app.include_router(analytics.router)
app.include_router(insights.router)
app.include_router(history.router)
app.include_router(download.router)
