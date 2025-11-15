"""Event database model for tracking agent operation events."""
from sqlalchemy import Column, String, Index, ForeignKey, DateTime, ForeignKeyConstraint, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base, BaseModel


class Event(BaseModel):
    """Event model for tracking individual events during agent execution."""

    __tablename__ = "events"

    event_id = Column(String(36), primary_key=True, index=True, nullable=False)
    """Unique event identifier (UUID)."""

    run_id = Column(String(36), ForeignKey('runs.run_id', ondelete='CASCADE'), nullable=False, index=True)
    """Run ID (UUID) associated with this event."""

    agent_name = Column(String(255), nullable=False, index=True)
    """Agent name that generated this event."""

    event_type = Column(String(50), nullable=False, index=True)
    """Type of event (e.g., 'llm_call', 'tool_call', 'agent_start', 'agent_end')."""

    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    """Event timestamp (ISO 8601 format)."""

    parent_event_id = Column(String(36), nullable=True, index=True)
    """Parent event ID for hierarchical event relationships."""

    previous_event_id = Column(String(36), nullable=True, index=True)
    """Previous event ID for sequential execution flow tracking."""

    data = Column(JSON, nullable=False)
    """Event data as JSON object containing event-specific information."""

    # Relationship
    run = relationship("Run", back_populates="events")
    """Reference to the run this event belongs to."""

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_event_id", "event_id"),
        Index("idx_event_run_id", "run_id"),
        Index("idx_event_agent_name", "agent_name"),
        Index("idx_event_type", "event_type"),
        Index("idx_event_timestamp", "timestamp"),
        # Composite indexes for common queries
        Index("idx_event_run_timestamp", "run_id", "timestamp"),
        Index("idx_event_agent_timestamp", "agent_name", "timestamp"),
        Index("idx_event_type_timestamp", "event_type", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Event(event_id='{self.event_id}', run_id='{self.run_id}', event_type='{self.event_type}')>"
