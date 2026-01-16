"""
LAIM - Lab Asset Inventory Manager
FastAPI Main Application
"""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, init_db
from app.models import User, InventoryItem, ItemType, RoomLocation, UserRole
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
)
from app.auth import (
    get_current_user,
    get_current_user_optional,
    authenticate_user,
    create_access_token,
    get_password_hash,
    require_admin,
    require_superuser,
)


# -----------------------------------------------------------------------------
# Application Lifespan
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


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

    # Calculate stats
    stats = {
        "total": len(items),
        "by_type": {},
        "by_room": {}
    }

    for item_type in ItemType:
        count = len([i for i in items if i.item_type == item_type])
        stats["by_type"][item_type.value] = count

    for room in RoomLocation:
        count = len([i for i in items if i.room_location == room])
        stats["by_room"][room.value] = count

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "stats": stats,
            "item_types": [t.value for t in ItemType],
            "room_locations": [r.value for r in RoomLocation],
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
        try:
            room_enum = RoomLocation(room)
            query = query.where(InventoryItem.room_location == room_enum)
        except ValueError:
            pass

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

    # Count by room
    by_room = {}
    for room in RoomLocation:
        result = await db.execute(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.room_location == room,
                InventoryItem.is_active == True
            )
        )
        by_room[room.value] = result.scalar()

    return {
        "total": total,
        "by_type": by_type,
        "by_room": by_room
    }
