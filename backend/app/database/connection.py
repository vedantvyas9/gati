"""Database connection and session management."""
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


# Synchronous engine for migrations and sync operations
_sync_engine = None
_sync_session_factory = None

# Asynchronous engine and session factory
_async_engine = None
_async_session_factory = None


def init_sync_db() -> None:
    """Initialize synchronous database engine and session factory."""
    global _sync_engine, _sync_session_factory

    settings = get_settings()

    # Convert async PostgreSQL URL to sync URL if needed
    db_url = settings.database_url
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    _sync_engine = create_engine(
        db_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
        echo=settings.debug,
    )

    _sync_session_factory = sessionmaker(
        bind=_sync_engine,
        class_=Session,
        expire_on_commit=False,
    )


async def init_async_db() -> None:
    """Initialize asynchronous database engine and session factory."""
    global _async_engine, _async_session_factory

    settings = get_settings()

    db_url = settings.database_url
    if not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    _async_engine = create_async_engine(
        db_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
        echo=settings.debug,
    )

    _async_session_factory = async_sessionmaker(
        bind=_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def get_sync_session() -> Generator[Session, None, None]:
    """Get synchronous database session."""
    if _sync_session_factory is None:
        init_sync_db()

    session = _sync_session_factory()
    try:
        yield session
    finally:
        session.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session."""
    if _async_session_factory is None:
        await init_async_db()

    async with _async_session_factory() as session:
        yield session


def get_sync_engine():
    """Get synchronous database engine."""
    if _sync_engine is None:
        init_sync_db()
    return _sync_engine


async def get_async_engine():
    """Get asynchronous database engine."""
    if _async_engine is None:
        await init_async_db()
    return _async_engine


async def close_async_db() -> None:
    """Close asynchronous database engine."""
    global _async_engine
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None


def close_sync_db() -> None:
    """Close synchronous database engine."""
    global _sync_engine
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None
