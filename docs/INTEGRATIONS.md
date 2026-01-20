# Integrations

LAIM can automatically discover and sync devices from network monitoring systems.

---

## Netdisco

[Netdisco](https://netdisco.org/) is an open-source network management tool.

### Setup

1. Add credentials to `.env`:
```bash
NETDISCO_API_URL=https://netdisco.example.com
NETDISCO_USERNAME=api_user
NETDISCO_PASSWORD=your_password
```

2. Restart LAIM:
```bash
docker compose restart web
```

### Getting Credentials

1. Log into Netdisco web interface
2. Go to **Admin** > **User Management**
3. Create a dedicated API user or use existing credentials
4. The API uses the same username/password as web login

---

## LibreNMS

[LibreNMS](https://www.librenms.org/) is an open-source network monitoring system.

### Setup

1. Add credentials to `.env`:
```bash
LIBRENMS_API_URL=https://librenms.example.com
LIBRENMS_API_TOKEN=your_api_token
```

2. Restart LAIM:
```bash
docker compose restart web
```

### Getting an API Token

1. Log into LibreNMS web interface
2. Go to **Settings** (gear icon) > **API** > **API Settings**
3. Click **Create API Token**
4. Copy the token to your `.env` file

---

## Sync Configuration

### Scheduled Sync

Enable automatic syncing in `.env`:
```bash
SYNC_ENABLED=true
SYNC_INTERVAL_HOURS=6
```

### IP Exclusion

Exclude devices by IP prefix:
```bash
LAIM_EXCLUDE_IPS=10.2.50.,192.168.100.
```

Useful for excluding test VMs or temporary devices.

---

## Manual Sync

### Via UI
Click the **Sync** button in the dashboard header.

### Via API
```bash
# Sync all sources
curl -X POST http://localhost:8000/api/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"source": "all"}'

# Netdisco only
curl -X POST http://localhost:8000/api/sync/trigger \
  -d '{"source": "netdisco"}'

# LibreNMS only
curl -X POST http://localhost:8000/api/sync/trigger \
  -d '{"source": "librenms"}'
```

---

## How Sync Works

1. **Fetch** - Retrieves device lists from configured sources
2. **Merge** - Combines data (LibreNMS takes priority on conflicts)
3. **Dedupe** - Matches by serial number, then MAC address
4. **Classify** - Auto-detects device type from model/vendor
5. **Upsert** - Updates existing records or creates new ones
6. **Log** - Records sync results for auditing

---

## Data Mapping

| LAIM Field | Netdisco | LibreNMS |
|------------|----------|----------|
| hostname | dns | hostname/sysName |
| serial_number | serial | serial |
| mac_address | nodes[0].mac | ports[0].ifPhysAddress |
| ip_address | ip | ip |
| model | model | hardware |
| vendor | vendor | (parsed from hardware) |
| firmware_version | os_ver | version |

---

## Sync Behavior

- **Existing items are preserved** - Sync won't overwrite manual edits
- **New items created** - Devices not in LAIM are added
- **Source tracking** - Each item shows its origin (manual, netdisco, librenms, merged)
- **History logged** - View past syncs via API or logs
