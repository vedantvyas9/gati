"""Add run_name column to runs table

Revision ID: 002
Revises: 001
Create Date: 2025-01-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """Add run_name column with unique constraint."""

    # For SQLite, we need to use batch_alter_table to modify columns
    with op.batch_alter_table('runs') as batch_op:
        # Step 1: Add run_name column to runs table (nullable initially)
        batch_op.add_column(sa.Column('run_name', sa.String(255), nullable=True))

    # Step 2: Populate run_name for existing runs based on creation order per agent
    # SQLite-compatible version using a subquery instead of CTE with UPDATE FROM
    op.execute("""
        UPDATE runs
        SET run_name = (
            SELECT 'run ' || COUNT(*)
            FROM runs r2
            WHERE r2.agent_name = runs.agent_name
            AND r2.created_at <= runs.created_at
        )
        WHERE run_name IS NULL;
    """)

    # Step 3-5: Use batch_alter_table for SQLite compatibility
    with op.batch_alter_table('runs') as batch_op:
        # Make run_name NOT NULL
        batch_op.alter_column('run_name', nullable=False, existing_type=sa.String(255))

        # Add unique constraint on (agent_name, run_name)
        batch_op.create_unique_constraint('uq_agent_run_name', ['agent_name', 'run_name'])

        # Create index on run_name for faster lookups
        batch_op.create_index('idx_run_name', ['run_name'])


def downgrade():
    """Remove run_name column and related constraints."""

    # Drop index
    op.drop_index('idx_run_name', table_name='runs')

    # Drop unique constraint
    op.drop_constraint('uq_agent_run_name', 'runs', type_='unique')

    # Drop column
    op.drop_column('runs', 'run_name')
