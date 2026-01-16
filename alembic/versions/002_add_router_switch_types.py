"""Add Router and Switch item types

Revision ID: 002_add_types
Revises: 001_add_sync
Create Date: 2024-01-16

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '002_add_types'
down_revision: Union[str, None] = '001_add_sync'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values to itemtype enum
    # PostgreSQL requires ALTER TYPE to add new enum values
    op.execute("ALTER TYPE itemtype ADD VALUE IF NOT EXISTS 'Router'")
    op.execute("ALTER TYPE itemtype ADD VALUE IF NOT EXISTS 'Switch'")


def downgrade() -> None:
    # Note: PostgreSQL does not support removing enum values directly
    # To downgrade, you would need to:
    # 1. Create a new enum type without the values
    # 2. Update the column to use the new type
    # 3. Drop the old type
    # This is left as a manual operation if needed
    pass
