"""Health check endpoint."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.connection import get_async_session
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_async_session)) -> HealthResponse:
    """
    Health check endpoint.

    Verifies that the API and database are operational.
    """
    try:
        settings = get_settings()
        # Test database connection with a simple query
        await session.execute(text("SELECT 1"))

        return HealthResponse(
            status="healthy",
            version=settings.app_version,
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            version=settings.app_version,
        )
