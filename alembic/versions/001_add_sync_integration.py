"""Add sync integration fields and SyncLog table

Revision ID: 001_add_sync
Revises:
Create Date: 2024-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_sync'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to inventory_items table
    op.add_column('inventory_items', sa.Column('source', sa.String(50), nullable=True))
    op.add_column('inventory_items', sa.Column('source_id', sa.String(255), nullable=True))
    op.add_column('inventory_items', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('inventory_items', sa.Column('firmware_version', sa.String(100), nullable=True))
    op.add_column('inventory_items', sa.Column('ip_address', sa.String(45), nullable=True))
    op.add_column('inventory_items', sa.Column('model', sa.String(255), nullable=True))
    op.add_column('inventory_items', sa.Column('vendor', sa.String(255), nullable=True))

    # Create sync_status enum type
    sync_status_enum = sa.Enum('RUNNING', 'COMPLETED', 'FAILED', name='syncstatus')
    sync_status_enum.create(op.get_bind(), checkfirst=True)

    # Create sync_logs table
    op.create_table(
        'sync_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('status', sync_status_enum, nullable=False),
        sa.Column('devices_found', sa.Integer(), server_default='0'),
        sa.Column('created', sa.Integer(), server_default='0'),
        sa.Column('updated', sa.Integer(), server_default='0'),
        sa.Column('skipped', sa.Integer(), server_default='0'),
        sa.Column('errors', sa.JSON(), nullable=True),
    )
    op.create_index('ix_sync_logs_id', 'sync_logs', ['id'])


def downgrade() -> None:
    # Drop sync_logs table
    op.drop_index('ix_sync_logs_id', table_name='sync_logs')
    op.drop_table('sync_logs')

    # Drop sync_status enum
    sa.Enum(name='syncstatus').drop(op.get_bind(), checkfirst=True)

    # Remove columns from inventory_items
    op.drop_column('inventory_items', 'vendor')
    op.drop_column('inventory_items', 'model')
    op.drop_column('inventory_items', 'ip_address')
    op.drop_column('inventory_items', 'firmware_version')
    op.drop_column('inventory_items', 'last_synced_at')
    op.drop_column('inventory_items', 'source_id')
    op.drop_column('inventory_items', 'source')
