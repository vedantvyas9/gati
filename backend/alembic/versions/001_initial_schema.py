"""Create initial schema with agents, runs, and events tables.

Revision ID: 001
Revises:
Create Date: 2024-11-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial tables."""
    # Create agents table
    op.create_table(
        "agents",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("name"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_agent_name", "agents", ["name"])
    op.create_index("idx_agent_created_at", "agents", ["created_at"])

    # Create runs table
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(50), nullable=True, server_default="development"),
        sa.Column("total_duration_ms", sa.Float(), nullable=True),
        sa.Column("total_cost", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("tokens_in", sa.Float(), nullable=True, server_default="0"),
        sa.Column("tokens_out", sa.Float(), nullable=True, server_default="0"),
        sa.Column("status", sa.String(20), nullable=True, server_default="active"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_name"],
            ["agents.name"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("idx_run_id", "runs", ["run_id"])
    op.create_index("idx_run_agent_name", "runs", ["agent_name"])
    op.create_index("idx_run_created_at", "runs", ["created_at"])
    op.create_index("idx_run_agent_created", "runs", ["agent_name", "created_at"])
    op.create_index("idx_run_status", "runs", ["status"])

    # Create events table
    op.create_table(
        "events",
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.run_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("idx_event_id", "events", ["event_id"])
    op.create_index("idx_event_run_id", "events", ["run_id"])
    op.create_index("idx_event_agent_name", "events", ["agent_name"])
    op.create_index("idx_event_type", "events", ["event_type"])
    op.create_index("idx_event_timestamp", "events", ["timestamp"])
    op.create_index("idx_event_run_timestamp", "events", ["run_id", "timestamp"])
    op.create_index("idx_event_agent_timestamp", "events", ["agent_name", "timestamp"])
    op.create_index("idx_event_type_timestamp", "events", ["event_type", "timestamp"])
    op.create_index(
        "idx_event_agent_time_range",
        "events",
        ["agent_name", sa.desc("timestamp")],
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("events")
    op.drop_table("runs")
    op.drop_table("agents")
