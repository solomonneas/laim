"""
LAIM - Lab Asset Inventory Manager
Pydantic Schemas for Request/Response Validation
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, field_validator
import re

from app.models import ItemType, RoomLocation, UserRole


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
    serial_number: str = Field(..., min_length=1, max_length=100)
    mac_address: Optional[str] = Field(None, max_length=17)
    asset_tag: str = Field(..., min_length=1, max_length=100)
    item_type: ItemType
    room_location: RoomLocation
    sub_location: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # Normalize MAC address format
        v = v.upper().replace("-", ":").replace(".", ":")
        # Validate MAC address format
        mac_pattern = r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$"
        if not re.match(mac_pattern, v):
            raise ValueError("Invalid MAC address format. Use XX:XX:XX:XX:XX:XX")
        return v


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    hostname: Optional[str] = Field(None, min_length=1, max_length=255)
    serial_number: Optional[str] = Field(None, min_length=1, max_length=100)
    mac_address: Optional[str] = Field(None, max_length=17)
    asset_tag: Optional[str] = Field(None, min_length=1, max_length=100)
    item_type: Optional[ItemType] = None
    room_location: Optional[RoomLocation] = None
    sub_location: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        v = v.upper().replace("-", ":").replace(".", ":")
        mac_pattern = r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$"
        if not re.match(mac_pattern, v):
            raise ValueError("Invalid MAC address format. Use XX:XX:XX:XX:XX:XX")
        return v


class InventoryItemResponse(InventoryItemBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

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
    room_location: Optional[RoomLocation] = None
    is_active: bool = True


# -----------------------------------------------------------------------------
# Statistics Schema
# -----------------------------------------------------------------------------
class DashboardStats(BaseModel):
    total_items: int
    by_type: dict[str, int]
    by_room: dict[str, int]
    recent_items: list[InventoryItemResponse]
