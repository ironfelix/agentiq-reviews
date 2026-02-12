"""Main FastAPI application - AgentIQ Chat Center MVP"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import get_settings
from app.database import engine, Base
from app.api import sellers, chats, messages, auth, interactions
from app import models  # noqa: F401

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

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
    allow_origins=["*"],  # Dev: allow all origins for LAN access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting AgentIQ Chat Center API...")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[-1]}")  # Hide credentials in logs

    # Create tables (for development - use Alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down AgentIQ Chat Center API...")
    await engine.dispose()


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "agentiq-chat-center",
        "version": "0.1.0"
    }

@app.get("/api/health")
async def health_check_api():
    """Health check endpoint (API namespace, for reverse proxies)."""
    return await health_check()


# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(sellers.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(interactions.router, prefix="/api")


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
