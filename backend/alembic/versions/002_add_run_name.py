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

    # Step 1: Add run_name column to runs table (nullable initially)
    op.add_column('runs', sa.Column('run_name', sa.String(255), nullable=True))

    # Step 2: Populate run_name for existing runs based on creation order per agent
    op.execute("""
        WITH numbered_runs AS (
            SELECT
                run_id,
                agent_name,
                ROW_NUMBER() OVER (PARTITION BY agent_name ORDER BY created_at) as run_number
            FROM runs
        )
        UPDATE runs
        SET run_name = 'run ' || numbered_runs.run_number
        FROM numbered_runs
        WHERE runs.run_id = numbered_runs.run_id;
    """)

    # Step 3: Make run_name NOT NULL after populating data
    op.alter_column('runs', 'run_name', nullable=False)

    # Step 4: Add unique constraint on (agent_name, run_name)
    op.create_unique_constraint('uq_agent_run_name', 'runs', ['agent_name', 'run_name'])

    # Step 5: Create index on run_name for faster lookups
    op.create_index('idx_run_name', 'runs', ['run_name'])


def downgrade():
    """Remove run_name column and related constraints."""

    # Drop index
    op.drop_index('idx_run_name', table_name='runs')

    # Drop unique constraint
    op.drop_constraint('uq_agent_run_name', 'runs', type_='unique')

    # Drop column
    op.drop_column('runs', 'run_name')
