<p align="center">
  <img src="static/logo.svg" alt="LAIM" width="300">
</p>

<h3 align="center">Lab Asset Inventory Manager</h3>

<p align="center">A modern, self-hosted inventory management system for lab environments.</p>

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Multi-category tracking** - Laptops, Desktops, Servers, Switches, WAPs, Firewalls, Smart TVs, and more
- **Real-time search** - Instant filtering across hostnames, serials, MACs, and asset tags
- **Auto-discovery** - Sync devices from Netdisco and LibreNMS
- **Role-based access** - Superuser and admin roles with granular permissions
- **Customizable UI** - Dark/light mode, custom branding, configurable colors
- **Docker-ready** - Single command deployment with Docker Compose

## Quick Start

```bash
# Clone and start
git clone https://github.com/solomonneas/laim.git
cd laim
cp .env.example .env
docker compose up -d

# Access at http://localhost:8000
# Default login: superadmin / SuperAdmin123!
```

## Documentation

| Document | Description |
|----------|-------------|
| [Deployment](docs/DEPLOYMENT.md) | Installation guides for Docker and Proxmox LXC |
| [Configuration](docs/CONFIGURATION.md) | Environment variables and settings |
| [API Reference](docs/API.md) | REST API endpoints |
| [Integrations](docs/INTEGRATIONS.md) | Netdisco and LibreNMS sync setup |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **Frontend**: Jinja2, Tailwind CSS, Vanilla JS
- **Infrastructure**: Docker Compose

## License

MIT License - see [LICENSE](LICENSE) for details.

---

[Report Issues](https://github.com/solomonneas/laim/issues)
