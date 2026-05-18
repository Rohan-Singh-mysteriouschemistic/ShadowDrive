"""Add chunk_uploads table (Week 5)

Revision ID: a7f2b5c91d04
Revises: 30da9aebda0c
Create Date: 2026-05-17 18:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f2b5c91d04'
down_revision: Union[str, Sequence[str], None] = '30da9aebda0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the chunk_uploads table for tracking chunked file transfers."""
    op.create_table('chunk_uploads',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('version_id', sa.BigInteger(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('total_chunks', sa.Integer(), nullable=False),
        sa.Column('chunk_storage_key', sa.String(length=500), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['version_id'], ['versions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_id', 'chunk_index', name='unique_chunk_per_version')
    )
    op.create_index(op.f('ix_chunk_uploads_id'), 'chunk_uploads', ['id'], unique=False)


def downgrade() -> None:
    """Remove the chunk_uploads table."""
    op.drop_index(op.f('ix_chunk_uploads_id'), table_name='chunk_uploads')
    op.drop_table('chunk_uploads')
