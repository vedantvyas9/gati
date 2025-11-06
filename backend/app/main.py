"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.database.connection import init_async_db, close_async_db
from app.api import health, events, agents, runs, metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting GATI Backend...")
    await init_async_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down GATI Backend...")
    await close_async_db()
    logger.info("Database closed")


# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="GATI Backend API for event ingestion and agent tracking",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    """Log incoming requests."""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(events.router, prefix=settings.api_prefix, tags=["Events"])
app.include_router(agents.router, prefix=settings.api_prefix, tags=["Agents"])
app.include_router(runs.router, prefix=settings.api_prefix, tags=["Runs"])
app.include_router(metrics.router, prefix=settings.api_prefix, tags=["Metrics"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
