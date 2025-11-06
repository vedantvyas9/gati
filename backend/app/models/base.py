"""Base model with common fields for all database models."""
from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class BaseModel(Base):
    """Abstract base model with common audit fields."""

    __abstract__ = True

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
