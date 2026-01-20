"""
LAIM - Lab Asset Inventory Manager
FastAPI Main Application
"""

import os
import csv
import io
import re
from contextlib import asynccontextmanager
from typing import Optional

# Room configuration - set via environment variable as comma-separated list
# Example: LAIM_ROOMS="LTB 2265,LTB 2266,LTB 2280,LTB 2281,LTB 1305,LTB 1307"
# If not set, rooms are dynamically populated from existing data
CONFIGURED_ROOMS = [r.strip() for r in os.getenv("LAIM_ROOMS", "").split(",") if r.strip()]

from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, Query, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, init_db
from app.models import User, InventoryItem, SyncLog, Backup, Settings, ItemType, UserRole, SyncStatus, DEFAULT_ITEM_TYPES
from app.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    LoginRequest,
    TokenResponse,
    DashboardStats,
    SyncTriggerRequest,
    SyncTriggerResponse,
    SyncStatusResponse,
    SyncLogResponse,
)
from app.scheduler import start_scheduler, stop_scheduler
from app.integrations.sync import DeviceSyncService
from app.auth import (
    get_current_user,
    get_current_user_optional,
    authenticate_user,
    create_access_token,
    get_password_hash,
    verify_password,
    require_admin,
    require_superuser,
)


# -----------------------------------------------------------------------------
# Application Lifespan
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and scheduler on startup."""
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()


# -----------------------------------------------------------------------------
# Settings Helpers
# -----------------------------------------------------------------------------
async def get_item_types(db: AsyncSession) -> list[str]:
    """Get item types from settings or return defaults."""
    result = await db.execute(select(Settings).where(Settings.key == "item_types"))
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return setting.value
    return DEFAULT_ITEM_TYPES


async def get_room_locations(db: AsyncSession) -> list[str]:
    """Get room locations from settings, env var, or data."""
    # First check settings table
    result = await db.execute(select(Settings).where(Settings.key == "room_locations"))
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return setting.value
    # Fall back to env var
    if CONFIGURED_ROOMS:
        return CONFIGURED_ROOMS
    # Fall back to existing data
    items_result = await db.execute(
        select(InventoryItem.room_location)
        .where(InventoryItem.is_active == True)
        .where(InventoryItem.room_location.isnot(None))
        .distinct()
    )
    rooms = [r[0] for r in items_result.fetchall() if r[0]]
    return sorted(rooms) if rooms else []


async def get_appearance_settings(db: AsyncSession) -> dict:
    """Get appearance settings from database or return defaults."""
    result = await db.execute(select(Settings).where(Settings.key == "appearance"))
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return setting.value
    return {
        "title": "LAIM",
        "icon": "chip",
        "accentColor": "#3b82f6",
        "secondaryColor": "#22d3ee"
    }


# -----------------------------------------------------------------------------
# Application Setup
# -----------------------------------------------------------------------------
app = FastAPI(
    title="LAIM - Lab Asset Inventory Manager",
    description="Modern hardware inventory management system",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker."""
    return {"status": "healthy"}


# -----------------------------------------------------------------------------
# Authentication Endpoints
# -----------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Render login page."""
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Process login form."""
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    user = await authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401
        )

    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=28800,  # 8 hours
        samesite="lax"
    )
    return response


@app.post("/api/login", response_model=TokenResponse)
async def api_login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """API login endpoint."""
    user = await authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    access_token = create_access_token(data={"sub": user.username})
    return TokenResponse(access_token=access_token)


@app.get("/logout")
async def logout():
    """Logout and clear session."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# -----------------------------------------------------------------------------
# Dashboard (Main Page)
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """Render main dashboard."""
    # Redirect to login if not authenticated
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    # Get all active items
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.is_active == True)
        .order_by(desc(InventoryItem.updated_at))
    )
    items = result.scalars().all()

    # Get configured item types, rooms, and appearance
    item_types = await get_item_types(db)
    room_locations = await get_room_locations(db)
    appearance = await get_appearance_settings(db)

    # Calculate stats
    stats = {
        "total": len(items),
        "by_type": {},
        "by_room": {}
    }

    # Count by type (using configured types)
    for type_name in item_types:
        count = len([i for i in items if i.item_type and i.item_type.value == type_name])
        stats["by_type"][type_name] = count

    # Count by room (dynamic from actual data)
    room_counts = {}
    for item in items:
        room = item.room_location
        if room:
            room_counts[room] = room_counts.get(room, 0) + 1
    stats["by_room"] = room_counts

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "stats": stats,
            "item_types": item_types,
            "room_locations": room_locations,
            "appearance": appearance,
        }
    )


