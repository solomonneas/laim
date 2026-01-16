"""
LAIM - Lab Asset Inventory Manager
Bulk CSV Import Script
"""

import sys
import csv
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SyncSessionLocal
from app.models import InventoryItem, ItemType, RoomLocation


def normalize_mac(mac: str) -> str:
    """Normalize MAC address to XX:XX:XX:XX:XX:XX format."""
    if not mac or mac.strip() == "":
        return None
    # Remove common separators and spaces
    mac = mac.upper().replace("-", "").replace(":", "").replace(".", "").replace(" ", "")
    # Add colons every 2 characters
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
    }
    if value in mapping:
        return mapping[value]
    raise ValueError(f"Unknown item type: {value}")


def parse_room(value: str) -> RoomLocation:
    """Parse room location from string."""
    value = value.strip()
    # Remove "Room " prefix if present
    value = value.replace("Room ", "").replace("room ", "")
    if value == "2265":
        return RoomLocation.ROOM_2265
    elif value == "2266":
        return RoomLocation.ROOM_2266
    raise ValueError(f"Unknown room: {value}")


def import_csv(csv_file: str, dry_run: bool = False, skip_duplicates: bool = True):
    """Import inventory items from CSV file."""

    print("=" * 70)
    print("LAIM - Bulk CSV Import")
    print("=" * 70)
    print(f"\nFile: {csv_file}")
    print(f"Dry Run: {dry_run}")
    print(f"Skip Duplicates: {skip_duplicates}")
    print()

    # Validate file exists
    if not Path(csv_file).exists():
        print(f"[ERROR] File not found: {csv_file}")
        sys.exit(1)

    # Read CSV
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"[ERROR] Failed to read CSV: {e}")
        sys.exit(1)

    print(f"Found {len(rows)} rows in CSV\n")

    # Expected columns
    required_columns = ['hostname', 'serial_number', 'asset_tag', 'item_type', 'room_location']
    optional_columns = ['mac_address', 'sub_location', 'notes']

    # Validate columns
    if not rows:
        print("[ERROR] CSV file is empty")
        sys.exit(1)

    first_row = rows[0]
    missing_columns = [col for col in required_columns if col not in first_row]

    if missing_columns:
        print(f"[ERROR] Missing required columns: {', '.join(missing_columns)}")
        print(f"\nRequired columns: {', '.join(required_columns)}")
        print(f"Optional columns: {', '.join(optional_columns)}")
        print(f"\nFound columns: {', '.join(first_row.keys())}")
        sys.exit(1)

    # Process rows
    db = SyncSessionLocal()
    created = 0
    skipped = 0
    errors = 0

    try:
        print("-" * 70)
        print("Processing rows...")
        print("-" * 70)

        for idx, row in enumerate(rows, start=1):
            hostname = row.get('hostname', '').strip()
            serial = row.get('serial_number', '').strip()
            asset_tag = row.get('asset_tag', '').strip()

            if not hostname or not serial or not asset_tag:
                print(f"[SKIP] Row {idx}: Missing required fields")
                skipped += 1
                continue

            try:
                # Parse fields
                item_type = parse_item_type(row.get('item_type', ''))
                room = parse_room(row.get('room_location', ''))
                mac = normalize_mac(row.get('mac_address', ''))
                sub_location = row.get('sub_location', '').strip() or None
                notes = row.get('notes', '').strip() or None

                # Check for duplicates
                existing = db.query(InventoryItem).filter(
                    (InventoryItem.serial_number == serial) |
                    (InventoryItem.asset_tag == asset_tag)
                ).first()

                if existing:
                    if skip_duplicates:
                        print(f"[SKIP] Row {idx}: Duplicate - {hostname} (Serial: {serial})")
                        skipped += 1
                        continue
                    else:
                        print(f"[ERROR] Row {idx}: Duplicate found - {hostname}")
                        errors += 1
                        continue

                # Create item
                if not dry_run:
                    item = InventoryItem(
                        hostname=hostname,
                        serial_number=serial,
                        asset_tag=asset_tag,
                        mac_address=mac,
                        item_type=item_type,
                        room_location=room,
                        sub_location=sub_location,
                        notes=notes,
                    )
                    db.add(item)

                print(f"[CREATE] Row {idx}: {hostname} ({item_type.value}) - Room {room.value}")
                created += 1

            except ValueError as e:
                print(f"[ERROR] Row {idx}: {e}")
                errors += 1
            except Exception as e:
                print(f"[ERROR] Row {idx}: Unexpected error - {e}")
                errors += 1

        # Commit changes
        if not dry_run and created > 0:
            db.commit()
            print("\n[SUCCESS] Changes committed to database")
        elif dry_run:
            print("\n[DRY RUN] No changes made to database")

    except Exception as e:
        print(f"\n[ERROR] Import failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

    # Summary
    print("\n" + "=" * 70)
    print("Import Summary")
    print("=" * 70)
    print(f"Total Rows:    {len(rows)}")
    print(f"Created:       {created}")
    print(f"Skipped:       {skipped}")
    print(f"Errors:        {errors}")
    print("=" * 70)

    if dry_run and created > 0:
        print("\n[INFO] This was a dry run. Run without --dry-run to import.")


def main():
    parser = argparse.ArgumentParser(
        description="Bulk import inventory items from CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV Format:
  Required columns: hostname, serial_number, asset_tag, item_type, room_location
  Optional columns: mac_address, sub_location, notes

  item_type values: Laptop, Desktop, Smart TV, Server, WAP
  room_location values: 2265, 2266

Example CSV:
  hostname,serial_number,mac_address,asset_tag,item_type,room_location,sub_location,notes
  LAB-LAPTOP-001,SN12345,00:1A:2B:3C:4D:01,AST-001,Laptop,2265,Desk 1,Dell Latitude
  LAB-SERVER-001,SN67890,00:1A:2B:3C:4D:02,AST-002,Server,2266,Rack 1,HP ProLiant

Usage:
  # Dry run (preview without importing)
  python -m app.bulk_import data.csv --dry-run

  # Import with duplicate checking
  python -m app.bulk_import data.csv

  # Import and fail on duplicates
  python -m app.bulk_import data.csv --no-skip-duplicates
        """
    )
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--dry-run', action='store_true', help='Preview import without saving')
    parser.add_argument('--no-skip-duplicates', action='store_true', help='Fail on duplicates instead of skipping')

    args = parser.parse_args()

    import_csv(
        args.csv_file,
        dry_run=args.dry_run,
        skip_duplicates=not args.no_skip_duplicates
    )


if __name__ == "__main__":
    main()
