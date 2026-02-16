"""Main FastAPI application - AgentIQ Chat Center MVP"""

import logging
import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from starlette.responses import JSONResponse

from app.config import get_settings
from app.database import engine, Base
from app.api import sellers, chats, messages, auth, interactions, settings as settings_api, leads
from app import models  # noqa: F401

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize Sentry if DSN is provided
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        release="1.0.0",
        integrations=[
            FastApiIntegration(),
        ],
    )
    logging.info("Sentry initialized for environment: %s", settings.SENTRY_ENVIRONMENT)
else:
    logging.info("Sentry disabled (no DSN configured)")

# Prometheus metrics (kept minimal; avoid high-cardinality labels).
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Create FastAPI app
app = FastAPI(
    title="AgentIQ Chat Center API",
    description="Unified chat management for marketplace sellers (Ozon, WB, etc.)",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "https://agentiq.ru,http://localhost:5173,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all for unhandled exceptions — log + Sentry + clean 500."""
    import logging
    logger = logging.getLogger("agentiq")
    logger.exception("Unhandled exception: %s %s", request.method, request.url)
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Lifecycle events
@app.on_event("startup")
async def validate_secrets():
    from app.config import get_settings as _get_settings
    _settings = _get_settings()
    if _settings.SECRET_KEY in ("change-me-in-production", "test-secret-key"):
        import warnings
        warnings.warn("SECURITY WARNING: SECRET_KEY is using a default/weak value! Generate a secure key for production.", stacklevel=2)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting AgentIQ Chat Center API...")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[-1]}")  # Hide credentials in logs

    # Create tables (for development - use Alembic migrations in production)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.warning("create_all race condition (harmless if tables exist): %s", exc)

    logger.info("Database initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down AgentIQ Chat Center API...")
    await engine.dispose()

@app.middleware("http")
async def prometheus_http_middleware(request, call_next):
    """
    Record request metrics with low-cardinality path templates.
    """
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = getattr(response, "status_code", 500) or 500
        return response
    finally:
        try:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path) or request.url.path
            # Avoid scraping loops / noise.
            if path not in {"/api/metrics", "/metrics"}:
                elapsed = time.perf_counter() - start
                HTTP_REQUESTS_TOTAL.labels(
                    method=request.method,
                    path=path,
                    status_code=str(status_code),
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=request.method,
                    path=path,
                ).observe(elapsed)
        except Exception:
            # Never fail the request because of metrics.
            pass


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint — verifies DB connectivity."""
    from app.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "agentiq-chat-center", "version": "0.1.0"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "service": "agentiq-chat-center", "error": str(e)}
        )

@app.get("/api/health")
async def health_check_api():
    """Health check endpoint (API namespace, for reverse proxies)."""
    return await health_check()

@app.get("/api/metrics")
async def prometheus_metrics():
    """
    Prometheus scrape endpoint.

    Security: this is intended to be scraped locally (Prometheus runs on the same host).
    Do not expose publicly in nginx.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(sellers.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(interactions.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(leads.router, prefix="/api")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "AgentIQ Chat Center API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "sellers": "/api/sellers",
            "chats": "/api/chats",
            "messages": "/api/messages",
            "interactions": "/api/interactions",
            "leads": "/api/leads",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
