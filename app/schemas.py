"""
LAIM - Lab Asset Inventory Manager
Pydantic Schemas for Request/Response Validation
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, field_validator
import re

from app.models import ItemType, UserRole, SyncStatus


# -----------------------------------------------------------------------------
# User Schemas
# -----------------------------------------------------------------------------
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole = UserRole.ADMIN


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Inventory Item Schemas
# -----------------------------------------------------------------------------
class InventoryItemBase(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    item_type: ItemType
    serial_number: Optional[str] = Field(None, max_length=100)
    mac_address: Optional[str] = Field(None, max_length=17)
    asset_tag: Optional[str] = Field(None, max_length=100)
    ip_address: Optional[str] = Field(None, max_length=45)
    room_location: Optional[str] = Field(None, max_length=100)
    sub_location: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        original = v.upper()
        # Remove all separators and spaces for validation
        stripped = original.replace("-", "").replace(":", "").replace(".", "").replace(" ", "")
        # Check if it's a valid 12-character hex string
        if len(stripped) == 12 and all(c in "0123456789ABCDEF" for c in stripped):
            # Format as XX:XX:XX:XX:XX:XX
            return ":".join(stripped[i:i+2] for i in range(0, 12, 2))
        # If not valid, return original input (don't block responses for bad data)
        return original


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    hostname: Optional[str] = Field(None, min_length=1, max_length=255)
    item_type: Optional[ItemType] = None
    serial_number: Optional[str] = Field(None, max_length=100)
    mac_address: Optional[str] = Field(None, max_length=17)
    asset_tag: Optional[str] = Field(None, max_length=100)
    ip_address: Optional[str] = Field(None, max_length=45)
    room_location: Optional[str] = Field(None, max_length=100)
    sub_location: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        original = v.upper()
        # Remove all separators and spaces for validation
        stripped = original.replace("-", "").replace(":", "").replace(".", "").replace(" ", "")
        # Check if it's a valid 12-character hex string
        if len(stripped) == 12 and all(c in "0123456789ABCDEF" for c in stripped):
            # Format as XX:XX:XX:XX:XX:XX
            return ":".join(stripped[i:i+2] for i in range(0, 12, 2))
        # If not valid, return original input (don't block for bad data)
        return original


class InventoryItemResponse(InventoryItemBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    model: Optional[str] = None
    vendor: Optional[str] = None

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Authentication Schemas
# -----------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -----------------------------------------------------------------------------
# Search/Filter Schemas
# -----------------------------------------------------------------------------
class SearchParams(BaseModel):
    query: Optional[str] = None
    item_type: Optional[ItemType] = None
    room_location: Optional[str] = None
    is_active: bool = True


# -----------------------------------------------------------------------------
# Statistics Schema
# -----------------------------------------------------------------------------
class DashboardStats(BaseModel):
    total_items: int
    by_type: dict[str, int]
    by_room: dict[str, int]
    recent_items: list[InventoryItemResponse]


# -----------------------------------------------------------------------------
# Sync Schemas
# -----------------------------------------------------------------------------
class SyncTriggerRequest(BaseModel):
    source: str = Field(default="all", pattern="^(all|netdisco|librenms)$")


class SyncTriggerResponse(BaseModel):
    sync_id: int
    message: str
    status: str


class SyncStatusResponse(BaseModel):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    source: str
    status: SyncStatus
    devices_found: int
    created: int
    updated: int
    skipped: int
    errors: Optional[list[str]] = None

    class Config:
        from_attributes = True


class SyncLogResponse(BaseModel):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    source: str
    status: SyncStatus
    devices_found: int
    created: int
    updated: int
    skipped: int

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Device Data Schema (for sync)
# -----------------------------------------------------------------------------
class DeviceData(BaseModel):
    """Unified device data schema for merging from multiple sources."""
    hostname: Optional[str] = None
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    model: Optional[str] = None
    vendor: Optional[str] = None
    firmware_version: Optional[str] = None
    location: Optional[str] = None
    source: str
    source_id: Optional[str] = None
