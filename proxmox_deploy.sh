#!/bin/bash
#===============================================================================
# LAIM - Lab Asset Inventory Manager
# FULLY AUTOMATED Proxmox Deployment Script
#===============================================================================
# Run this script on the Proxmox host to deploy everything automatically
#===============================================================================

set -euo pipefail

# Configuration
CTID="${CTID:-200}"
HOSTNAME="${HOSTNAME:-laim}"
STORAGE="${STORAGE:-local-lvm}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
MEMORY="${MEMORY:-2048}"
SWAP="${SWAP:-512}"
CORES="${CORES:-2}"
DISK_SIZE="${DISK_SIZE:-16}"
BRIDGE="${BRIDGE:-vmbr0}"
IP_CONFIG="${IP_CONFIG:-dhcp}"
PASSWORD="${PASSWORD:-}"
GITHUB_REPO="https://github.com/solomonneas/laim.git"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $*" >&2; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $*" >&2; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

check_root() {
    [[ $EUID -eq 0 ]] || error "This script must be run as root on the Proxmox host"
}

get_or_download_template() {
    log "Checking for Debian 13 (Trixie) template..."
    local available_templates
    available_templates=$(pveam list "$TEMPLATE_STORAGE" 2>/dev/null || true)
    local template_file
    template_file=$(echo "$available_templates" | grep -i "debian-13" | head -1 | awk '{print $1}')

    if [[ -z "$template_file" ]]; then
        log "Debian 13 template not found. Updating and downloading..."
        pveam update
        local remote_template
        remote_template=$(pveam available | grep -i "debian-13" | head -1 | awk '{print $2}')
        [[ -n "$remote_template" ]] || error "Debian 13 template not found in repository"
        log "Downloading: $remote_template"
        pveam download "$TEMPLATE_STORAGE" "$remote_template"
        template_file="${TEMPLATE_STORAGE}:vztmpl/${remote_template}"
    else
        template_file="${TEMPLATE_STORAGE}:vztmpl/$(basename "$template_file")"
    fi
    echo "$template_file"
}

create_container() {
    local template="$1"
    log "Creating LXC container (CTID: $CTID)..."

    if pct status "$CTID" &>/dev/null; then
        error "Container $CTID already exists. Remove it or choose a different CTID."
    fi

    local pct_cmd=(
        pct create "$CTID" "$template"
        --hostname "$HOSTNAME"
        --memory "$MEMORY"
        --swap "$SWAP"
        --cores "$CORES"
        --rootfs "${STORAGE}:${DISK_SIZE}"
        --unprivileged 1
        --features "nesting=1,keyctl=1"
        --onboot 1
        --start 0
    )

    if [[ "$IP_CONFIG" == "dhcp" ]]; then
        pct_cmd+=(--net0 "name=eth0,bridge=${BRIDGE},ip=dhcp")
    else
        pct_cmd+=(--net0 "name=eth0,bridge=${BRIDGE},ip=${IP_CONFIG}")
    fi

    [[ -n "$PASSWORD" ]] && pct_cmd+=(--password "$PASSWORD")

    "${pct_cmd[@]}"
    success "Container created"
}

configure_container() {
    log "Applying Docker compatibility settings..."
    cat >> "/etc/pve/lxc/${CTID}.conf" << 'EOF'

# Docker compatibility
lxc.apparmor.profile: unconfined
lxc.cgroup2.devices.allow: a
lxc.cap.drop:
lxc.mount.auto: proc:rw sys:rw
EOF
    success "Container configured"
}

start_and_install_docker() {
    log "Starting container..."
    pct start "$CTID"
    sleep 10

    log "Installing Docker and dependencies..."
    pct exec "$CTID" -- bash -c '
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get install -y ca-certificates curl gnupg lsb-release git sudo

        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        systemctl enable docker
        systemctl start docker
    '
    success "Docker installed"

    log "Setting container hostname..."
    pct exec "$CTID" -- bash -c "
        hostnamectl set-hostname ${HOSTNAME}
        echo '${HOSTNAME}' > /etc/hostname
    "
    success "Hostname set to ${HOSTNAME}"
}

clone_and_deploy() {
    log "Cloning repository from GitHub..."
    pct exec "$CTID" -- bash -c "
        cd /opt
        rm -rf laim
        git clone ${GITHUB_REPO}
        cd laim
        chmod +x setup.sh
    "
    success "Repository cloned"

    log "Running application setup..."
    pct exec "$CTID" -- bash -c "cd /opt/laim && ./setup.sh"
}

display_completion() {
    local container_ip
    container_ip=$(pct exec "$CTID" -- hostname -I | awk '{print $1}')

    echo
    echo "=============================================="
    echo -e "${GREEN}LAIM Deployment Complete!${NC}"
    echo "=============================================="
    echo
    echo "Container Details:"
    echo "  CTID:     $CTID"
    echo "  Hostname: $HOSTNAME"
    echo "  IP:       $container_ip"
    echo
    echo "Access Application:"
    echo "  URL: http://${container_ip}:8000"
    echo
    echo "Default Credentials:"
    echo "  Superuser: superadmin / SuperAdmin123!"
    echo "  Admin 1:   admin1 / Admin123!"
    echo
    echo "Useful Commands:"
    echo "  Enter container:  pct enter $CTID"
    echo "  View logs:        pct exec $CTID -- docker compose -f /opt/laim/docker-compose.yml logs -f"
    echo "  Restart:          pct restart $CTID"
    echo "  Stop:             pct stop $CTID"
    echo
    echo "=============================================="
}

main() {
    echo
    echo "=============================================="
    echo "LAIM - Fully Automated Deployment"
    echo "=============================================="
    echo

    check_root

    if [[ -z "$PASSWORD" ]]; then
        read -sp "Enter root password for container: " PASSWORD
        echo
    fi

    local template
    template=$(get_or_download_template)
    log "Using template: $template"

    create_container "$template"
    configure_container
    start_and_install_docker
    clone_and_deploy
    display_completion
}

main "$@"
