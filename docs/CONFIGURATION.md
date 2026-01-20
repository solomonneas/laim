# Configuration

## Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | Database username | laim |
| `POSTGRES_PASSWORD` | Database password | (generated) |
| `POSTGRES_DB` | Database name | laim |
| `APP_PORT` | Application port | 8000 |
| `SECRET_KEY` | JWT secret key | (generated) |

### Initial Admin Account

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPERUSER_USERNAME` | Initial superuser | superadmin |
| `SUPERUSER_PASSWORD` | Initial password | SuperAdmin123! |
| `SUPERUSER_EMAIL` | Initial email | admin@example.com |

### Sync Integration

| Variable | Description | Default |
|----------|-------------|---------|
| `NETDISCO_API_URL` | Netdisco server URL | (none) |
| `NETDISCO_USERNAME` | Netdisco username | (none) |
| `NETDISCO_PASSWORD` | Netdisco password | (none) |
| `LIBRENMS_API_URL` | LibreNMS server URL | (none) |
| `LIBRENMS_API_TOKEN` | LibreNMS API token | (none) |
| `SYNC_ENABLED` | Enable scheduled sync | true |
| `SYNC_INTERVAL_HOURS` | Hours between syncs | 6 |
| `SYNC_RATE_LIMIT` | API requests/second | 10 |

### Advanced Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `LAIM_ROOMS` | Comma-separated room list | (from data) |
| `LAIM_EXCLUDE_IPS` | IP prefixes to exclude from sync | (none) |

---

## In-App Settings

Access via the gear icon in the header.

### Item Types
Customize the device categories available in dropdowns. Drag to reorder.

### Room Locations
Manage room/location options. Drag to reorder.

### Appearance
- **Header Title** - Custom application name
- **Header Icon** - Choose from 12 icons
- **Colors** - Accent and secondary gradient colors
- **Presets** - Quick color scheme selection

### Users (Superuser only)
- Create new admin or superuser accounts
- Activate/deactivate users
- Delete users
- Switch to another user's session

### Password
Change your account password.
