# LAIM - Lab Asset Inventory Manager

A modern, high-density hardware inventory management system built for lab environments. Features real-time search, category filtering, and a beautiful 2026-style UI with professional typography.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **5 Hardware Categories**: Laptops, Desktops, Smart TVs, Servers, and WAPs
- **Real-time Search**: Instant filtering across hostnames, serials, MACs, and asset tags
- **RBAC**: Role-based access control with superuser and admin accounts
- **Modern UI**: 2026-style design with Geist/Inter fonts and tabular numbers
- **Docker-based**: Fully containerized FastAPI + PostgreSQL stack
- **Proxmox Ready**: Automated LXC container deployment on Proxmox VE 9.1.2

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL 16
- **Frontend**: Jinja2, Tailwind CSS, Vanilla JavaScript
- **Infrastructure**: Docker Compose, Debian 13 LXC
- **Fonts**: Geist Sans (headers), Inter (body), Geist Mono (technical data)

## Quick Start

### Option 1: Proxmox LXC Deployment (Recommended)

1. **On Proxmox host**, create the container:
```bash
chmod +x proxmox_lxc_create.sh
./proxmox_lxc_create.sh
```

2. **Copy files to container**:
```bash
pct push 200 /path/to/laim /opt/laim -r
```

3. **Enter container and deploy**:
```bash
pct enter 200
cd /opt/laim
chmod +x setup.sh
./setup.sh
```

4. **Access the application**:
```
http://<container-ip>:8000
```

### Option 2: Local Docker Deployment

1. **Clone the repository**:
```bash
git clone <your-repo-url>
cd inventory
```

2. **Create environment file**:
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. **Start the application**:
```bash
docker compose up -d
```

4. **Seed the database**:
```bash
docker compose exec web python -m app.seed --with-samples
```

5. **Access the application**:
```
http://localhost:8000
```

## Default Credentials

| Username | Password | Role |
|----------|----------|------|
| superadmin | SuperAdmin123! | Superuser |
| admin1 | Admin123! | Admin |
| admin2 | Admin123! | Admin |
| admin3 | Admin123! | Admin |

**⚠️ IMPORTANT**: Change these passwords in production!

## Data Model

Each inventory item includes:
- **Hostname**: Device hostname (e.g., LAB-LAPTOP-001)
- **Serial Number**: Manufacturer serial number
- **MAC Address**: Network MAC address (optional)
- **Asset Tag**: Internal asset tracking number
- **Item Type**: Laptop, Desktop, Smart TV, Server, or WAP
- **Room Location**: 2265 or 2266
- **Sub-location**: Rack, shelf, or desk identifier
- **Notes**: Additional information

## API Endpoints

### Authentication
- `POST /api/login` - Get access token
- `GET /logout` - Logout and clear session

### Inventory Items
- `GET /api/items` - List items (supports search, type, and room filters)
- `GET /api/items/{id}` - Get specific item
- `POST /api/items` - Create new item (admin+)
- `PUT /api/items/{id}` - Update item (admin+)
- `DELETE /api/items/{id}` - Soft delete item (admin+)

### User Management (Superuser only)
- `GET /api/users` - List users
- `POST /api/users` - Create user
- `PUT /api/users/{id}` - Update user

### Statistics
- `GET /api/stats` - Get dashboard statistics

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | Database username | laim |
| `POSTGRES_PASSWORD` | Database password | (generated) |
| `POSTGRES_DB` | Database name | laim |
| `APP_PORT` | Application port | 8000 |
| `SECRET_KEY` | JWT secret key | (generated) |
| `SUPERUSER_USERNAME` | Initial superuser username | superadmin |
| `SUPERUSER_PASSWORD` | Initial superuser password | SuperAdmin123! |

## Project Structure

```
inventory/
├── proxmox_lxc_create.sh    # Proxmox LXC creation script
├── docker-compose.yml       # Docker orchestration
├── Dockerfile               # Application container
├── requirements.txt         # Python dependencies
├── setup.sh                 # Container setup script
├── app/
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # Database configuration
│   ├── auth.py              # Authentication utilities
│   ├── schemas.py           # Pydantic schemas
│   ├── main.py              # FastAPI application
│   └── seed.py              # Database seeding
└── templates/
    ├── base.html            # Base template
    ├── login.html           # Login page
    └── dashboard.html       # Main dashboard
```

## Development

### Running Tests
```bash
docker compose exec web pytest
```

### View Logs
```bash
docker compose logs -f web
```

### Database Shell
```bash
docker compose exec db psql -U laim -d laim
```

### Application Shell
```bash
docker compose exec web python
```

## Useful Commands

### Docker Compose
```bash
# Stop services
docker compose down

# Restart services
docker compose restart

# Rebuild images
docker compose build --no-cache

# View service status
docker compose ps
```

### Proxmox LXC
```bash
# Start container
pct start 200

# Stop container
pct stop 200

# Enter container
pct enter 200

# View container config
pct config 200
```

## Design Philosophy

- **Fast & Responsive**: Built for speed with a small dataset (hundreds of items)
- **Professional Grade**: Production-ready code with proper error handling
- **Beautiful UI**: Modern 2026 aesthetic with Swiss precision typography
- **Repeatable**: Fully automated deployment from scratch

## Requirements

### Proxmox Deployment
- Proxmox VE 9.1.2+
- Debian 13 (Trixie) template
- 2GB RAM, 2 CPU cores, 16GB disk (minimum)

### Manual Deployment
- Docker 24+
- Docker Compose v2+
- 2GB RAM available

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

Built with ❤️ for lab infrastructure management
