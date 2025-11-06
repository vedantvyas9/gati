"""Run database model for tracking agent execution runs."""
from sqlalchemy import Column, String, Text, Float, Index, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON

from app.models.base import Base, BaseModel


class Run(BaseModel):
    """Run model for tracking individual agent execution runs."""

    __tablename__ = "runs"

    run_id = Column(String(36), primary_key=True, nullable=False)
    """Unique run identifier (UUID)."""

    agent_name = Column(
        String(255),
        ForeignKey("agents.name", ondelete="CASCADE"),
        nullable=False,
    )
    """Agent name that executed this run."""

    run_name = Column(String(255), nullable=False)
    """Run name (e.g., 'run 1', 'run 2')."""

    environment = Column(String(50), nullable=True, default="development")
    """Environment where the run was executed."""

    total_duration_ms = Column(Float, nullable=True)
    """Total duration of the run in milliseconds."""

    total_cost = Column(Float, nullable=True, default=0.0)
    """Total cost of the run."""

    tokens_in = Column(Float, nullable=True, default=0)
    """Total input tokens used."""

    tokens_out = Column(Float, nullable=True, default=0)
    """Total output tokens used."""

    status = Column(String(20), nullable=True, default="active")
    """Status of the run (active, completed, failed)."""

    run_metadata = Column("metadata", JSON, nullable=True)
    """Flexible metadata JSON field for additional run information."""

    # Relationships
    agent = relationship("Agent", back_populates="runs")
    """Reference to the agent that executed this run."""

    events = relationship(
        "Event",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    """Events that occurred during this run."""

    # Indexes and constraints
    __table_args__ = (
        Index("idx_run_id", "run_id"),
        Index("idx_run_name", "run_name"),
        Index("idx_run_agent_name", "agent_name"),
        Index("idx_run_created_at", "created_at"),
        Index("idx_run_agent_created", "agent_name", "created_at"),
        Index("idx_run_status", "status"),
        UniqueConstraint("agent_name", "run_name", name="uq_agent_run_name"),
    )

    def __repr__(self) -> str:
        return f"<Run(run_id='{self.run_id}', run_name='{self.run_name}', agent_name='{self.agent_name}')>"
