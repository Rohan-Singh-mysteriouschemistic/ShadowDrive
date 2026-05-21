"""Add upload_status and job_id to versions (Week 8)

Revision ID: d4f9a8e23c67
Revises: c3e8f7d12b56
Create Date: 2026-05-21 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f9a8e23c67'
down_revision: Union[str, Sequence[str], None] = 'c3e8f7d12b56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The enum values that PostgreSQL needs to know about.
upload_status_enum = sa.Enum(
    'pending', 'uploading', 'processing', 'complete', 'failed',
    name='upload_status_enum'
)


def upgrade() -> None:
    """Add upload_status enum column and job_id to versions.

    1. Create the PostgreSQL enum type first.
    2. Add upload_status with a server_default of 'pending' so all
       existing rows are back-filled automatically — zero-downtime.
    3. Add job_id (nullable) for correlating versions to RQ jobs.
    """
    # Step 1: Create the enum type in PostgreSQL's pg_type catalog.
    upload_status_enum.create(op.get_bind(), checkfirst=True)

    # Step 2: Add upload_status column — existing rows get 'pending'.
    op.add_column('versions', sa.Column(
        'upload_status',
        upload_status_enum,
        server_default='pending',
        nullable=False
    ))

    # Step 3: Add job_id for RQ correlation.
    op.add_column('versions', sa.Column(
        'job_id',
        sa.String(64),
        nullable=True
    ))


def downgrade() -> None:
    """Remove Week 8 async tracking columns and enum type."""
    op.drop_column('versions', 'job_id')
    op.drop_column('versions', 'upload_status')

    # Drop the enum type from PostgreSQL.
    upload_status_enum.drop(op.get_bind(), checkfirst=True)
