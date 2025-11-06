"""Agent database model."""
from sqlalchemy import Column, String, Index
from sqlalchemy.orm import relationship

from app.models.base import Base, BaseModel


class Agent(BaseModel):
    """Agent model for tracking agent instances."""

    __tablename__ = "agents"

    name = Column(String(255), primary_key=True, index=True, nullable=False)
    """Agent name (unique identifier)."""

    description = Column(String(1000), nullable=True)
    """Optional description of the agent."""

    # Relationships
    runs = relationship("Run", back_populates="agent", cascade="all, delete-orphan")
    """Runs executed by this agent."""

    # Indexes
    __table_args__ = (
        Index("idx_agent_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<Agent(name='{self.name}')>"
