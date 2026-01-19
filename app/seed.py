"""
LAIM - Lab Asset Inventory Manager
Database Seeding Script
Creates initial superuser and admin accounts.
"""

import os
import sys
from sqlalchemy import select

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SyncSessionLocal, init_db_sync
from app.models import User, UserRole
from app.auth import get_password_hash


# Default user configurations
DEFAULT_USERS = [
    {
        "username": os.getenv("SUPERUSER_USERNAME", "superadmin"),
        "email": os.getenv("SUPERUSER_EMAIL", "superadmin@laim.local"),
        "password": os.getenv("SUPERUSER_PASSWORD", "SuperAdmin123!"),
        "role": UserRole.SUPERUSER,
    },
    {
        "username": "admin1",
        "email": "admin1@laim.local",
        "password": "Admin123!",
        "role": UserRole.ADMIN,
    },
    {
        "username": "admin2",
        "email": "admin2@laim.local",
        "password": "Admin123!",
        "role": UserRole.ADMIN,
    },
    {
        "username": "admin3",
        "email": "admin3@laim.local",
        "password": "Admin123!",
        "role": UserRole.ADMIN,
    },
]


def seed_users():
    """Create initial user accounts."""
    print("=" * 60)
    print("LAIM - Database Seeding")
    print("=" * 60)

    # Initialize database tables
    print("\nInitializing database tables...")
    init_db_sync()
    print("Database tables created successfully.")

    # Create session
    db = SyncSessionLocal()

    try:
        print("\nSeeding user accounts...")
        created_count = 0
        skipped_count = 0

        for user_data in DEFAULT_USERS:
            # Check if user already exists
            existing = db.execute(
                select(User).where(User.username == user_data["username"])
            ).scalar_one_or_none()

            if existing:
                print(f"  [SKIP] User '{user_data['username']}' already exists")
                skipped_count += 1
                continue

            # Create new user
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=get_password_hash(user_data["password"]),
                role=user_data["role"],
                is_active=True,
            )
            db.add(user)
            print(f"  [CREATE] User '{user_data['username']}' ({user_data['role'].value})")
            created_count += 1

        db.commit()

        print("\n" + "-" * 60)
        print(f"Seeding complete: {created_count} created, {skipped_count} skipped")
        print("-" * 60)

        # Print credentials summary
        print("\nDefault Credentials:")
        print("-" * 40)
        for user_data in DEFAULT_USERS:
            role_label = "SUPERUSER" if user_data["role"] == UserRole.SUPERUSER else "ADMIN"
            print(f"  [{role_label}] {user_data['username']}")
            print(f"           Password: {user_data['password']}")
            print()

        print("=" * 60)
        print("IMPORTANT: Change default passwords in production!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Seeding failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def seed_sample_data():
    """Create sample inventory items for testing."""
    from app.models import InventoryItem, ItemType, RoomLocation

    SAMPLE_ITEMS = [
        {
            "hostname": "LAB-LAPTOP-001",
            "serial_number": "SN-LP-001",
            "mac_address": "00:1A:2B:3C:4D:01",
            "asset_tag": "AST-2024-0001",
            "item_type": ItemType.LAPTOP,
            "room_location": RoomLocation.ROOM_2265,
            "sub_location": "Desk 1",
            "notes": "Dell Latitude 5540",
        },
        {
            "hostname": "LAB-DESKTOP-001",
            "serial_number": "SN-DT-001",
            "mac_address": "00:1A:2B:3C:4D:02",
            "asset_tag": "AST-2024-0002",
            "item_type": ItemType.DESKTOP,
            "room_location": RoomLocation.ROOM_2265,
            "sub_location": "Desk 2",
            "notes": "HP ProDesk 400 G7",
        },
        {
            "hostname": "LAB-SERVER-001",
            "serial_number": "SN-SV-001",
            "mac_address": "00:1A:2B:3C:4D:03",
            "asset_tag": "AST-2024-0003",
            "item_type": ItemType.SERVER,
            "room_location": RoomLocation.ROOM_2266,
            "sub_location": "Rack 1, U1-U4",
            "notes": "Dell PowerEdge R750",
        },
        {
            "hostname": "LAB-WAP-001",
            "serial_number": "SN-WP-001",
            "mac_address": "00:1A:2B:3C:4D:04",
            "asset_tag": "AST-2024-0004",
            "item_type": ItemType.WAP,
            "room_location": RoomLocation.ROOM_2265,
            "sub_location": "Ceiling Mount A",
            "notes": "Cisco Catalyst 9120AX",
        },
        {
            "hostname": "LAB-TV-001",
            "serial_number": "SN-TV-001",
            "mac_address": "00:1A:2B:3C:4D:05",
            "asset_tag": "AST-2024-0005",
            "item_type": ItemType.SMART_TV,
            "room_location": RoomLocation.ROOM_2265,
            "sub_location": "Wall Mount Front",
            "notes": "Samsung 65\" QN65Q80C",
        },
    ]

    print("\nSeeding sample inventory data...")
    db = SyncSessionLocal()

    try:
        created_count = 0
        for item_data in SAMPLE_ITEMS:
            existing = db.execute(
                select(InventoryItem).where(
                    InventoryItem.serial_number == item_data["serial_number"]
                )
            ).scalar_one_or_none()

            if existing:
                print(f"  [SKIP] Item '{item_data['hostname']}' already exists")
                continue

            item = InventoryItem(**item_data)
            db.add(item)
            print(f"  [CREATE] Item '{item_data['hostname']}'")
            created_count += 1

        db.commit()
        print(f"\nSample data seeding complete: {created_count} items created")

    except Exception as e:
        print(f"\n[ERROR] Sample data seeding failed: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LAIM Database Seeding")
    parser.add_argument(
        "--with-samples",
        action="store_true",
        help="Also seed sample inventory data"
    )
    args = parser.parse_args()

    seed_users()

    if args.with_samples:
        seed_sample_data()
