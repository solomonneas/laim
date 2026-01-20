# Deployment Guide

## Docker Compose (Recommended)

### Requirements
- Docker 24+
- Docker Compose v2+
- 2GB RAM available

### Installation

```bash
git clone https://github.com/solomonneas/laim.git
cd laim
cp .env.example .env
docker compose up -d
```

Access at `http://localhost:8000`

### Default Credentials

| Username | Password | Role |
|----------|----------|------|
| superadmin | SuperAdmin123! | Superuser |

> Change these in production via Settings > Users

---

## Proxmox LXC

### Requirements
- Proxmox VE 8.0+
- Debian 12/13 template
- 2GB RAM, 2 CPU cores, 16GB disk

### Installation

1. **Create container on Proxmox host:**
```bash
chmod +x proxmox_lxc_create.sh
./proxmox_lxc_create.sh
```

2. **Copy files to container:**
```bash
pct push 200 /path/to/laim /opt/laim -r
```

3. **Enter container and deploy:**
```bash
pct enter 200
cd /opt/laim
chmod +x setup.sh
./setup.sh
```

4. **Access:** `http://<container-ip>:8000`

### LXC Commands

```bash
pct start 200      # Start container
pct stop 200       # Stop container
pct enter 200      # Enter container shell
pct config 200     # View config
```

---

## Upgrading

### Standard Upgrade

```bash
cd /path/to/laim
docker compose down
git pull origin main
docker compose build --no-cache
docker compose up -d
docker compose exec web alembic upgrade head
```

### Verify Upgrade

```bash
docker compose logs -f web
curl http://localhost:8000/health
```

### Important Notes

- Always stop the app before pulling updates
- Run migrations after rebuilding
- Fresh installations don't need migrations

---

## Common Commands

```bash
# View logs
docker compose logs -f web

# Restart services
docker compose restart

# Database shell
docker compose exec db psql -U laim -d laim

# Application shell
docker compose exec web python

# Run migrations
docker compose exec web alembic upgrade head
```
