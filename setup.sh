#!/bin/bash
#===============================================================================
# LAIM - Lab Asset Inventory Manager
# Container-Side Setup Script
#===============================================================================
# Run this script inside the LXC container to build, deploy, and seed the
# application using Docker Compose.
#===============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="${APP_DIR:-/opt/laim}"
ENV_FILE="${APP_DIR}/.env"

#-------------------------------------------------------------------------------
# Helper Functions
#-------------------------------------------------------------------------------
log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $*"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
    exit 1
}

#-------------------------------------------------------------------------------
# Pre-flight Checks
#-------------------------------------------------------------------------------
preflight_checks() {
    log "Running pre-flight checks..."

    # Check if running as root (or with Docker permissions)
    if ! docker info &>/dev/null; then
        error "Docker is not running or you don't have permission to use it"
    fi

    # Check if docker compose is available
    if ! docker compose version &>/dev/null; then
        error "Docker Compose plugin is not installed"
    fi

    # Check if we're in the app directory
    if [[ ! -f "${APP_DIR}/docker-compose.yml" ]]; then
        error "docker-compose.yml not found in ${APP_DIR}"
    fi

    success "Pre-flight checks passed"
}

#-------------------------------------------------------------------------------
# Environment Setup
#-------------------------------------------------------------------------------
setup_environment() {
    log "Setting up environment..."

    cd "${APP_DIR}"

    # Create .env file if it doesn't exist
    if [[ ! -f "${ENV_FILE}" ]]; then
        log "Creating .env file with default values..."

        # Generate a random secret key
        SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 64)

        cat > "${ENV_FILE}" << EOF
# LAIM Environment Configuration
# Generated on $(date '+%Y-%m-%d %H:%M:%S')

# Database
POSTGRES_USER=laim
POSTGRES_PASSWORD=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32)
POSTGRES_DB=laim

# Application
APP_NAME=LAIM
APP_ENV=production
APP_PORT=8000
SECRET_KEY=${SECRET_KEY}

# Superuser (change these in production!)
SUPERUSER_USERNAME=superadmin
SUPERUSER_PASSWORD=SuperAdmin123!
SUPERUSER_EMAIL=admin@laim.local
EOF

        warn "Created .env file with generated passwords"
        warn "Review and update credentials in ${ENV_FILE} for production use"
    else
        log "Using existing .env file"
    fi

    success "Environment configured"
}

#-------------------------------------------------------------------------------
# Build and Deploy
#-------------------------------------------------------------------------------
build_and_deploy() {
    log "Building Docker images..."

    cd "${APP_DIR}"

    # Pull latest base images
    docker compose pull db || true

    # Build the application image
    docker compose build --no-cache web

    success "Docker images built"

    log "Starting services..."

    # Start services
    docker compose up -d

    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    local max_attempts=30
    local attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if docker compose ps | grep -q "healthy"; then
            break
        fi
        sleep 2
        ((attempt++))
        echo -n "."
    done
    echo

    if [[ $attempt -ge $max_attempts ]]; then
        warn "Services may not be fully healthy yet"
        docker compose ps
    else
        success "Services are running and healthy"
    fi
}

#-------------------------------------------------------------------------------
# Database Seeding
#-------------------------------------------------------------------------------
seed_database() {
    log "Seeding database..."

    cd "${APP_DIR}"

    # Wait a bit more for the database to be ready
    sleep 5

    # Run the seed script (users only, no sample data)
    docker compose exec -T web python -m app.seed

    success "Database seeded"
}

#-------------------------------------------------------------------------------
# Display Status
#-------------------------------------------------------------------------------
display_status() {
    cd "${APP_DIR}"

    echo
    echo "=============================================="
    echo -e "${GREEN}LAIM Deployment Complete${NC}"
    echo "=============================================="
    echo

    # Get container IP
    local container_ip
    container_ip=$(hostname -I | awk '{print $1}')

    echo "Service Status:"
    docker compose ps
    echo

    echo "Access Information:"
    echo "  URL: http://${container_ip}:8000"
    echo "  URL: http://localhost:8000 (from within container)"
    echo

    echo "Default Credentials:"
    echo "  Superuser: superadmin / SuperAdmin123!"
    echo "  Admin 1:   admin1 / Admin123!"
    echo "  Admin 2:   admin2 / Admin123!"
    echo "  Admin 3:   admin3 / Admin123!"
    echo

    echo -e "${YELLOW}IMPORTANT: Change default passwords in production!${NC}"
    echo

    echo "Useful Commands:"
    echo "  View logs:     docker compose logs -f"
    echo "  Stop:          docker compose down"
    echo "  Restart:       docker compose restart"
    echo "  Shell access:  docker compose exec web bash"
    echo

    echo "=============================================="
}

#-------------------------------------------------------------------------------
# Main Execution
#-------------------------------------------------------------------------------
main() {
    echo
    echo "=============================================="
    echo "LAIM - Lab Asset Inventory Manager"
    echo "Container Setup Script"
    echo "=============================================="
    echo

    preflight_checks
    setup_environment
    build_and_deploy
    seed_database
    display_status
}

# Parse arguments
case "${1:-}" in
    --build-only)
        preflight_checks
        setup_environment
        build_and_deploy
        ;;
    --seed-only)
        seed_database
        ;;
    --status)
        display_status
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo
        echo "Options:"
        echo "  --build-only    Only build and start containers"
        echo "  --seed-only     Only run database seeding"
        echo "  --status        Show deployment status"
        echo "  --help          Show this help message"
        echo
        echo "Without options, runs full setup (build + seed)"
        ;;
    *)
        main
        ;;
esac
