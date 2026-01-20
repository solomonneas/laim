"""Migrate Router data to Firewall

Revision ID: 004_migrate_router
Revises: 003_rename_router
Create Date: 2025-01-20

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '004_migrate_router'
down_revision: Union[str, None] = '003_rename_router'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update any items with Router type to Firewall
    op.execute("UPDATE inventory_items SET item_type = 'Firewall' WHERE item_type = 'Router'")


def downgrade() -> None:
    # Revert Firewall items back to Router
    op.execute("UPDATE inventory_items SET item_type = 'Router' WHERE item_type = 'Firewall'")
