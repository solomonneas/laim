"""
LAIM - Lab Asset Inventory Manager
SQLAlchemy Database Models
"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum as SQLEnum,
    Boolean,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
class ItemType(enum.Enum):
    """Hardware category enumeration."""
    LAPTOP = "Laptop"
    DESKTOP = "Desktop"
    SMART_TV = "Smart TV"
    SERVER = "Server"
    WAP = "WAP"  # Wireless Access Point
    ROUTER = "Router"
    SWITCH = "Switch"


class UserRole(enum.Enum):
    """User role enumeration for RBAC."""
    SUPERUSER = "superuser"
    ADMIN = "admin"


class SyncStatus(enum.Enum):
    """Sync job status enumeration."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# -----------------------------------------------------------------------------
# User Model
# -----------------------------------------------------------------------------
class User(Base):
    """User model for authentication and RBAC."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.ADMIN)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_items = relationship(
        "InventoryItem",
        back_populates="created_by_user",
        foreign_keys="InventoryItem.created_by"
    )
    updated_items = relationship(
        "InventoryItem",
        back_populates="updated_by_user",
        foreign_keys="InventoryItem.updated_by"
    )

    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role.value}')>"


# -----------------------------------------------------------------------------
# Inventory Item Model
# -----------------------------------------------------------------------------
class InventoryItem(Base):
    """Main inventory item model."""
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)

    # Core identification fields
    hostname = Column(String(255), nullable=False, index=True)
    serial_number = Column(String(100), unique=True, nullable=False, index=True)
    mac_address = Column(String(17), unique=True, nullable=True, index=True)  # Format: XX:XX:XX:XX:XX:XX
    asset_tag = Column(String(100), unique=True, nullable=False, index=True)

    # Classification fields
    item_type = Column(SQLEnum(ItemType), nullable=False, index=True)
    room_location = Column(String(100), nullable=False, index=True)  # Free-form room/location
    sub_location = Column(String(100), nullable=True)  # e.g., "Rack 1", "Shelf B", "Desk 3"

    # Metadata
    notes = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Audit fields
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Sync/source tracking fields
    source = Column(String(50), nullable=True)  # 'manual', 'netdisco', 'librenms', 'merged'
    source_id = Column(String(255), nullable=True)  # External system ID
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    firmware_version = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    model = Column(String(255), nullable=True)
    vendor = Column(String(255), nullable=True)

    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="created_items",
        foreign_keys=[created_by]
    )
    updated_by_user = relationship(
        "User",
        back_populates="updated_items",
        foreign_keys=[updated_by]
    )

    # Indexes for search optimization
    __table_args__ = (
        Index("ix_inventory_search", "hostname", "serial_number", "asset_tag"),
        Index("ix_inventory_location", "room_location", "sub_location"),
    )

    def __repr__(self):
        return f"<InventoryItem(hostname='{self.hostname}', type='{self.item_type.value}')>"

    def to_dict(self):
        """Convert model to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "hostname": self.hostname,
            "serial_number": self.serial_number,
            "mac_address": self.mac_address,
            "asset_tag": self.asset_tag,
            "item_type": self.item_type.value,
            "room_location": self.room_location,
            "sub_location": self.sub_location,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "source": self.source,
            "source_id": self.source_id,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "firmware_version": self.firmware_version,
            "ip_address": self.ip_address,
            "model": self.model,
            "vendor": self.vendor,
        }


# -----------------------------------------------------------------------------
# Sync Log Model
# -----------------------------------------------------------------------------
class SyncLog(Base):
    """Sync job history model for tracking API sync operations."""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String(50), nullable=False)  # 'netdisco', 'librenms', 'all'
    status = Column(SQLEnum(SyncStatus), nullable=False, default=SyncStatus.RUNNING)
    devices_found = Column(Integer, default=0)
    created = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    errors = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<SyncLog(id={self.id}, source='{self.source}', status='{self.status.value}')>"

    def to_dict(self):
        """Convert model to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "source": self.source,
            "status": self.status.value,
            "devices_found": self.devices_found,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
        }
