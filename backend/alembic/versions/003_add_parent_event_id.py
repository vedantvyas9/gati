"""Add parent_event_id column to events table

Revision ID: 003
Revises: 002
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """Add parent_event_id column to events table for hierarchical event relationships."""

    # Add parent_event_id column (nullable to support events without parents)
    op.add_column('events', sa.Column('parent_event_id', sa.String(36), nullable=True))

    # Create index on parent_event_id for efficient querying of event hierarchies
    op.create_index('idx_event_parent_id', 'events', ['parent_event_id'])


def downgrade():
    """Remove parent_event_id column from events table."""

    # Drop index
    op.drop_index('idx_event_parent_id', table_name='events')

    # Drop column
    op.drop_column('events', 'parent_event_id')