# -----------------------------------------------------------------------------
# Inventory API Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/items", response_model=list[InventoryItemResponse])
async def list_items(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    search: Optional[str] = Query(None, description="Search query"),
    item_type: Optional[str] = Query(None, description="Filter by item type"),
    room: Optional[str] = Query(None, description="Filter by room"),
    active_only: bool = Query(True, description="Show only active items")
):
    """List inventory items with optional filtering."""
    query = select(InventoryItem)

    # Apply active filter
    if active_only:
        query = query.where(InventoryItem.is_active == True)

    # Apply type filter
    if item_type:
        try:
            type_enum = ItemType(item_type)
            query = query.where(InventoryItem.item_type == type_enum)
        except ValueError:
            pass

    # Apply room filter
    if room:
        query = query.where(InventoryItem.room_location == room)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                InventoryItem.hostname.ilike(search_term),
                InventoryItem.serial_number.ilike(search_term),
                InventoryItem.mac_address.ilike(search_term),
                InventoryItem.asset_tag.ilike(search_term),
                InventoryItem.sub_location.ilike(search_term),
            )
        )

    query = query.order_by(desc(InventoryItem.updated_at))
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/api/items/{item_id}", response_model=InventoryItemResponse)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get a single inventory item."""
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/api/items", response_model=InventoryItemResponse, status_code=201)
async def create_item(
    item_data: InventoryItemCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Create a new inventory item."""
    # Check for duplicate serial number
    existing = await db.execute(
        select(InventoryItem).where(InventoryItem.serial_number == item_data.serial_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Serial number already exists")

    # Check for duplicate asset tag
    existing = await db.execute(
        select(InventoryItem).where(InventoryItem.asset_tag == item_data.asset_tag)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Asset tag already exists")

    # Check for duplicate MAC address if provided
    if item_data.mac_address:
        existing = await db.execute(
            select(InventoryItem).where(InventoryItem.mac_address == item_data.mac_address)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="MAC address already exists")

    item = InventoryItem(
        **item_data.model_dump(),
        created_by=user.id,
        updated_by=user.id
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@app.put("/api/items/{item_id}", response_model=InventoryItemResponse)
async def update_item(
    item_id: int,
    item_data: InventoryItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Update an inventory item."""
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = item_data.model_dump(exclude_unset=True)

    # Check for duplicate serial number
    if "serial_number" in update_data:
        existing = await db.execute(
            select(InventoryItem).where(
                InventoryItem.serial_number == update_data["serial_number"],
                InventoryItem.id != item_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Serial number already exists")

    # Check for duplicate asset tag
    if "asset_tag" in update_data:
        existing = await db.execute(
            select(InventoryItem).where(
                InventoryItem.asset_tag == update_data["asset_tag"],
                InventoryItem.id != item_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Asset tag already exists")

    # Check for duplicate MAC address
    if "mac_address" in update_data and update_data["mac_address"]:
        existing = await db.execute(
            select(InventoryItem).where(
                InventoryItem.mac_address == update_data["mac_address"],
                InventoryItem.id != item_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="MAC address already exists")

    for key, value in update_data.items():
        setattr(item, key, value)

    item.updated_by = user.id
    await db.commit()
    await db.refresh(item)
    return item


@app.delete("/api/items/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Soft delete an inventory item."""
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_active = False
    item.updated_by = user.id
    await db.commit()
    return Response(status_code=204)


@app.post("/api/items/bulk-room")
async def bulk_update_room(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Bulk update room location for multiple items."""
    body = await request.json()
    item_ids = body.get("item_ids", [])
    new_room = body.get("room_location")

    if not item_ids:
        raise HTTPException(status_code=400, detail="No items specified")
    if not new_room:
        raise HTTPException(status_code=400, detail="Room location is required")

    # Update all specified items
    from sqlalchemy import update
    result = await db.execute(
        update(InventoryItem)
        .where(InventoryItem.id.in_(item_ids))
        .values(room_location=new_room, updated_by=user.id)
    )
    await db.commit()

    return {"message": f"Updated {result.rowcount} items to room '{new_room}'", "updated": result.rowcount}


@app.post("/api/items/bulk-delete")
async def bulk_delete_items(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Bulk soft-delete multiple items."""
    body = await request.json()
    item_ids = body.get("item_ids", [])

    if not item_ids:
        raise HTTPException(status_code=400, detail="No items specified")

    # Soft delete all specified items
    from sqlalchemy import update
    result = await db.execute(
        update(InventoryItem)
        .where(InventoryItem.id.in_(item_ids))
        .where(InventoryItem.is_active == True)
        .values(is_active=False, updated_by=user.id)
    )
    await db.commit()

    return {"message": f"Deleted {result.rowcount} items", "deleted": result.rowcount}


# -----------------------------------------------------------------------------
# User Management API (Superuser only)
# -----------------------------------------------------------------------------
@app.get("/api/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser)
):
    """List all users (superuser only)."""
    result = await db.execute(select(User).order_by(User.username))
    return result.scalars().all()


@app.post("/api/users", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser)
):
    """Create a new user (superuser only)."""
    # Check for existing username
    existing = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    # Check for existing email
    existing = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@app.put("/api/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser)
):
    """Update a user (superuser only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.model_dump(exclude_unset=True)

    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    if "email" in update_data:
        existing = await db.execute(
            select(User).where(User.email == update_data["email"], User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already exists")

    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user


@app.delete("/api/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser)
):
    """Delete a user (superuser only). Cannot delete yourself."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
    return {"message": "User deleted successfully"}


@app.post("/api/users/switch/{user_id}")
async def switch_user(
    user_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser)
):
    """Switch to another user account (superuser only). Creates a new session as that user."""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not target_user.is_active:
        raise HTTPException(status_code=400, detail="Cannot switch to inactive user")

    # Create new token for target user
    access_token = create_access_token(data={"sub": target_user.username})

    # Set the cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 days
        samesite="lax"
    )

    return {"message": f"Switched to user {target_user.username}", "username": target_user.username}


# -----------------------------------------------------------------------------
# Password Change API
# -----------------------------------------------------------------------------
@app.put("/api/me/password")
async def change_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Change the current user's password."""
    body = await request.json()
    current_password = body.get("current_password", "")
    new_password = body.get("new_password", "")
    confirm_password = body.get("confirm_password", "")

    # Validate current password
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")

    # Update password
    user.hashed_password = get_password_hash(new_password)
    await db.commit()

    return {"message": "Password changed successfully"}


# -----------------------------------------------------------------------------
# Statistics API
# -----------------------------------------------------------------------------
@app.get("/api/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get dashboard statistics."""
    # Total count
    total_result = await db.execute(
        select(func.count(InventoryItem.id)).where(InventoryItem.is_active == True)
    )
    total = total_result.scalar()

    # Count by type
    by_type = {}
    for item_type in ItemType:
        result = await db.execute(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.item_type == item_type,
                InventoryItem.is_active == True
            )
        )
        by_type[item_type.value] = result.scalar()

    # Count by room (dynamic from actual data)
    room_result = await db.execute(
        select(InventoryItem.room_location, func.count(InventoryItem.id))
        .where(InventoryItem.is_active == True)
        .group_by(InventoryItem.room_location)
    )
    by_room = {row[0]: row[1] for row in room_result.fetchall()}

    return {
        "total": total,
        "by_type": by_type,
        "by_room": by_room
    }


@app.post("/api/rooms/rename")
async def rename_room(
    old_name: str = Query(..., description="Current room name"),
    new_name: str = Query(..., description="New room name"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Rename all items with a specific room to a new room name."""
    # Count items to be updated
    count_result = await db.execute(
        select(func.count(InventoryItem.id)).where(
            InventoryItem.room_location == old_name
        )
    )
    count = count_result.scalar()

    if count == 0:
        raise HTTPException(status_code=404, detail=f"No items found with room '{old_name}'")

    # Update all items
    from sqlalchemy import update
    await db.execute(
        update(InventoryItem)
        .where(InventoryItem.room_location == old_name)
        .values(room_location=new_name)
    )
    await db.commit()

    return {"message": f"Renamed {count} items from '{old_name}' to '{new_name}'"}


@app.get("/api/rooms")
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all unique room names in the database."""
    result = await db.execute(
        select(InventoryItem.room_location, func.count(InventoryItem.id))
        .group_by(InventoryItem.room_location)
        .order_by(InventoryItem.room_location)
    )
    rooms = [{"name": row[0], "count": row[1]} for row in result.fetchall()]
    return {"rooms": rooms, "configured": CONFIGURED_ROOMS}


# -----------------------------------------------------------------------------
# CSV Import Helper Functions
# -----------------------------------------------------------------------------
def normalize_mac(mac: str) -> Optional[str]:
    """Normalize MAC address to XX:XX:XX:XX:XX:XX format."""
    if not mac or mac.strip() == "":
        return None
    mac = mac.upper().replace("-", "").replace(":", "").replace(".", "").replace(" ", "")
    if len(mac) == 12:
        return ":".join([mac[i:i+2] for i in range(0, 12, 2)])
    return mac


def parse_item_type(value: str) -> ItemType:
    """Parse item type from string."""
    value = value.strip().upper()
    mapping = {
        "LAPTOP": ItemType.LAPTOP,
        "DESKTOP": ItemType.DESKTOP,
        "SMART TV": ItemType.SMART_TV,
        "SMARTTV": ItemType.SMART_TV,
        "TV": ItemType.SMART_TV,
        "SERVER": ItemType.SERVER,
        "WAP": ItemType.WAP,
        "ACCESS POINT": ItemType.WAP,
        "AP": ItemType.WAP,
        "FIREWALL": ItemType.FIREWALL,
        "ROUTER": ItemType.FIREWALL,  # Map Router to Firewall for backwards compatibility
        "SWITCH": ItemType.SWITCH,
    }
    if value in mapping:
        return mapping[value]
    raise ValueError(f"Unknown item type: {value}")


def parse_room(value: str) -> str:
    """Parse room location from string."""
    value = value.strip().replace("Room ", "").replace("room ", "")
    if not value:
        raise ValueError("Room location cannot be empty")
    return value


# -----------------------------------------------------------------------------
# CSV Import API
# -----------------------------------------------------------------------------
@app.post("/api/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Import inventory items from CSV file."""

    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    # Read CSV content
    try:
        contents = await file.read()
        decoded = contents.decode('utf-8')
        csv_file = io.StringIO(decoded)
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    # Validate required columns
    required_columns = ['hostname', 'serial_number', 'asset_tag', 'item_type', 'room_location']
    first_row = rows[0]
    missing_columns = [col for col in required_columns if col not in first_row]

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(missing_columns)}"
        )

    # Process rows
    created = 0
    skipped = 0
    errors = []

    for idx, row in enumerate(rows, start=1):
        hostname = row.get('hostname', '').strip()
        serial = row.get('serial_number', '').strip()
        asset_tag = row.get('asset_tag', '').strip()

        if not hostname or not serial or not asset_tag:
            errors.append(f"Row {idx}: Missing required fields")
            continue

        try:
            # Parse fields
            item_type = parse_item_type(row.get('item_type', ''))
            room = parse_room(row.get('room_location', ''))
            mac = normalize_mac(row.get('mac_address', ''))
            sub_location = row.get('sub_location', '').strip() or None
            notes = row.get('notes', '').strip() or None

            # Check for duplicates
            existing = await db.execute(
                select(InventoryItem).where(
                    (InventoryItem.serial_number == serial) |
                    (InventoryItem.asset_tag == asset_tag)
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            # Create item
            item = InventoryItem(
                hostname=hostname,
                serial_number=serial,
                asset_tag=asset_tag,
                mac_address=mac,
                item_type=item_type,
                room_location=room,
                sub_location=sub_location,
                notes=notes,
                created_by=user.id,
                updated_by=user.id
            )
            db.add(item)
            created += 1

        except ValueError as e:
            errors.append(f"Row {idx}: {str(e)}")
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")

    # Commit changes
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save items: {str(e)}")

    return JSONResponse({
        "success": True,
        "total_rows": len(rows),
        "created": created,
        "skipped": skipped,
        "errors": errors
    })


# -----------------------------------------------------------------------------
# Backup API Endpoints
# -----------------------------------------------------------------------------
@app.post("/api/backups")
async def create_backup(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Create a server-side backup of all inventory items."""
    result = await db.execute(
        select(InventoryItem).where(InventoryItem.is_active == True).order_by(InventoryItem.id)
    )
    items = result.scalars().all()

    backup_data = [
        {
            "id": item.id,
            "hostname": item.hostname,
            "item_type": item.item_type.value,
            "serial_number": item.serial_number,
            "mac_address": item.mac_address,
            "asset_tag": item.asset_tag,
            "ip_address": item.ip_address,
            "room_location": item.room_location,
            "sub_location": item.sub_location,
            "notes": item.notes,
            "model": item.model,
            "vendor": item.vendor,
            "firmware_version": item.firmware_version,
            "source": item.source,
            "source_id": item.source_id,
        }
        for item in items
    ]

    backup = Backup(
        created_by=user.id,
        item_count=len(items),
        data=backup_data
    )
    db.add(backup)
    await db.commit()
    await db.refresh(backup)

    return {
        "id": backup.id,
        "created_at": backup.created_at.isoformat(),
        "item_count": backup.item_count,
        "message": f"Backup created with {backup.item_count} items"
    }


def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


@app.get("/api/backups")
async def list_backups(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=10, le=50)
):
    """List recent backups."""
    result = await db.execute(
        select(Backup).order_by(desc(Backup.created_at)).limit(limit)
    )
    backups = result.scalars().all()

    return [
        {
            "id": b.id,
            "created_at": b.created_at.isoformat(),
            "item_count": b.item_count,
            "note": b.note,
            "file_size": format_file_size(len(str(b.data).encode('utf-8'))) if b.data else "0 B"
        }
        for b in backups
    ]


@app.post("/api/backups/{backup_id}/restore")
async def restore_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Restore inventory from a backup."""
    # Get the backup
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    # Soft-delete all current items
    await db.execute(
        select(InventoryItem).where(InventoryItem.is_active == True)
    )
    from sqlalchemy import update
    await db.execute(
        update(InventoryItem).where(InventoryItem.is_active == True).values(is_active=False)
    )

    # Restore items from backup
    restored_count = 0
    for item_data in backup.data:
        # Check if item exists (by original ID)
        existing = await db.execute(
            select(InventoryItem).where(InventoryItem.id == item_data["id"])
        )
        existing_item = existing.scalar_one_or_none()

        if existing_item:
            # Reactivate and update existing item
            existing_item.is_active = True
            existing_item.hostname = item_data["hostname"]
            existing_item.item_type = ItemType(item_data["item_type"])
            existing_item.serial_number = item_data.get("serial_number")
            existing_item.mac_address = item_data.get("mac_address")
            existing_item.asset_tag = item_data.get("asset_tag")
            existing_item.ip_address = item_data.get("ip_address")
            existing_item.room_location = item_data.get("room_location")
            existing_item.sub_location = item_data.get("sub_location")
            existing_item.notes = item_data.get("notes")
            existing_item.model = item_data.get("model")
            existing_item.vendor = item_data.get("vendor")
            existing_item.firmware_version = item_data.get("firmware_version")
            existing_item.source = item_data.get("source")
            existing_item.source_id = item_data.get("source_id")
        else:
            # Create new item
            new_item = InventoryItem(
                hostname=item_data["hostname"],
                item_type=ItemType(item_data["item_type"]),
                serial_number=item_data.get("serial_number"),
                mac_address=item_data.get("mac_address"),
                asset_tag=item_data.get("asset_tag"),
                ip_address=item_data.get("ip_address"),
                room_location=item_data.get("room_location"),
                sub_location=item_data.get("sub_location"),
                notes=item_data.get("notes"),
                model=item_data.get("model"),
                vendor=item_data.get("vendor"),
                firmware_version=item_data.get("firmware_version"),
                source=item_data.get("source"),
                source_id=item_data.get("source_id"),
                is_active=True
            )
            db.add(new_item)
        restored_count += 1

    await db.commit()

    return {
        "message": f"Restored {restored_count} items from backup",
        "restored_count": restored_count,
        "backup_id": backup_id
    }


@app.delete("/api/backups/{backup_id}")
async def delete_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Delete a backup."""
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    await db.delete(backup)
    await db.commit()

    return {"message": "Backup deleted"}


# -----------------------------------------------------------------------------
# Settings API Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/settings/item-types")
async def get_item_types_api(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get configured item types."""
    types = await get_item_types(db)
    return {"item_types": types}


@app.put("/api/settings/item-types")
async def update_item_types_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Update configured item types."""
    body = await request.json()
    item_types = body.get("item_types", [])

    if not item_types or not isinstance(item_types, list):
        raise HTTPException(status_code=400, detail="item_types must be a non-empty list")

    # Clean up types
    item_types = [t.strip() for t in item_types if t and t.strip()]

    # Update or create setting
    result = await db.execute(select(Settings).where(Settings.key == "item_types"))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = item_types
    else:
        setting = Settings(key="item_types", value=item_types)
        db.add(setting)

    await db.commit()
    return {"item_types": item_types, "message": "Item types updated"}


@app.get("/api/settings/rooms")
async def get_rooms_api(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get configured room locations."""
    rooms = await get_room_locations(db)
    return {"rooms": rooms}


@app.put("/api/settings/rooms")
async def update_rooms_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Update configured room locations."""
    body = await request.json()
    rooms = body.get("rooms", [])

    if not isinstance(rooms, list):
        raise HTTPException(status_code=400, detail="rooms must be a list")

    # Clean up rooms
    rooms = [r.strip() for r in rooms if r and r.strip()]

    # Update or create setting
    result = await db.execute(select(Settings).where(Settings.key == "room_locations"))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = rooms
    else:
        setting = Settings(key="room_locations", value=rooms)
        db.add(setting)

    await db.commit()
    return {"rooms": rooms, "message": "Room locations updated"}


@app.get("/api/settings/appearance")
async def get_appearance_api(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get appearance settings."""
    result = await db.execute(select(Settings).where(Settings.key == "appearance"))
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return {"appearance": setting.value}
    # Return defaults
    return {
        "appearance": {
            "title": "LAIM",
            "icon": "chip",
            "accentColor": "#3b82f6",
            "secondaryColor": "#22d3ee"
        }
    }


@app.put("/api/settings/appearance")
async def update_appearance_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Update appearance settings."""
    body = await request.json()
    appearance = body.get("appearance", {})

    # Validate required fields
    title = appearance.get("title", "LAIM").strip()[:30]
    icon = appearance.get("icon", "chip")
    accent_color = appearance.get("accentColor", "#3b82f6")
    secondary_color = appearance.get("secondaryColor", "#22d3ee")

    # Validate icon is in allowed list
    allowed_icons = ["chip", "server", "database", "cube", "folder", "globe",
                     "home", "office", "beaker", "clipboard", "collection", "desktop"]
    if icon not in allowed_icons:
        icon = "chip"

    # Validate hex colors
    hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
    if not hex_pattern.match(accent_color):
        accent_color = "#3b82f6"
    if not hex_pattern.match(secondary_color):
        secondary_color = "#22d3ee"

    appearance_data = {
        "title": title or "LAIM",
        "icon": icon,
        "accentColor": accent_color,
        "secondaryColor": secondary_color
    }

    # Update or create setting
    result = await db.execute(select(Settings).where(Settings.key == "appearance"))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = appearance_data
    else:
        setting = Settings(key="appearance", value=appearance_data)
        db.add(setting)

    await db.commit()
    return {"appearance": appearance_data, "message": "Appearance settings updated"}


# -----------------------------------------------------------------------------
# Device Sync API Endpoints
# -----------------------------------------------------------------------------
@app.post("/api/sync/trigger", response_model=SyncTriggerResponse)
async def trigger_sync(
    request: SyncTriggerRequest = SyncTriggerRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """
    Trigger a manual device sync from external systems.

    Args:
        source: 'all', 'netdisco', or 'librenms'

    Returns:
        Sync log ID and status for tracking
    """
    service = DeviceSyncService(db)

    if request.source == "netdisco":
        sync_log, result = await service.sync_netdisco_only()
    elif request.source == "librenms":
        sync_log, result = await service.sync_librenms_only()
    else:
        sync_log, result = await service.sync_all()

    return SyncTriggerResponse(
        sync_id=sync_log.id,
        message=f"Sync completed: {result.created} created, {result.updated} updated, {result.skipped} skipped",
        status=sync_log.status.value
    )


@app.get("/api/sync/status/{sync_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    sync_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get the status of a sync operation.

    Args:
        sync_id: ID of the sync log entry

    Returns:
        Current sync status and statistics
    """
    result = await db.execute(
        select(SyncLog).where(SyncLog.id == sync_id)
    )
    sync_log = result.scalar_one_or_none()

    if not sync_log:
        raise HTTPException(status_code=404, detail="Sync log not found")

    return SyncStatusResponse(
        id=sync_log.id,
        started_at=sync_log.started_at,
        completed_at=sync_log.completed_at,
        source=sync_log.source,
        status=sync_log.status,
        devices_found=sync_log.devices_found,
        created=sync_log.created,
        updated=sync_log.updated,
        skipped=sync_log.skipped,
        errors=sync_log.errors
    )


@app.get("/api/sync/history", response_model=list[SyncLogResponse])
async def get_sync_history(
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get sync history.

    Args:
        limit: Maximum number of records to return (default: 20)

    Returns:
        List of recent sync log entries
    """
    result = await db.execute(
        select(SyncLog)
        .order_by(desc(SyncLog.started_at))
        .limit(limit)
    )
    return result.scalars().all()
