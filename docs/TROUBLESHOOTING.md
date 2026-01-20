# Troubleshooting

## Database Issues

### Migration Errors

**"type already exists" or "column does not exist"**

This happens when the app started before migrations ran.

**Fix:**
```bash
# Connect to database
docker compose exec db psql -U laim -d laim

# Add missing columns
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS source VARCHAR(50);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS firmware_version VARCHAR(100);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS model VARCHAR(255);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS vendor VARCHAR(255);

# Exit
\q

# Mark migrations complete
docker compose exec web alembic stamp head
docker compose restart web
```

**Prevention:**
- Stop app before pulling updates: `docker compose down`
- Run migrations after rebuild: `docker compose exec web alembic upgrade head`

---

## Sync Issues

### Authentication Failed

- Verify API credentials in `.env`
- Check that API user has read permissions
- Ensure API URL is reachable from LAIM container:
  ```bash
  docker compose exec web curl -I https://netdisco.example.com
  ```

### No Devices Synced

- Check sync history: `GET /api/sync/history`
- View logs: `docker compose logs -f web`
- Verify devices exist in source system

### Duplicate Devices

- Sync deduplicates by serial number first, then MAC
- Devices without both identifiers may create duplicates

---

## Authentication Issues

### Can't Log In

- Verify credentials are correct
- Check if user is active (superuser can check in Settings > Users)
- Clear browser cookies and try again

### Session Expired

- Sessions last 7 days by default
- Re-login to get a new token

---

## Container Issues

### Container Won't Start

```bash
# Check logs
docker compose logs web
docker compose logs db

# Verify ports aren't in use
netstat -tlnp | grep 8000
```

### Database Connection Failed

```bash
# Check if database is running
docker compose ps

# Restart database
docker compose restart db

# Wait a few seconds, then restart web
docker compose restart web
```

### Out of Disk Space

```bash
# Clean up Docker
docker system prune -a

# Check disk usage
df -h
```

---

## Performance Issues

### Slow Search

- Search is client-side for datasets under 10,000 items
- For larger datasets, consider server-side filtering

### High Memory Usage

- Default config is optimized for 2GB RAM
- Reduce `SYNC_RATE_LIMIT` if syncing large device lists

---

## Getting Help

1. Check the [logs](#viewing-logs)
2. Search [existing issues](https://github.com/solomonneas/laim/issues)
3. Open a [new issue](https://github.com/solomonneas/laim/issues/new) with:
   - LAIM version
   - Error messages
   - Steps to reproduce

---

## Viewing Logs

```bash
# All logs
docker compose logs -f

# Web app only
docker compose logs -f web

# Database only
docker compose logs -f db

# Last 100 lines
docker compose logs --tail=100 web
```
