"""add stored_chunks and version_chunks tables

Revision ID: e5a1b2c34d78
Revises: d4f9a8e23c67
Create Date: 2026-05-23 08:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5a1b2c34d78'
down_revision = 'd4f9a8e23c67'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### Phase 1: Chunk-Level Delta Synchronization Tables ###

    op.create_table(
        'stored_chunks',
        sa.Column('chunk_hash', sa.String(64), primary_key=True, index=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('storage_path', sa.String(500), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'version_chunks',
        sa.Column('id', sa.BigInteger(), primary_key=True, index=True, autoincrement=True),
        sa.Column('version_id', sa.BigInteger(), sa.ForeignKey('versions.id'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_hash', sa.String(64), sa.ForeignKey('stored_chunks.chunk_hash'), nullable=False),
        sa.UniqueConstraint('version_id', 'chunk_index', name='unique_chunk_index_per_version'),
    )


def downgrade() -> None:
    op.drop_table('version_chunks')
    op.drop_table('stored_chunks')
