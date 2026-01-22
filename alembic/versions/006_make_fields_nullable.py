"""make_serial_number_asset_tag_room_nullable

Revision ID: 006_make_fields_nullable
Revises: 005_add_backup_settings
Create Date: 2026-01-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '006_make_fields_nullable'
down_revision: Union[str, Sequence[str], None] = '005_add_backup_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make serial_number, asset_tag, and room_location nullable."""
    op.alter_column('inventory_items', 'serial_number',
                    existing_type=sa.String(100),
                    nullable=True)
    op.alter_column('inventory_items', 'asset_tag',
                    existing_type=sa.String(100),
                    nullable=True)
    op.alter_column('inventory_items', 'room_location',
                    existing_type=sa.String(100),
                    nullable=True)


def downgrade() -> None:
    """Revert to non-nullable (will fail if NULL values exist)."""
    op.alter_column('inventory_items', 'serial_number',
                    existing_type=sa.String(100),
                    nullable=False)
    op.alter_column('inventory_items', 'asset_tag',
                    existing_type=sa.String(100),
                    nullable=False)
    op.alter_column('inventory_items', 'room_location',
                    existing_type=sa.String(100),
                    nullable=False)
