# API Reference

Base URL: `http://localhost:8000`

All API endpoints require authentication via cookie-based JWT token.

---

## Authentication

### Login
```http
POST /api/login
Content-Type: application/json

{"username": "admin", "password": "password"}
```

### Logout
```http
GET /logout
```

---

## Inventory Items

### List Items
```http
GET /api/items
GET /api/items?search=laptop
GET /api/items?item_type=Server
GET /api/items?room_location=Lab%20A
```

### Get Item
```http
GET /api/items/{id}
```

### Create Item
```http
POST /api/items
Content-Type: application/json

{
  "hostname": "LAB-PC-001",
  "serial_number": "SN123456",
  "asset_tag": "AT001",
  "item_type": "Desktop",
  "room_location": "Lab A",
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "ip_address": "192.168.1.100",
  "notes": "Optional notes"
}
```

### Update Item
```http
PUT /api/items/{id}
Content-Type: application/json

{"hostname": "NEW-NAME", "room_location": "Lab B"}
```

### Delete Item
```http
DELETE /api/items/{id}
```

### Bulk Room Change
```http
PUT /api/items/bulk-room
Content-Type: application/json

{"item_ids": [1, 2, 3], "room_location": "Lab B"}
```

---

## Statistics

### Get Stats
```http
GET /api/stats
```

Returns total count and breakdown by type/room.

---

## Device Sync

### Trigger Sync
```http
POST /api/sync/trigger
Content-Type: application/json

{"source": "all"}  # or "netdisco" or "librenms"
```

### Get Sync Status
```http
GET /api/sync/status/{sync_id}
```

### Sync History
```http
GET /api/sync/history
```

---

## Settings

### Item Types
```http
GET /api/settings/item-types
PUT /api/settings/item-types
Content-Type: application/json

{"item_types": ["Laptop", "Desktop", "Server"]}
```

### Room Locations
```http
GET /api/settings/rooms
PUT /api/settings/rooms
Content-Type: application/json

{"rooms": ["Lab A", "Lab B", "Server Room"]}
```

### Appearance
```http
GET /api/settings/appearance
PUT /api/settings/appearance
Content-Type: application/json

{
  "appearance": {
    "title": "My Inventory",
    "icon": "server",
    "accentColor": "#3b82f6",
    "secondaryColor": "#22d3ee"
  }
}
```

---

## User Management (Superuser only)

### List Users
```http
GET /api/users
```

### Create User
```http
POST /api/users
Content-Type: application/json

{
  "username": "newuser",
  "email": "user@example.com",
  "password": "password123",
  "role": "admin"
}
```

### Update User
```http
PUT /api/users/{id}
Content-Type: application/json

{"is_active": false, "role": "superuser"}
```

### Delete User
```http
DELETE /api/users/{id}
```

### Switch User
```http
POST /api/users/switch/{id}
```

---

## Backups

### List Backups
```http
GET /api/backups
```

### Create Backup
```http
POST /api/backups
```

### Restore Backup
```http
POST /api/backups/{id}/restore
```

### Delete Backup
```http
DELETE /api/backups/{id}
```

---

## CSV Import/Export

### Export CSV
```http
GET /api/export/csv
```

### Import CSV
```http
POST /api/import/csv
Content-Type: multipart/form-data

file: <csv_file>
```
