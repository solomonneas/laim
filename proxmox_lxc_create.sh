#!/bin/bash
#===============================================================================
# LAIM - Lab Asset Inventory Manager
# Proxmox VE 9.1.2 LXC Container Creation Script
#===============================================================================
# Run this script on the Proxmox host to create an unprivileged LXC container
# with Docker nesting enabled for the LAIM application.
#===============================================================================

set -euo pipefail

# Configuration - Adjust these values as needed
CTID="${CTID:-200}"
HOSTNAME="${HOSTNAME:-laim}"
STORAGE="${STORAGE:-local-lvm}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
MEMORY="${MEMORY:-2048}"
SWAP="${SWAP:-512}"
CORES="${CORES:-2}"
DISK_SIZE="${DISK_SIZE:-16}"
BRIDGE="${BRIDGE:-vmbr0}"
IP_CONFIG="${IP_CONFIG:-dhcp}"  # Use "dhcp" or "192.168.1.100/24,gw=192.168.1.1"
PASSWORD="${PASSWORD:-}"        # Leave empty to be prompted
SSH_KEY="${SSH_KEY:-}"          # Path to SSH public key (optional)

# Debian 13 (Trixie) template name pattern
TEMPLATE_NAME="debian-13"

#-------------------------------------------------------------------------------
# Helper Functions
#-------------------------------------------------------------------------------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[ERROR] $*" >&2
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root on the Proxmox host"
    fi
}

#-------------------------------------------------------------------------------
# Template Management
#-------------------------------------------------------------------------------
get_or_download_template() {
    log "Checking for Debian 13 (Trixie) template..."

    # List available templates
    local available_templates
    available_templates=$(pveam list "$TEMPLATE_STORAGE" 2>/dev/null || true)

    # Check if Debian 13 template exists
    local template_file
    template_file=$(echo "$available_templates" | grep -i "$TEMPLATE_NAME" | head -1 | awk '{print $1}')

    if [[ -z "$template_file" ]]; then
        log "Debian 13 template not found locally. Updating template list..."
        pveam update

        # Find available Debian 13 template
        local remote_template
        remote_template=$(pveam available | grep -i "debian-13" | head -1 | awk '{print $2}')

        if [[ -z "$remote_template" ]]; then
            error "Debian 13 (Trixie) template not found in repository. Please check Proxmox template availability."
        fi

        log "Downloading template: $remote_template"
        pveam download "$TEMPLATE_STORAGE" "$remote_template"

        template_file="${TEMPLATE_STORAGE}:vztmpl/${remote_template}"
    else
        template_file="${TEMPLATE_STORAGE}:vztmpl/$(basename "$template_file")"
    fi

    echo "$template_file"
}

#-------------------------------------------------------------------------------
# Container Creation
#-------------------------------------------------------------------------------
create_container() {
    local template="$1"

    log "Creating LXC container (CTID: $CTID)..."

    # Check if container already exists
    if pct status "$CTID" &>/dev/null; then
        error "Container $CTID already exists. Choose a different CTID or remove the existing container."
    fi

    # Build pct create command
    local pct_cmd=(
        pct create "$CTID" "$template"
        --hostname "$HOSTNAME"
        --memory "$MEMORY"
        --swap "$SWAP"
        --cores "$CORES"
        --rootfs "${STORAGE}:${DISK_SIZE}"
        --net0 "name=eth0,bridge=${BRIDGE}"
        --unprivileged 1
        --features "nesting=1,keyctl=1"
        --onboot 1
        --start 0
    )

    # Add network configuration
    if [[ "$IP_CONFIG" == "dhcp" ]]; then
        pct_cmd+=(--net0 "name=eth0,bridge=${BRIDGE},ip=dhcp")
    else
        pct_cmd+=(--net0 "name=eth0,bridge=${BRIDGE},ip=${IP_CONFIG}")
    fi

    # Add password if provided
    if [[ -n "$PASSWORD" ]]; then
        pct_cmd+=(--password "$PASSWORD")
    fi

    # Add SSH key if provided
    if [[ -n "$SSH_KEY" && -f "$SSH_KEY" ]]; then
        pct_cmd+=(--ssh-public-keys "$SSH_KEY")
    fi

    # Execute container creation
    "${pct_cmd[@]}"

    log "Container created successfully"
}

#-------------------------------------------------------------------------------
# Container Configuration
#-------------------------------------------------------------------------------
configure_container() {
    log "Applying additional container configuration..."

    # Enable features required for Docker
    cat >> "/etc/pve/lxc/${CTID}.conf" << 'EOF'

# Docker compatibility settings
lxc.apparmor.profile: unconfined
lxc.cgroup2.devices.allow: a
lxc.cap.drop:
lxc.mount.auto: proc:rw sys:rw
EOF

    log "Container configuration updated"
}

#-------------------------------------------------------------------------------
# Post-Creation Setup
#-------------------------------------------------------------------------------
start_and_setup() {
    log "Starting container..."
    pct start "$CTID"

    # Wait for container to be ready
    log "Waiting for container to initialize..."
    sleep 10

    # Install essential packages
    log "Installing Docker and dependencies inside container..."
    pct exec "$CTID" -- bash -c '
        export DEBIAN_FRONTEND=noninteractive

        # Update package lists
        apt-get update

        # Install prerequisites
        apt-get install -y \
            ca-certificates \
            curl \
            gnupg \
            lsb-release \
            git \
            sudo

        # Add Docker official GPG key
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg

        # Add Docker repository
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

        # Install Docker
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        # Enable and start Docker
        systemctl enable docker
        systemctl start docker

        # Create app directory
        mkdir -p /opt/laim

        echo "Docker installation complete!"
    '

    log "Container setup complete"
}

#-------------------------------------------------------------------------------
# Main Execution
#-------------------------------------------------------------------------------
main() {
    log "=========================================="
    log "LAIM - LXC Container Deployment Script"
    log "=========================================="

    check_root

    # Prompt for password if not set
    if [[ -z "$PASSWORD" ]]; then
        read -sp "Enter root password for container: " PASSWORD
        echo
    fi

    local template
    template=$(get_or_download_template)

    log "Using template: $template"

    create_container "$template"
    configure_container
    start_and_setup

    log "=========================================="
    log "Deployment Complete!"
    log "=========================================="
    log ""
    log "Container Details:"
    log "  CTID:     $CTID"
    log "  Hostname: $HOSTNAME"
    log "  Memory:   ${MEMORY}MB"
    log "  Cores:    $CORES"
    log "  Disk:     ${DISK_SIZE}GB"
    log ""
    log "Next Steps:"
    log "  1. Copy LAIM application files to container:"
    log "     pct push $CTID /path/to/laim /opt/laim -r"
    log ""
    log "  2. Enter container and run setup:"
    log "     pct enter $CTID"
    log "     cd /opt/laim && ./setup.sh"
    log ""
    log "  3. Access the application at:"
    log "     http://<container-ip>:8000"
    log ""
}

main "$@"
