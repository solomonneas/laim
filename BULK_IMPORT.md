# Bulk Import Guide

Import inventory items from a CSV/Excel spreadsheet.

## Quick Start

### 1. Prepare Your Spreadsheet

Create a CSV file with these columns:

**Required:**
- `hostname` - Device hostname (e.g., LAB-LAPTOP-001)
- `serial_number` - Manufacturer serial number
- `asset_tag` - Your internal asset tag
- `item_type` - One of: `Laptop`, `Desktop`, `Smart TV`, `Server`, `WAP`
- `room_location` - Either `2265` or `2266`

**Optional:**
- `mac_address` - Network MAC address (any format: XX:XX:XX:XX:XX:XX, XX-XX-XX-XX-XX-XX, or XXXXXXXXXXXX)
- `sub_location` - Specific location (e.g., "Rack 1", "Desk 3", "Shelf B")
- `notes` - Additional notes

### 2. Export from Excel

1. Open your spreadsheet in Excel
2. Save As → CSV (Comma delimited) (*.csv)
3. Name it something like `inventory.csv`

### 3. Copy CSV to Container

```bash
# From your Windows/Mac machine
scp inventory.csv root@<proxmox-ip>:/tmp/

# On Proxmox host
pct push 200 /tmp/inventory.csv /opt/laim/inventory.csv
```

Or use WinSCP/FileZilla to copy to Proxmox, then push to container.

### 4. Import the Data

```bash
# Enter the container
pct enter 200

# Navigate to project
cd /opt/laim

# Preview the import (dry run - doesn't save anything)
docker compose exec web python -m app.bulk_import inventory.csv --dry-run

# If everything looks good, import for real
docker compose exec web python -m app.bulk_import inventory.csv
```

## Examples

### Example CSV Format

See `import_template.csv` for a complete example:

```csv
hostname,serial_number,mac_address,asset_tag,item_type,room_location,sub_location,notes
LAB-LAPTOP-001,SN-LP-001,00:1A:2B:3C:4D:01,AST-2024-0001,Laptop,2265,Desk 1,Dell Latitude 5540
LAB-SERVER-001,SN-SV-001,00:1A:2B:3C:4D:03,AST-2024-0003,Server,2266,Rack 1 U1-U4,Dell PowerEdge R750
```

### Accepted Item Types

- `Laptop` or `LAPTOP`
- `Desktop` or `DESKTOP`
- `Smart TV`, `SMARTTV`, or `TV`
- `Server` or `SERVER`
- `WAP`, `Access Point`, or `AP`

### Accepted Room Values

- `2265` or `Room 2265`
- `2266` or `Room 2266`

## Command Options

```bash
# Dry run (preview without importing)
docker compose exec web python -m app.bulk_import inventory.csv --dry-run

# Import and skip duplicates (default)
docker compose exec web python -m app.bulk_import inventory.csv

# Import and fail on duplicates
docker compose exec web python -m app.bulk_import inventory.csv --no-skip-duplicates
```

## Tips

1. **Always do a dry run first** - Use `--dry-run` to preview the import
2. **Check for duplicates** - The script will skip items with duplicate serial numbers or asset tags
3. **MAC address format** - Any common format works (colons, dashes, or no separators)
4. **Empty fields** - Leave optional fields empty if you don't have the data
5. **Quotes in CSV** - If your notes contain commas, Excel will automatically quote them

## Common Issues

### "Missing required columns"
- Make sure your CSV has: `hostname`, `serial_number`, `asset_tag`, `item_type`, `room_location`
- Column names are case-sensitive and must match exactly

### "Unknown item type"
- Check spelling: `Laptop`, `Desktop`, `Smart TV`, `Server`, or `WAP`
- Case doesn't matter but spelling does

### "Unknown room"
- Use `2265` or `2266`
- Don't include extra text like "Room " (the script handles that automatically)

### "Duplicate found"
- Two items have the same serial number or asset tag
- Use `--dry-run` to identify duplicates before importing
- By default, duplicates are skipped (not imported)

## Output Example

```
======================================================================
LAIM - Bulk CSV Import
======================================================================

File: inventory.csv
Dry Run: False
Skip Duplicates: True

Found 50 rows in CSV

----------------------------------------------------------------------
Processing rows...
----------------------------------------------------------------------
[CREATE] Row 1: LAB-LAPTOP-001 (Laptop) - Room 2265
[CREATE] Row 2: LAB-LAPTOP-002 (Laptop) - Room 2265
[SKIP] Row 3: Duplicate - LAB-LAPTOP-001 (Serial: SN-LP-001)
[CREATE] Row 4: LAB-SERVER-001 (Server) - Room 2266
...

[SUCCESS] Changes committed to database

======================================================================
Import Summary
======================================================================
Total Rows:    50
Created:       47
Skipped:       3
Errors:        0
======================================================================
```

## Advanced: Direct Database Access

If you need to import hundreds/thousands of items, you can also use direct PostgreSQL COPY:

```bash
# Enter database container
docker compose exec db bash

# Copy your CSV to the container first, then:
psql -U laim -d laim -c "\COPY inventory_items(hostname,serial_number,mac_address,asset_tag,item_type,room_location,sub_location,notes) FROM '/path/to/file.csv' WITH (FORMAT csv, HEADER true);"
```

This is faster for very large imports but requires exact column matching with the database schema.
