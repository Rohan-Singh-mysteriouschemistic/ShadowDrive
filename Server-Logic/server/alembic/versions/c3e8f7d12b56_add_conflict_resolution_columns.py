"""Add conflict resolution columns to versions (Week 7)

Revision ID: c3e8f7d12b56
Revises: a7f2b5c91d04
Create Date: 2026-05-20 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e8f7d12b56'
down_revision: Union[str, Sequence[str], None] = 'a7f2b5c91d04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add parent_version_id, is_conflict_copy, and announced_at to versions."""
    # Self-referential FK: which version was this edit based on?
    op.add_column('versions', sa.Column(
        'parent_version_id',
        sa.BigInteger(),
        sa.ForeignKey('versions.id'),
        nullable=True
    ))

    # Flag to mark conflict copies created by LWW resolution
    op.add_column('versions', sa.Column(
        'is_conflict_copy',
        sa.Boolean(),
        server_default=sa.text('false'),
        nullable=False
    ))

    # Client-reported edit timestamp for LWW tiebreaking
    op.add_column('versions', sa.Column(
        'announced_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))


def downgrade() -> None:
    """Remove Week 7 conflict resolution columns."""
    op.drop_column('versions', 'announced_at')
    op.drop_column('versions', 'is_conflict_copy')
    op.drop_column('versions', 'parent_version_id')
