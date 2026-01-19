#!/bin/bash
#===============================================================================
#
#    ██╗      █████╗ ██╗███╗   ███╗
#    ██║     ██╔══██╗██║████╗ ████║
#    ██║     ███████║██║██╔████╔██║
#    ██║     ██╔══██║██║██║╚██╔╝██║
#    ███████╗██║  ██║██║██║ ╚═╝ ██║
#    ╚══════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝
#
#    Lab Asset Inventory Manager
#    Proxmox LXC Deployment Script
#
#===============================================================================
# Run this script on the Proxmox host to deploy everything automatically
#===============================================================================

set -euo pipefail

# Configuration
CT_HOSTNAME="${CT_HOSTNAME:-laim}"
STORAGE="${STORAGE:-local-lvm}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
MEMORY="${MEMORY:-2048}"
SWAP="${SWAP:-512}"
CORES="${CORES:-2}"
DISK_SIZE="${DISK_SIZE:-16}"
BRIDGE="${BRIDGE:-vmbr0}"
IP_CONFIG="${IP_CONFIG:-dhcp}"
VLAN_TAG="${VLAN_TAG:-}"
FIREWALL="${FIREWALL:-0}"
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

get_next_ctid() {
    # Find the next available CTID starting from 100
    local ctid=100
    while pct status "$ctid" &>/dev/null || qm status "$ctid" &>/dev/null; do
        ((ctid++))
    done
    echo "$ctid"
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
        --hostname "$CT_HOSTNAME"
        --memory "$MEMORY"
        --swap "$SWAP"
        --cores "$CORES"
        --rootfs "${STORAGE}:${DISK_SIZE}"
        --unprivileged 1
        --features "nesting=1,keyctl=1"
        --onboot 1
        --start 0
    )

    # Build network configuration string
    local net_config="name=eth0,bridge=${BRIDGE}"
    if [[ "$IP_CONFIG" == "dhcp" ]]; then
        net_config+=",ip=dhcp"
    else
        net_config+=",ip=${IP_CONFIG}"
    fi
    [[ -n "$VLAN_TAG" ]] && net_config+=",tag=${VLAN_TAG}"
    [[ "$FIREWALL" == "1" ]] && net_config+=",firewall=1"
    pct_cmd+=(--net0 "$net_config")

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

    log "Configuring DNS..."
    pct exec "$CTID" -- bash -c '
        # Ensure DNS is configured
        echo "nameserver 8.8.8.8" > /etc/resolv.conf
        echo "nameserver 1.1.1.1" >> /etc/resolv.conf
    '

    log "Installing Docker and dependencies..."
    pct exec "$CTID" -- bash -c '
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get install -y ca-certificates curl gnupg lsb-release git sudo

        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg

        # Use bookworm if trixie (Debian 13) - Docker may not have trixie packages yet
        DISTRO=$(lsb_release -cs)
        if [ "$DISTRO" = "trixie" ]; then
            DISTRO="bookworm"
        fi

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $DISTRO stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        systemctl enable docker
        systemctl start docker
    '
    success "Docker installed"

    log "Setting container hostname..."
    pct exec "$CTID" -- bash -c "
        hostnamectl set-hostname ${CT_HOSTNAME}
        echo '${CT_HOSTNAME}' > /etc/hostname
    "
    success "Hostname set to ${CT_HOSTNAME}"
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
    echo "  Hostname: $CT_HOSTNAME"
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
    echo -e "
${BLUE}    ██╗      █████╗ ██╗███╗   ███╗${NC}
${BLUE}    ██║     ██╔══██╗██║████╗ ████║${NC}
${BLUE}    ██║     ███████║██║██╔████╔██║${NC}
${BLUE}    ██║     ██╔══██║██║██║╚██╔╝██║${NC}
${BLUE}    ███████╗██║  ██║██║██║ ╚═╝ ██║${NC}
${BLUE}    ╚══════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝${NC}

    ${GREEN}Lab Asset Inventory Manager${NC}
    ${YELLOW}Proxmox LXC Deployment Script${NC}
"
    echo

    check_root

    # Get next available CTID if not explicitly set
    if [[ -z "${CTID:-}" ]]; then
        CTID=$(get_next_ctid)
        log "Auto-selected CTID: $CTID"
    else
        log "Using specified CTID: $CTID"
    fi

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
