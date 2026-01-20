"""Rename Router to Firewall

Revision ID: 003_rename_router
Revises: 002_add_types
Create Date: 2025-01-20

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '003_rename_router'
down_revision: Union[str, None] = '002_add_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Firewall enum value
    op.execute("ALTER TYPE itemtype ADD VALUE IF NOT EXISTS 'Firewall'")
    # Note: Can't update Router->Firewall in same transaction as ADD VALUE
    # This will be handled by a second migration or manually


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly
    pass
